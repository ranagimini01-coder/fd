"""Critical API and observer-ingestion regression tests for market backend."""

from __future__ import annotations

import time
import asyncio
import uuid
import io
import json
import zipfile
from urllib.parse import urlparse

import pytest
import websockets
from websockets.http11 import Headers, Response


def _url(base_url: str, path: str) -> str:
    return f"{base_url}{path}"


def _obs_headers(key: str) -> dict[str, str]:
    return {"Content-Type": "application/json", "X-Market-QX-Key": key}


def _session_id() -> str:
    return f"TESTONLY-session-{uuid.uuid4()}"


def _dedupe(tag: str) -> str:
    return f"TESTONLY-{tag}-{uuid.uuid4()}"


def _now_iso(offset_seconds: int = 0) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + offset_seconds))


def _aligned_candle_bounds(seconds: int = 60, shift_windows: int = 1) -> tuple[int, int]:
    now = int(time.time())
    close_epoch = (now // seconds) * seconds - (shift_windows * seconds)
    start_epoch = close_epoch - seconds
    return start_epoch, close_epoch


def test_deriv_connect_retries_alternate_endpoints_on_invalid_status(monkeypatch):
    from deriv_service import DerivService

    class DummyStore:
        pass

    class DummySocket:
        pass

    service = DerivService(DummyStore(), None, None)
    service.connect_urls = ["wss://bad.example/ws", "wss://good.example/ws"]
    seen = []

    async def fake_connect(url, **kwargs):
        seen.append(url)
        if url == service.connect_urls[0]:
            raise websockets.exceptions.InvalidStatus(Response(403, "Forbidden", Headers(), b""))
        return DummySocket()

    monkeypatch.setattr(websockets, "connect", fake_connect)

    async def exercise():
        return await service._open_connection()

    result = asyncio.run(exercise())

    assert result is not None
    assert seen == service.connect_urls


def test_telemetry_sse_emits_safe_disconnected_snapshot():
    from telemetry_routes import telemetry_router

    router = telemetry_router(None, None, None, None, None, None)
    assert router.routes[0].path == '/api/telemetry/stream'
    endpoint = router.routes[0].endpoint
    response = asyncio.run(endpoint(source='deriv', symbol='R_10', timeframe='unsupported'))

    async def first_event():
        return await response.body_iterator.__anext__()

    payload = asyncio.run(first_event())
    assert response.media_type == 'text/event-stream'
    assert payload.startswith('event: telemetry\ndata: ')
    assert '"status":"DISCONNECTED"' in payload
    assert '"direction":"NO_SIGNAL"' in payload


def test_telemetry_sse_emits_named_pre_signal_event():
    from types import SimpleNamespace
    from telemetry_routes import telemetry_router

    pre_signal = {
        'id': 'deriv:frxEURUSD:1m:180', 'source': 'deriv', 'symbol': 'frxEURUSD',
        'pair': 'EUR/USD', 'direction': 'CALL', 'timeframe': '1m',
        'setupConfidence': 92, 'entryEpoch': 180, 'generatedAt': 150,
        'countdownSeconds': 30,
    }
    signals = SimpleNamespace(current_pre_signal=lambda *_args: pre_signal)
    router = telemetry_router(None, None, None, signals, None, None)
    response = asyncio.run(router.routes[0].endpoint(source='deriv', symbol='frxEURUSD', timeframe='1m'))

    async def first_event():
        return await response.body_iterator.__anext__()

    payload = asyncio.run(first_event())
    assert payload.startswith('event: PRE_SIGNAL\ndata: ')
    assert '"direction":"CALL"' in payload
    assert '"countdownSeconds":30' in payload


def test_only_cross_validated_observer_ticks_make_signal_eligible_candles():
    from types import SimpleNamespace
    from market_store import MarketStore

    class Collection:
        def __init__(self):
            self.updates = []

        async def find_one(self, *_args, **_kwargs):
            return None

        async def update_one(self, *args, **kwargs):
            self.updates.append((args, kwargs))

        async def insert_one(self, *_args, **_kwargs):
            return None

    candles = Collection()
    database = SimpleNamespace(
        market_instruments=Collection(), market_candles=candles, market_ticks=Collection(),
    )
    store = MarketStore(database)

    async def exercise():
        await store.tick('market-qx-observer-v2', 'EUR/USD', 1.1, time.time(), 'VISIBLE_DOM_CROSS_VALIDATED')
        verified_count = len(candles.updates)
        await store.tick('market-qx-observer-v2', 'GBP/USD', 1.2, time.time(), 'VISIBLE_DOM_RECEIPT_TIME')
        return verified_count

    verified_count = asyncio.run(exercise())
    assert verified_count > 0
    assert all(call[0][1]['$set']['completeness'] == 'CROSS_VALIDATED' for call in candles.updates[:verified_count])
    assert all(call[0][1]['$set']['completeness'] == 'PARTIAL_TICK_COVERAGE' for call in candles.updates[verified_count:])


def test_deriv_tick_storage_defers_streamed_timeframes_but_builds_other_candles():
    from types import SimpleNamespace
    from market_config import TIMEFRAMES
    from market_store import MarketStore

    class Collection:
        def __init__(self):
            self.updates = []
            self.inserted = []

        async def find_one(self, *_args, **_kwargs):
            return None

        async def update_one(self, *args, **kwargs):
            self.updates.append((args, kwargs))

        async def insert_one(self, document):
            self.inserted.append(document)

    candles = Collection()
    ticks = Collection()
    database = SimpleNamespace(
        market_instruments=Collection(), market_candles=candles, market_ticks=ticks,
    )
    store = MarketStore(database)
    provider_timeframes = {'1m', '5m', '15m'}
    asyncio.run(store.tick(
        'deriv', 'frxEURUSD', 1.1, time.time(), 'DERIV_PUBLIC_TICK',
        skip_timeframes=provider_timeframes,
    ))

    written_timeframes = {args[0]['timeframe'] for args, _kwargs in candles.updates}
    assert written_timeframes == set(TIMEFRAMES) - provider_timeframes
    assert not (written_timeframes & provider_timeframes)
    assert len(ticks.inserted) == 1
    assert ticks.inserted[0]['symbol'] == 'frxEURUSD'


def test_telemetry_snapshot_maps_live_feed_agents_and_evidence():
    from types import SimpleNamespace
    from market_config import FRESHNESS
    from telemetry_routes import telemetry_snapshot

    now = time.time()
    epoch = int(now // 60) * 60 - 120
    candles = [
        {'epoch': epoch, 'open': 1.1, 'high': 1.2, 'low': 1.0, 'close': 1.15},
        {'epoch': epoch + 60, 'open': 1.15, 'high': 1.25, 'low': 1.1, 'close': 1.2},
    ]

    class Cursor:
        def __init__(self, rows):
            self.rows = rows

        def sort(self, *_args):
            return self

        def limit(self, *_args):
            return self

        async def to_list(self, _length):
            return self.rows

    class Collection:
        def __init__(self, row=None, rows=None):
            self.row = row
            self.rows = rows or []

        async def find_one(self, *_args, **_kwargs):
            return self.row

        def find(self, *_args, **_kwargs):
            return Cursor(self.rows)

    class Database:
        observer_status = Collection()
        market_analyses = Collection(row={
            'quality': {'score': 96},
            'indicators': {'values': {'atrRegime': 1.1}},
            'signal': {
                'direction': 'CALL', 'confidence': 88,
                'agreeing': ['ema_trend', 'momentum'], 'opposing': [],
                'votes': {
                    'ema_trend': {'direction': 'CALL', 'weight': 1.5},
                    'momentum': {'direction': 'CALL', 'weight': 0.75},
                },
            },
        })
        live_signals = Collection()
        signal_calibration_runs = Collection()

        async def command(self, _name):
            return {'ok': 1}

    class Store:
        db = Database()

        async def resolve(self, _source, _symbol):
            return {
                'symbol': 'R_10', 'latestEpoch': now - 1, 'latestPrice': 1.2,
                'verificationStatus': 'DERIV_PROVIDER_OHLC',
            }

        async def candles(self, *_args, **_kwargs):
            return candles

    registry = SimpleNamespace(agents={}, max_agents=500)
    signals = SimpleNamespace(
        market_registry=registry, master_agent=None,
        active_market_evaluations=2, max_concurrent_markets=8,
    )
    deriv = SimpleNamespace(status=lambda: {'state': 'DATA_RECEIVING'})
    postgres = SimpleNamespace(state='CONNECTED', vector_state='READY')
    deep_models = SimpleNamespace(models={})

    snapshot = asyncio.run(telemetry_snapshot(
        Store(), deriv, None, signals, postgres, deep_models,
        'deriv', 'R_10', '1m',
    ))

    assert snapshot['status'] == 'ONLINE'
    assert snapshot['feed']['gapGate'] == 'PASS'
    assert snapshot['evidence']['direction'] == 'CALL'
    assert snapshot['registry'] == {'active': 0, 'maximum': 500}
    assert snapshot['pool'] == {'active': 2, 'maximum': 8}
    assert [agent['id'] for agent in snapshot['agents']] == [f'A{index}' for index in range(1, 8)]
    assert snapshot['validation']['vectorSearch'] == 'READY'

    async def stale_resolve(_self, _source, _symbol):
        return {
            'symbol': 'R_10', 'latestEpoch': now - FRESHNESS - 1, 'latestPrice': 1.2,
            'verificationStatus': 'DERIV_PROVIDER_OHLC',
        }

    Store.resolve = stale_resolve
    stale_snapshot = asyncio.run(telemetry_snapshot(
        Store(), deriv, None, signals, postgres, deep_models,
        'deriv', 'R_10', '1m',
    ))

    assert stale_snapshot['status'] == 'STALE'
    assert stale_snapshot['modules'][0]['state'] == 'STALE'
    assert stale_snapshot['modules'][3]['state'] == 'ACTIVE'


class TestCoreEndpoints:
    """Health/runtime/public module endpoints."""

    def test_health_endpoint(self, api_client, base_url):
        response = api_client.get(_url(base_url, "/api/health"), timeout=20)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"

    def test_runtime_endpoint(self, api_client, base_url):
        response = api_client.get(_url(base_url, "/api/v1/runtime"), timeout=25)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data.get("providers"), list)
        deriv = next((p for p in data["providers"] if p.get("source") == "deriv"), None)
        assert deriv is not None
        assert isinstance(deriv.get("symbolCount", 0), int)

    def test_runtime_payload_includes_source_selection_without_simulated_metrics(self, api_client, base_url):
        response = api_client.get(_url(base_url, "/api/v1/runtime"), timeout=25)
        assert response.status_code == 200
        data = response.json()

        source_selection = data.get("sourceSelection")
        assert isinstance(source_selection, dict)
        assert source_selection.get("active") in {"deriv", "market-qx-observer-v2", "all"}
        assert isinstance(source_selection.get("available"), list)

        assert "blueprint" not in data
        assert "liveProbability" not in data
        assert "nextSignalWindow" not in data

    def test_modules_and_events(self, api_client, base_url):
        modules = api_client.get(_url(base_url, "/api/v1/modules"), timeout=20)
        events = api_client.get(_url(base_url, "/api/v1/events"), timeout=20)
        assert modules.status_code == 200
        assert events.status_code == 200
        assert isinstance(modules.json().get("items"), list)
        assert isinstance(events.json().get("items"), list)

    def test_observer_download_manifest_origin_permission_and_no_key_leak(self, api_client, base_url, observer_key):
        response = api_client.get(_url(base_url, "/api/v1/observer/download"), timeout=30)
        assert response.status_code == 200
        assert response.content

        archive = zipfile.ZipFile(io.BytesIO(response.content))
        manifest_name = next((n for n in archive.namelist() if n.endswith("manifest.json")), None)
        assert manifest_name is not None
        manifest = json.loads(archive.read(manifest_name).decode("utf-8"))

        expected_origin = urlparse(base_url).scheme + "://" + urlparse(base_url).netloc
        optional = manifest.get("optional_host_permissions", [])
        assert optional == [f"{expected_origin}/*"]
        assert "https://*/*" not in optional

        for name in archive.namelist():
            if name.endswith((".js", ".html", ".json", ".md", ".txt")):
                content = archive.read(name).decode("utf-8", errors="ignore")
                assert observer_key not in content


class TestDerivAndAnalysis:
    """Deriv market state and analysis behavior."""

    def test_instruments_and_source_isolation(self, api_client, base_url):
        deriv_instruments = api_client.get(_url(base_url, "/api/v1/instruments?source=deriv"), timeout=25)
        observer_instruments = api_client.get(
            _url(base_url, "/api/v1/instruments?source=market-qx-observer-v2"), timeout=25
        )
        assert deriv_instruments.status_code == 200
        assert observer_instruments.status_code == 200
        assert isinstance(deriv_instruments.json().get("items"), list)
        assert isinstance(observer_instruments.json().get("items"), list)

    def test_deriv_market_state_contains_no_object_id(self, api_client, base_url):
        response = api_client.get(
            _url(base_url, "/api/v1/market/state?source=deriv&symbol=EUR%2FUSD&timeframe=1m"), timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("source") == "deriv"
        assert "_id" not in str(data)

    def test_analysis_and_latest_no_duplicate_signal_history(self, api_client, base_url, mongo_db):
        payload = {"source": "deriv", "symbol": "EUR/USD", "timeframe": "1m"}
        first = api_client.post(_url(base_url, "/api/v1/analysis"), json=payload, timeout=40)
        second = api_client.post(_url(base_url, "/api/v1/analysis"), json=payload, timeout=40)
        latest = api_client.get(
            _url(base_url, "/api/v1/analysis/latest?source=deriv&symbol=EUR%2FUSD&timeframe=1m"), timeout=25
        )
        history = api_client.get(_url(base_url, "/api/v1/history?limit=200"), timeout=25)

        assert first.status_code == 200
        assert second.status_code == 200
        assert latest.status_code == 200
        assert history.status_code == 200

        latest_data = latest.json()
        assert latest_data.get("signal", {}).get("direction") == "NO_SIGNAL"
        latest_symbol = latest_data.get("symbol")
        assert isinstance(latest_symbol, str) and latest_symbol

        target_epoch = latest_data.get("latestEpoch")
        rows = [
            row
            for row in history.json().get("items", [])
            if row.get("source") == "deriv"
            and row.get("symbol") == latest_symbol
            and row.get("timeframe") == "1m"
            and row.get("candleEpoch") == target_epoch
        ]
        assert len(rows) <= 1

        db_count = mongo_db.signal_history.count_documents(
            {
                "source": "deriv",
                "symbol": latest_symbol,
                "timeframe": "1m",
                "candleEpoch": target_epoch,
            }
        )
        assert db_count <= 1

    def test_top_pairs_and_runtime_diagnostics(self, api_client, base_url):
        top = api_client.get(_url(base_url, "/api/v1/top-pairs"), timeout=25)
        runtime = api_client.get(_url(base_url, "/api/v1/runtime"), timeout=25)
        events = api_client.get(_url(base_url, "/api/v1/events"), timeout=25)

        assert top.status_code == 200
        assert runtime.status_code == 200
        assert isinstance(top.json().get("items"), list)

        runtime_data = runtime.json()
        deriv = next((p for p in runtime_data.get("providers", []) if p.get("source") == "deriv"), {})
        assert deriv.get("symbolCount", 0) >= 0

        if deriv.get("error") == "SUBSCRIPTION_REJECTED":
            assert any("Deriv" in row.get("source", "") for row in events.json().get("items", []))


class TestObservationSecurityAndValidation:
    """Observer auth, validation, idempotency and source isolation checks."""

    def test_observation_check_rejects_missing_or_wrong_key(self, api_client, base_url):
        missing = api_client.get(_url(base_url, "/api/v1/observation/check"), timeout=20)
        wrong = api_client.get(
            _url(base_url, "/api/v1/observation/check"),
            headers={"X-Market-QX-Key": "TESTONLY-wrong-key"},
            timeout=20,
        )
        assert missing.status_code == 401
        assert wrong.status_code == 401

    def test_observation_check_accepts_valid_key(self, api_client, base_url, observer_key):
        response = api_client.get(
            _url(base_url, "/api/v1/observation/check"),
            headers={"X-Market-QX-Key": observer_key},
            timeout=20,
        )
        assert response.status_code == 200
        assert response.json().get("ok") is True

    def test_pairs_ingest_and_idempotent_dedupe(self, api_client, base_url, observer_key):
        sid = _session_id()
        dedupe = _dedupe("pairs")
        payload = {
            "source": "MARKET_QX_BROWSER_OBSERVATION",
            "schema_version": 2,
            "session_id": sid,
            "dedupe_id": dedupe,
            "observationMethod": "visible-dom-only",
            "pairs": [{"symbol": "TESTONLY_EUR/USD", "providerSymbol": "TESTONLY_EUR/USD", "timeframe": "1m"}],
        }
        first = api_client.post(
            _url(base_url, "/api/v1/observation/pairs"),
            json=payload,
            headers=_obs_headers(observer_key),
            timeout=25,
        )
        second = api_client.post(
            _url(base_url, "/api/v1/observation/pairs"),
            json=payload,
            headers=_obs_headers(observer_key),
            timeout=25,
        )
        assert first.status_code == 200
        assert first.json().get("duplicate") is False
        assert second.status_code == 200
        assert second.json().get("duplicate") is True

    def test_tick_validation_nonfinite_nonpositive_and_stale(self, api_client, base_url, observer_key):
        sid = _session_id()
        bad_payloads = [
            {
                "source": "MARKET_QX_BROWSER_OBSERVATION",
                "schema_version": 2,
                "session_id": sid,
                "dedupe_id": _dedupe("tick-zero"),
                "observationMethod": "visible-dom-only",
                "symbol": "TESTONLY_EUR/USD",
                "providerSymbol": "TESTONLY_EUR/USD",
                "price": 0,
                "timestamp": _now_iso(),
                "timeframe": "tick",
            },
            {
                "source": "MARKET_QX_BROWSER_OBSERVATION",
                "schema_version": 2,
                "session_id": sid,
                "dedupe_id": _dedupe("tick-stale"),
                "observationMethod": "visible-dom-only",
                "symbol": "TESTONLY_EUR/USD",
                "providerSymbol": "TESTONLY_EUR/USD",
                "price": 1.12345,
                "timestamp": _now_iso(offset_seconds=-300),
                "timeframe": "tick",
            },
            {
                "source": "MARKET_QX_BROWSER_OBSERVATION",
                "schema_version": 2,
                "session_id": sid,
                "dedupe_id": _dedupe("tick-future"),
                "observationMethod": "visible-dom-only",
                "symbol": "TESTONLY_EUR/USD",
                "providerSymbol": "TESTONLY_EUR/USD",
                "price": 1.12345,
                "timestamp": _now_iso(offset_seconds=10),
                "timeframe": "tick",
            },
        ]
        for payload in bad_payloads:
            response = api_client.post(
                _url(base_url, "/api/v1/observation/tick"),
                json=payload,
                headers=_obs_headers(observer_key),
                timeout=25,
            )
            assert response.status_code == 422

    def test_unmapped_real_market_tick_is_not_accepted(self, api_client, base_url, observer_key):
        sid = _session_id()
        now = int(time.time())
        p1 = {
            "source": "MARKET_QX_BROWSER_OBSERVATION",
            "schema_version": 2,
            "session_id": sid,
            "dedupe_id": _dedupe("tick-now"),
            "observationMethod": "visible-dom-only",
            "symbol": "TESTONLY_ORDER/USD",
            "providerSymbol": "TESTONLY_ORDER/USD",
            "price": 1.2222,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "timeframe": "tick",
        }
        first = api_client.post(
            _url(base_url, "/api/v1/observation/tick"),
            json=p1,
            headers=_obs_headers(observer_key),
            timeout=25,
        )
        assert first.status_code == 503

    def test_unmapped_real_market_event_is_not_accepted(self, api_client, base_url, observer_key):
        sid = _session_id()
        start_epoch, close_epoch = _aligned_candle_bounds(seconds=60, shift_windows=1)
        valid = {
            "source": "MARKET_QX_BROWSER_OBSERVATION",
            "schema_version": 2,
            "session_id": sid,
            "dedupe_id": _dedupe("event-valid"),
            "observationMethod": "visible-dom-only",
            "symbol": "TESTONLY_EVENT/USD",
            "providerSymbol": "TESTONLY_EVENT/USD",
            "timeframe": "1m",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start_epoch)),
            "closeTimestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(close_epoch)),
            "open": 1.2,
            "high": 1.3,
            "low": 1.1,
            "close": 1.25,
            "volume": 10,
        }
        bad = {
            **valid,
            "dedupe_id": _dedupe("event-bad"),
            "high": 1.15,
            "close": 1.22,
        }
        ok = api_client.post(
            _url(base_url, "/api/v1/observation/event"),
            json=valid,
            headers=_obs_headers(observer_key),
            timeout=25,
        )
        reject = api_client.post(
            _url(base_url, "/api/v1/observation/event"),
            json=bad,
            headers=_obs_headers(observer_key),
            timeout=25,
        )
        assert ok.status_code == 503
        assert reject.status_code == 422

    def test_same_logical_pair_regular_vs_otc_isolated(self, api_client, base_url, observer_key):
        sid = _session_id()
        regular = "TESTONLY_EUR/USD"
        otc = "TESTONLY_EUR/USD (OTC)"
        pairs_payload = {
            "source": "MARKET_QX_BROWSER_OBSERVATION",
            "schema_version": 2,
            "session_id": sid,
            "dedupe_id": _dedupe("pair-otc"),
            "observationMethod": "visible-dom-only",
            "pairs": [
                {"symbol": regular, "providerSymbol": regular, "timeframe": "1m"},
                {"symbol": otc, "providerSymbol": otc, "timeframe": "1m"},
            ],
        }
        posted = api_client.post(
            _url(base_url, "/api/v1/observation/pairs"),
            json=pairs_payload,
            headers=_obs_headers(observer_key),
            timeout=25,
        )
        instruments = api_client.get(
            _url(base_url, "/api/v1/instruments?source=market-qx-observer-v2"), timeout=25
        )
        assert posted.status_code == 200
        assert instruments.status_code == 200
        symbols = {row.get("symbol") for row in instruments.json().get("items", [])}
        assert regular in symbols
        assert otc in symbols


class TestMongoLegacyIsolation:
    """Legacy import isolation checks via MongoDB."""

    def test_legacy_counts_and_training_eligibility(self, mongo_db):
        eligible_candles = mongo_db.legacy_candles_unverified.count_documents({"trainingEligible": {"$ne": False}})
        eligible_signals = mongo_db.legacy_signals_unverified.count_documents({"trainingEligible": True})

        assert eligible_candles == 0
        assert eligible_signals == 0
