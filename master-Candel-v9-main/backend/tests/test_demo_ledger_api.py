"""Demo ledger API regression tests for session, funds, trades, history and isolation."""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import requests


def _url(base_url: str, path: str) -> str:
    return f"{base_url}{path}"


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _open_demo(s: requests.Session, base_url: str) -> dict:
    response = s.post(_url(base_url, "/api/v1/demo/session"), timeout=20)
    assert response.status_code == 200
    body = response.json()
    assert body["balanceCents"] == 1_000_000
    assert isinstance(body["trades"], list)
    return body


def _action(s: requests.Session, base_url: str, payload: dict):
    return s.post(_url(base_url, "/api/v1/demo/actions"), json=payload, timeout=20)


class TestDemoLedgerApi:
    """Server-owned virtual ledger behavior and constraints."""

    def test_session_bootstrap_and_cookie(self, base_url):
        s = _session()
        body = _open_demo(s, base_url)
        assert body["mode"] == "SIMULATED"
        assert "mc_demo_session" in s.cookies.get_dict()

    def test_unauthorized_account_rejected(self, base_url):
        s = _session()
        response = s.get(_url(base_url, "/api/v1/demo/account"), timeout=20)
        assert response.status_code == 401

    def test_deposit_withdraw_and_bounds(self, base_url):
        s = _session()
        _open_demo(s, base_url)

        add = _action(
            s,
            base_url,
            {"requestId": str(uuid.uuid4()), "kind": "deposit", "cents": 500},
        )
        assert add.status_code == 200
        assert add.json()["balanceCents"] == 1_000_500

        remove = _action(
            s,
            base_url,
            {"requestId": str(uuid.uuid4()), "kind": "withdraw", "cents": 200},
        )
        assert remove.status_code == 200
        assert remove.json()["balanceCents"] == 1_000_300

        low = _action(
            s,
            base_url,
            {"requestId": str(uuid.uuid4()), "kind": "deposit", "cents": 99},
        )
        assert low.status_code == 422

        too_much = _action(
            s,
            base_url,
            {"requestId": str(uuid.uuid4()), "kind": "withdraw", "cents": 2_000_000},
        )
        assert too_much.status_code == 409

    def test_invalid_trade_payloads_unknown_market_and_min_stake(self, base_url):
        s = _session()
        _open_demo(s, base_url)

        unknown = _action(
            s,
            base_url,
            {
                "requestId": str(uuid.uuid4()),
                "kind": "place",
                "pairId": "missing-pair",
                "direction": "UP",
                "stakeCents": 100,
                "duration": 5,
                "pending": False,
            },
        )
        assert unknown.status_code == 422

        low_stake = _action(
            s,
            base_url,
            {
                "requestId": str(uuid.uuid4()),
                "kind": "place",
                "pairId": "eur-usd-regular",
                "direction": "DOWN",
                "stakeCents": 99,
                "duration": 5,
                "pending": False,
            },
        )
        assert low_stake.status_code == 422

    def test_5s_trade_completes_and_balance_persists(self, base_url):
        s = _session()
        _open_demo(s, base_url)

        opened = _action(
            s,
            base_url,
            {
                "requestId": str(uuid.uuid4()),
                "kind": "place",
                "pairId": "eur-usd-regular",
                "direction": "UP",
                "stakeCents": 100,
                "duration": 5,
                "pending": False,
            },
        )
        assert opened.status_code == 200
        trade_id = opened.json()["trades"][0]["id"]

        completed = None
        for _ in range(8):
            time.sleep(1.2)
            account = s.get(_url(base_url, "/api/v1/demo/account"), timeout=20)
            assert account.status_code == 200
            trades = account.json()["trades"]
            row = next((t for t in trades if t["id"] == trade_id), None)
            if row and row["status"] in {"WON", "LOST", "TIED"}:
                completed = row
                break
        assert completed is not None

        # Reload persistence with same cookie copied to another client
        copy_client = _session()
        copy_client.cookies.set("mc_demo_session", s.cookies.get("mc_demo_session"), path="/api/v1/demo")
        reload_account = copy_client.get(_url(base_url, "/api/v1/demo/account"), timeout=20)
        assert reload_account.status_code == 200
        assert reload_account.json()["balanceCents"] >= 0

    def test_pending_trade_starts_next_minute(self, base_url):
        s = _session()
        _open_demo(s, base_url)
        response = _action(
            s,
            base_url,
            {
                "requestId": str(uuid.uuid4()),
                "kind": "place",
                "pairId": "eur-usd-regular",
                "direction": "UP",
                "stakeCents": 100,
                "duration": 5,
                "pending": True,
            },
        )
        assert response.status_code == 200
        trade = response.json()["trades"][0]
        assert trade["status"] == "PENDING"
        assert trade["startsAt"] % 60000 == 0
        assert trade["startsAt"] > trade["createdAt"]

    def test_max_20_active_trades_enforced(self, base_url):
        s = _session()
        _open_demo(s, base_url)

        for _ in range(20):
            response = _action(
                s,
                base_url,
                {
                    "requestId": str(uuid.uuid4()),
                    "kind": "place",
                    "pairId": "eur-usd-regular",
                    "direction": "UP",
                    "stakeCents": 100,
                    "duration": 5,
                    "pending": True,
                },
            )
            assert response.status_code == 200

        blocked = _action(
            s,
            base_url,
            {
                "requestId": str(uuid.uuid4()),
                "kind": "place",
                "pairId": "eur-usd-regular",
                "direction": "DOWN",
                "stakeCents": 100,
                "duration": 5,
                "pending": True,
            },
        )
        assert blocked.status_code == 409

    def test_request_id_idempotency(self, base_url):
        s = _session()
        _open_demo(s, base_url)
        req = str(uuid.uuid4())
        payload = {"requestId": req, "kind": "deposit", "cents": 500}

        first = _action(s, base_url, payload)
        second = _action(s, base_url, payload)
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["balanceCents"] == second.json()["balanceCents"]
        assert "already" in second.json().get("message", "").lower()

    def test_session_isolation_between_browsers(self, base_url):
        s1 = _session()
        s2 = _session()
        _open_demo(s1, base_url)
        _open_demo(s2, base_url)

        changed = _action(
            s1,
            base_url,
            {"requestId": str(uuid.uuid4()), "kind": "deposit", "cents": 1200},
        )
        assert changed.status_code == 200

        account2 = s2.get(_url(base_url, "/api/v1/demo/account"), timeout=20)
        assert account2.status_code == 200
        assert account2.json()["balanceCents"] == 1_000_000

    def test_concurrent_withdraw_balance_safety(self, base_url):
        seed = _session()
        _open_demo(seed, base_url)
        token = seed.cookies.get("mc_demo_session")
        assert token

        lock = threading.Lock()

        def run_withdraw() -> int:
            local = _session()
            local.cookies.set("mc_demo_session", token, path="/api/v1/demo")
            response = _action(
                local,
                base_url,
                {"requestId": str(uuid.uuid4()), "kind": "withdraw", "cents": 700_000},
            )
            with lock:
                return response.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda _: run_withdraw(), [1, 2]))

        assert statuses.count(200) == 1
        assert statuses.count(409) == 1

        final_state = seed.get(_url(base_url, "/api/v1/demo/account"), timeout=20)
        assert final_state.status_code == 200
        assert final_state.json()["balanceCents"] == 300_000

    def test_reset_archives_history_and_restores_default_balance(self, base_url):
        s = _session()
        _open_demo(s, base_url)

        open_trade = _action(
            s,
            base_url,
            {
                "requestId": str(uuid.uuid4()),
                "kind": "place",
                "pairId": "eur-usd-regular",
                "direction": "UP",
                "stakeCents": 100,
                "duration": 5,
                "pending": True,
            },
        )
        assert open_trade.status_code == 200

        reset = _action(s, base_url, {"requestId": str(uuid.uuid4()), "kind": "reset"})
        assert reset.status_code == 200
        reset_body = reset.json()
        assert reset_body["balanceCents"] == 1_000_000
        assert reset_body["trades"] == []

        history = s.get(_url(base_url, "/api/v1/demo/history"), timeout=20)
        assert history.status_code == 200
        items = history.json()["items"]
        assert len(items) >= 1
        assert any(item["status"] in {"CANCELLED", "PENDING", "OPEN", "WON", "LOST", "TIED"} for item in items)
