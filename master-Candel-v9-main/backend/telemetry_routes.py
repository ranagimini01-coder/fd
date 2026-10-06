"""Server-sent telemetry snapshots for the live terminal."""
import asyncio
import json
import time

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from market_config import FRESHNESS, TIMEFRAMES


def _module(module_id, name, state, metrics, summary, *, score=None):
    tone = 'live' if state in {'ONLINE', 'PASS', 'ACTIVE', 'READY', 'VALIDATED'} else 'warn' if state in {'DATA_MISMATCH', 'GAP_DETECTED', 'STALE', 'WARNING'} else 'idle'
    return {
        'id': module_id, 'name': name, 'state': state, 'tone': tone,
        'summary': summary, 'value': metrics[0] if metrics else state,
        'metrics': metrics, 'score': score,
    }


def _agent(agent_id, name, state, score=None, direction='NO_SIGNAL'):
    return {'id': agent_id, 'name': name, 'state': state, 'score': score, 'direction': direction}


async def telemetry_snapshot(store, deriv, market_data, signals, postgres, deep_models, source, symbol, timeframe):
    now = time.time()
    base = {
        'timestamp': now, 'status': 'DISCONNECTED', 'source': source,
        'symbol': symbol, 'timeframe': timeframe, 'price': None,
        'feed': {}, 'registry': {'active': 0, 'maximum': 500},
        'pool': {'active': 0, 'maximum': 0}, 'agents': [],
        'evidence': {'direction': 'NO_SIGNAL', 'confidence': None, 'agreement': 0, 'uncertainty': 'HIGH', 'gate': 'WAITING'},
        'signal': None, 'signals': [], 'validation': {}, 'candles': [], 'modules': [],
        'preSignal': None,
    }
    if timeframe not in TIMEFRAMES:
        return {**base, 'feed': {'error': 'UNSUPPORTED_TIMEFRAME'}}

    pre_signal_reader = getattr(signals, 'current_pre_signal', None)
    if callable(pre_signal_reader):
        base['preSignal'] = pre_signal_reader(source, symbol, timeframe, now)

    try:
        instrument = await store.resolve(source, symbol)
        if instrument is None:
            return {**base, 'feed': {'verification': 'INSTRUMENT_UNAVAILABLE'}}

        resolved_symbol = instrument['symbol']
        candles = await store.candles(source, resolved_symbol, timeframe, limit=300)
        seconds = TIMEFRAMES[timeframe]
        latest_epoch = instrument.get('latestEpoch')
        age_seconds = max(0.0, now - float(latest_epoch)) if latest_epoch is not None else None
        fresh = age_seconds is not None and age_seconds <= FRESHNESS
        gaps = [
            {'fromEpoch': int(left['epoch']), 'toEpoch': int(right['epoch'])}
            for left, right in zip(candles, candles[1:])
            if float(right['epoch']) - float(left['epoch']) > seconds * 1.5
        ]
        recent_gaps = [gap for gap in gaps if gap['toEpoch'] >= now - max(FRESHNESS, seconds * 10)]
        invalid_candles = sum(
            1 for candle in candles
            if not (candle['low'] <= min(candle['open'], candle['close']) <= max(candle['open'], candle['close']) <= candle['high'])
        )
        quality_score = max(0, 100 - len(recent_gaps) * 8 - invalid_candles * 20)
        verification = instrument.get('verificationStatus') or instrument.get('provenance') or 'DERIV_PROVIDER_OHLC'
        otc_observation = verification == 'OTC_OBSERVATION_ONLY'
        mismatch = source == 'market-qx-observer-v2' and verification in {
            'DATA_MISMATCH', 'CROSS_VALIDATION_REJECTED', 'MANIPULATION_VARIANCE_EXCEEDED',
        }
        cross_validation_state = (
            'MISMATCH' if mismatch else 'OTC_OBSERVATION_ONLY' if otc_observation
            else 'VALIDATED' if source == 'deriv' or verification == 'CROSS_VALIDATED'
            else 'PENDING'
        )
        verification_passed = source == 'deriv' or otc_observation or verification == 'CROSS_VALIDATED'

        deriv_status = deriv.status() if deriv is not None else {'state': 'DISABLED'}
        observer_status = await store.db.observer_status.find_one({'id': 'current'}, {'_id': 0})
        if source == 'deriv':
            connected = deriv_status.get('state') in {'CONNECTED', 'DATA_RECEIVING'}
        else:
            observer_age = now - float(observer_status.get('lastReceived', 0)) if observer_status else None
            connected = observer_age is not None and observer_age <= FRESHNESS
        if not connected:
            overall_status = 'DISCONNECTED'
        elif not fresh:
            overall_status = 'STALE'
        elif mismatch:
            overall_status = 'DATA_MISMATCH'
        elif recent_gaps:
            overall_status = 'GAP_DETECTED'
        else:
            overall_status = 'ONLINE'

        analysis = await store.db.market_analyses.find_one(
            {'source': source, 'symbol': resolved_symbol, 'timeframe': timeframe}, {'_id': 0},
        ) or {}
        signal_rows = await store.db.live_signals.find(
            {'source': source, 'symbol': resolved_symbol, 'timeframe': timeframe}, {'_id': 0},
        ).sort('entryEpoch', -1).limit(50).to_list(50)
        signals_for_chart = [
            row for row in signal_rows
            if row.get('direction') in {'CALL', 'PUT'} and row.get('entryEpoch') is not None
        ]
        current_signals = [
            row for row in signals_for_chart
            if row.get('status') == 'PENDING' and float(row.get('expiryEpoch', 0)) >= now
        ]
        current_signal = min(current_signals, key=lambda row: abs(float(row['entryEpoch']) - now)) if current_signals else None
        analysis_signal = analysis.get('signal') or {}
        evidence_signal = current_signal or analysis_signal
        votes = evidence_signal.get('votes') or {}
        agreeing = evidence_signal.get('agreeing') or []
        opposing = evidence_signal.get('opposing') or []
        vote_total = len(agreeing) + len(opposing)
        agreement = len(agreeing) / vote_total if vote_total else 0.0
        direction = evidence_signal.get('direction', 'NO_SIGNAL')
        uncertainty = 'LOW' if agreement >= 0.8 else 'MODERATE' if agreement >= 0.6 else 'HIGH'
        calibrated_profile = (current_signal or {}).get('calibratedProfile') or {}
        quality = analysis.get('quality') or {}
        indicators = analysis.get('indicators') or {}
        indicator_values = indicators.get('values') or indicators
        model_consensus = (current_signal or {}).get('modelConsensus') or {}
        validated_model = (current_signal or {}).get('validatedModel') or {}
        live_model = validated_model if validated_model.get('readyForLive') else model_consensus
        higher = (current_signal or {}).get('higherTimeframe') or {}

        def vote_agent(agent_id, name, key, max_weight):
            vote = votes.get(key) or {}
            score = vote.get('weight')
            normalized = min(100.0, max(0.0, float(score) / max_weight * 100)) if score is not None else None
            state = vote.get('direction', 'WAITING')
            return _agent(agent_id, name, state, normalized, state if state in {'CALL', 'PUT'} else 'NO_SIGNAL')

        agents = [
            _agent('A1', 'Data quality', 'PASS' if quality_score >= 85 and not recent_gaps and not mismatch else 'WARNING', float(quality.get('score', quality_score))),
            vote_agent('A2', 'Trend / structure', 'ema_trend', 1.5),
            vote_agent('A3', 'Momentum', 'momentum', 0.75),
            vote_agent('A4', 'Breakout / mean reversion', 'support_resistance', 0.75),
            _agent('A5', 'Volatility / regime', 'ACTIVE' if indicator_values.get('atrRegime') is not None else 'WAITING', float(indicator_values['atrRegime']) if indicator_values.get('atrRegime') is not None else None),
            _agent('A6', 'Higher-timeframe confirmation', higher.get('direction', 'WAITING'), float(evidence_signal.get('confidence')) if higher.get('direction') else None, higher.get('direction', 'NO_SIGNAL')),
            _agent('A7', 'ML forecaster', 'READY' if live_model else 'WAITING', live_model.get('confidence'), live_model.get('direction', live_model.get('decision', 'NO_SIGNAL'))),
        ]
        registry = signals.market_registry
        pool_active = int(getattr(signals, 'active_market_evaluations', 0))
        weight_report = await signals.master_agent.status(source, resolved_symbol, timeframe) if signals.master_agent else {'weights': {}, 'readyForLive': False}
        live_weights = weight_report.get('weights') or {}
        calibration = None
        if source == 'deriv':
            calibration = await store.db.signal_calibration_runs.find_one(
                {'source': source, 'symbol': resolved_symbol, 'timeframe': timeframe},
                {'_id': 0, 'readyForLive': 1, 'generatedAt': 1, 'datasetVersion': 1, 'result.status': 1},
                sort=[('generatedAt', -1)],
            )
        calibration_status = (calibration or {}).get('result', {}).get('status', 'NOT_READY')
        mongo_state = 'CONNECTED'
        try:
            await store.db.command('ping')
        except Exception:
            mongo_state = 'DISCONNECTED'
        postgres_state = getattr(postgres, 'state', 'DISABLED')
        vector_state = getattr(postgres, 'vector_state', 'DISABLED')
        model_ready = (source, resolved_symbol, timeframe) in getattr(deep_models, 'models', {})
        latest_price = instrument.get('latestPrice')
        feed = {
            'fresh': fresh, 'ageSeconds': age_seconds, 'gapCount': len(gaps),
            'recentGapCount': len(recent_gaps), 'gapGate': 'FAIL' if recent_gaps else 'PASS',
            'qualityScore': quality_score, 'verification': verification,
            'crossValidation': cross_validation_state,
            'price': latest_price,
        }
        evidence = {
            'direction': direction, 'confidence': evidence_signal.get('confidence'),
            'agreement': round(agreement, 4), 'agreeing': agreeing, 'opposing': opposing,
            'uncertainty': uncertainty,
            'gate': 'PASS' if direction in {'CALL', 'PUT'} and uncertainty != 'HIGH' and quality_score >= 85 and overall_status == 'ONLINE' and not mismatch and verification_passed else 'NO_SIGNAL',
            'calibratedWeights': live_weights,
            'calibratedWeightsReady': bool(weight_report.get('readyForLive')),
            'calibrationProfile': calibrated_profile,
        }
        modules = [
            _module('source-sync', 'Data feed & cross validation', overall_status, [f'{source} · {"fresh" if fresh else "stale"}', f'Gap gate · {feed["gapGate"]}', f'Observer · {feed["crossValidation"]}'], 'Provenance and freshness'),
            _module('tick-ingest', 'Registry & parallel pool', 'ACTIVE' if registry.agents else 'WAITING', [f'{len(registry.agents)} / {registry.max_agents} contexts', f'{pool_active} / {signals.max_concurrent_markets} tasks', f'{len(signals.market_registry.agents)} active contexts'], 'Active market workers'),
            _module('observer-bridge', 'Data quality agent', agents[0]['state'], [f'Quality · {quality_score}%', f'{len(candles)} candles', f'{len(recent_gaps)} recent gaps'], 'A1 · Data-quality gate', score=quality_score),
            _module('data-normalize', 'Trend & momentum agents', 'ACTIVE' if len(candles) else 'WAITING', [f'Trend · {agents[1]["state"]}', f'Momentum · {agents[2]["state"]}', f'Structure · {direction}'], 'A2 / A3 · Directional evidence'),
            _module('pattern-scan', 'Breakout & volatility agents', 'ACTIVE' if len(candles) else 'WAITING', [f'Breakout · {agents[3]["state"]}', f'Volatility · {agents[4]["state"]}', f'HTF · {agents[5]["state"]}'], 'A4 / A5 / A6 · Regime checks'),
            _module('quality-gate', 'Evidence & confluence gate', evidence['gate'], [f'Agreement · {agreement:.0%}', f'Uncertainty · {uncertainty}', f'Weights · {"OOS" if evidence["calibratedWeightsReady"] else "baseline"}'], 'Calibrated evidence aggregation', score=agreement * 100),
            _module('behaviour-rank', 'ML forecaster', agents[6]['state'], [f'Model · {agents[6]["state"]}', f'Confidence · {agents[6]["score"] if agents[6]["score"] is not None else "—"}', f'Validated · {model_ready}'], 'A7 · Promoted models only', score=agents[6]['score']),
            _module('model-ensemble', 'Signal & entry epoch', 'ACTIVE' if current_signal else 'WAITING', [f'{direction}', f'Entry · {current_signal.get("entryEpoch") if current_signal else "—"}', f'Expiry · {current_signal.get("expiryEpoch") if current_signal else "—"}'], 'Analytical signal window'),
            _module('master-selection', 'Walk-forward & database validation', 'VALIDATED' if calibration and calibration.get('readyForLive') else 'WAITING', [f'Mongo · {mongo_state}', f'PostgreSQL vectors · {vector_state}', f'OOS calibration · {calibration_status}'], 'Persistence and out-of-sample feedback'),
            _module('signal-output', 'Signal output', direction, [f'{direction}', f'{evidence_signal.get("confidence", "—")}% confidence', f'Entry · {current_signal.get("entryEpoch") if current_signal else "—"}'], 'CALL / PUT / NO_SIGNAL'),
            _module('risk-control', 'Execution policy', 'BLOCKED', ['Execution disabled', 'Analytical only'], 'No automatic trade execution'),
        ]
        return {
            **base, 'timestamp': now, 'status': overall_status, 'symbol': resolved_symbol,
            'price': latest_price, 'feed': feed,
            'registry': {'active': len(registry.agents), 'maximum': registry.max_agents},
            'pool': {'active': pool_active, 'maximum': signals.max_concurrent_markets},
            'agents': agents, 'evidence': evidence,
            'signal': current_signal, 'signals': signals_for_chart,
            'validation': {
                'mongo': mongo_state, 'postgres': postgres_state,
                'vectorSearch': vector_state, 'calibration': calibration,
            },
            'candles': candles, 'modules': modules,
        }
    except Exception as exc:  # noqa: BLE001 - telemetry must degrade without interrupting UI rendering.
        return {**base, 'timestamp': now, 'status': 'DISCONNECTED', 'feed': {'error': type(exc).__name__}}


def telemetry_router(store, deriv, market_data, signals, postgres, deep_models):
    router = APIRouter(prefix='/api/telemetry')

    @router.get('/stream')
    async def stream(
        source: str = Query(..., pattern='^(deriv|market-qx-observer-v2)$'),
        symbol: str = Query(..., min_length=1, max_length=80),
        timeframe: str = Query('1m'),
    ):
        async def events():
            last_pre_signal_id = None
            while True:
                snapshot = await telemetry_snapshot(
                    store, deriv, market_data, signals, postgres, deep_models,
                    source, symbol, timeframe,
                )
                pre_signal = snapshot.get('preSignal')
                if pre_signal and pre_signal.get('id') != last_pre_signal_id:
                    last_pre_signal_id = pre_signal.get('id')
                    yield f'event: PRE_SIGNAL\ndata: {json.dumps(pre_signal, separators=(",", ":"), default=str)}\n\n'
                yield f'event: telemetry\ndata: {json.dumps(snapshot, separators=(",", ":"), default=str)}\n\n'
                await asyncio.sleep(1)

        return StreamingResponse(
            events(), media_type='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
        )

    return router