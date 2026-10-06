"""Signal engine unit tests and live-signal API contract tests."""

from __future__ import annotations

import os
import sys
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('MARKET_TIMEFRAMES', '1s,5s,15s,1m,5m,10m,15m,30m,1h')

from signal_engine import evaluate, qualifies, outcome, market_safety_veto, trend_direction, MIN_CANDLES  # noqa: E402
from signal_service import DEFAULT_SETTINGS, SignalService  # noqa: E402
from ensemble_fusion import EnsembleFusion  # noqa: E402


def _series(seed: int, drift: float, count: int = 120, vol: float = 0.00015):
    rng = np.random.default_rng(seed)
    price, rows = 1.1, []
    for i in range(count):
        o = price
        c = o + drift + rng.normal(0, vol)
        rows.append({'open': o, 'high': max(o, c) + abs(rng.normal(0, 0.0001)), 'low': min(o, c) - abs(rng.normal(0, 0.0001)), 'close': c, 'epoch': i * 60})
        price = c
    return rows


class TestSignalEngine:
    def test_model_bootstrap_prioritizes_live_24_7_markets_and_observes_retry_cooldown(self):
        class Cursor:
            def __init__(self, rows):
                self.rows = rows

            async def to_list(self, _limit):
                return self.rows

        class Instruments:
            def find(self, *_args):
                return Cursor([
                    {'symbol': 'frxEURUSD', 'market': 'forex', 'latestEpoch': 1000},
                    {'symbol': 'R_10', 'market': 'synthetic_index', 'latestEpoch': 900},
                ])

        class TrainingRuns:
            async def find_one(self, query, *_args):
                recent = (query['symbol'], query['timeframe']) == ('R_10', '1m')
                return {'_id': 'recent'} if recent else None

        class CandleCounts:
            def aggregate(self, _pipeline):
                return Cursor([
                    {'_id': 'R_10', 'closedCandles': 200},
                    {'_id': 'frxEURUSD', 'closedCandles': 200},
                ])

        service = SignalService.__new__(SignalService)
        service.db = SimpleNamespace(
            market_instruments=Instruments(), deep_model_training_runs=TrainingRuns(),
            market_candles=CandleCounts(),
        )
        service.deep_model_service = SimpleNamespace(models={}, paper_models={}, MIN_RAW_CANDLES=5000)
        service.settings = {'timeframes': ['1m']}
        service.model_bootstrap_cooldown = 3600

        market = asyncio.run(service._next_model_bootstrap_market(now=1000))

        assert market == ('deriv', 'R_10', '5m')

    def test_default_quality_gates_match_the_ui_defaults(self):
        assert DEFAULT_SETTINGS['threshold'] == 85
        assert DEFAULT_SETTINGS['minAgree'] == 4
        assert DEFAULT_SETTINGS['deepScanFloor'] == 70

    def test_dynamic_threshold_requires_fifty_results_and_recovers(self):
        low = ['WIN'] * 29 + ['LOSS'] * 21
        high = ['WIN'] * 30 + ['LOSS'] * 20
        assert SignalService.adjusted_confidence_threshold(85, low) == 90
        assert SignalService.adjusted_confidence_threshold(85, high) == 85
        assert SignalService.adjusted_confidence_threshold(85, low[:20]) == 85

    def test_bayesian_ensemble_weights_shift_with_verified_model_accuracy(self):
        weights = EnsembleFusion.bayesian_weights({
            'sequence': {'wins': 20, 'losses': 2},
            'tree': {'wins': 2, 'losses': 20},
            'rule': {'wins': 10, 'losses': 10},
        })

        assert sum(weights.values()) == pytest.approx(1.0)
        assert weights['sequence'] > weights['rule'] > weights['tree']

    def test_risk_manager_threshold_and_emit_keep_the_live_gate_at_eighty_five(self):
        service = SignalService(SimpleNamespace(db=SimpleNamespace()))
        service.settings['threshold'] = 70

        assert asyncio.run(service._required_confidence('market-qx-observer-v2', 'EUR/USD', '1m')) == 85
        service._is_blacklisted = AsyncMock(return_value=False)
        emitted = asyncio.run(service.emit(
            {'source': 'market-qx-observer-v2', 'symbol': 'EUR/USD'},
            '1m', 120,
            {'direction': 'CALL', 'confidence': 84},
            'STANDARD',
        ))
        assert emitted is False

    def test_verified_loss_updates_risk_manager_threshold(self):
        controls = SimpleNamespace(
            find_one_and_update=AsyncMock(return_value={}),
            update_one=AsyncMock(),
        )
        service = SignalService(SimpleNamespace(db=SimpleNamespace(signal_market_controls=controls)))
        service._record_online_outcome = AsyncMock()

        asyncio.run(service._record_market_outcome({
            'source': 'deriv', 'symbol': 'EURUSD', 'timeframe': '1m',
            'direction': 'CALL', 'confidence': 90,
            'entryCandleCompleteness': 'PROVIDER_OHLC',
        }, 'LOSS', 100))

        assert service.risk_manager.reward_history[-1]['reward'] == -1.0
        assert service.risk_manager.threshold > 0.85
        loss_threshold = service.risk_manager.threshold
        asyncio.run(service._record_market_outcome({
            'source': 'deriv', 'symbol': 'EURUSD', 'timeframe': '1m',
            'direction': 'CALL', 'confidence': 90,
            'entryCandleCompleteness': 'PROVIDER_OHLC',
        }, 'WIN', 101))
        assert service.risk_manager.reward_history[-1]['reward'] == 1.0
        assert service.risk_manager.threshold < loss_threshold

    def test_settled_model_observation_persists_bayesian_calibrations(self):
        class Observations:
            def __init__(self):
                self.row = {
                    'signalId': 'signal-1', 'status': 'PENDING',
                    'modelProbabilities': {'sequence': 0.8, 'tree': 0.2, 'rule': 0.7},
                    'modelDirections': {'sequence': 'CALL', 'tree': 'PUT', 'rule': 'CALL'},
                }

            async def update_one(self, selector, update, upsert=False):
                if selector.get('status') == 'PENDING' and self.row['status'] != 'PENDING':
                    return SimpleNamespace(modified_count=0)
                if selector.get('status') == 'PENDING' or not self.row:
                    self.row.update(update.get('$set', {}))
                    return SimpleNamespace(modified_count=1)
                return SimpleNamespace(modified_count=0)

            async def find_one(self, _selector, _projection=None):
                return self.row

        class Cursor:
            def __init__(self, rows):
                self.rows = rows

            async def to_list(self, _limit):
                return self.rows

        class Calibrations:
            def __init__(self):
                self.rows = {}

            async def update_one(self, selector, update, upsert=False):
                key = selector['modelName']
                row = self.rows.setdefault(key, dict(selector))
                row.update(update.get('$setOnInsert', {}))
                for field, amount in update.get('$inc', {}).items():
                    row[field] = row.get(field, 0) + amount
                row.update(update.get('$set', {}))
                return SimpleNamespace(modified_count=1)

            def find(self, _selector, _projection=None):
                return Cursor(list(self.rows.values()))

        observations = Observations()
        calibrations = Calibrations()
        service = SignalService(SimpleNamespace(db=SimpleNamespace(
            model_observations=observations,
            calibrations=calibrations,
        )))

        asyncio.run(service._record_model_observation_outcome({
            'id': 'signal-1', 'source': 'deriv', 'symbol': 'R_10', 'timeframe': '1m',
            'direction': 'CALL', 'modelDirections': observations.row['modelDirections'],
            'modelProbabilities': observations.row['modelProbabilities'],
            'entryCandleCompleteness': 'PROVIDER_OHLC',
        }, 'WIN', 120))

        assert observations.row['status'] == 'WIN'
        assert calibrations.rows['sequence']['wins'] == 1
        assert calibrations.rows['tree']['losses'] == 1
        assert calibrations.rows['rule']['weight'] > calibrations.rows['tree']['weight']
        weights = asyncio.run(service._bayesian_model_weights('deriv', 'R_10', '1m'))
        assert weights['sequence'] > weights['tree']

    def test_market_safety_blocks_atr_spikes_and_sideways_low_tick_volume(self):
        candles = [
            {'open': 100.0, 'high': 101.0, 'low': 99.0, 'close': 100.0, 'tickVolume': 10}
            for _ in range(25)
        ]
        candles[-1] = {'open': 100.0, 'high': 120.0, 'low': 80.0, 'close': 100.0, 'tickVolume': 10}
        assert market_safety_veto(candles) == 'ATR_SPIKE'

        sideways = [
            {'open': 100.0, 'high': 100.1, 'low': 99.9, 'close': 100.0, 'tickVolume': 10}
            for _ in range(21)
        ]
        for candle in sideways[-5:]:
            candle['tickVolume'] = 1
        assert market_safety_veto(sideways) == 'SIDEWAYS_LOW_TICK_VOLUME'

    def test_market_safety_blocks_abnormal_bollinger_width_without_atr_spike(self):
        candles = []
        for index in range(50):
            close = 100.0 + (0.1 if index % 2 else -0.1)
            if index >= 47:
                close = 104.0 if index % 2 else 96.0
            candles.append({
                'open': 100.0, 'high': 105.0, 'low': 95.0,
                'close': close, 'tickVolume': 10,
            })

        assert market_safety_veto(candles) == 'BOLLINGER_WIDTH_SPIKE'

    def test_higher_timeframe_trend_uses_ema_direction(self):
        rising = _series(1, 0.0004, count=60)
        falling = _series(2, -0.0004, count=60)

        assert trend_direction(rising) == 'CALL'
        assert trend_direction(falling) == 'PUT'
        assert trend_direction(rising[:20]) is None

    def test_one_minute_signal_is_suppressed_by_conflicting_five_or_fifteen_minute_trend(self):
        assessment = {'direction': 'CALL', 'confidence': 91, 'vetoes': []}

        suppressed = SignalService._apply_multi_timeframe_filter(
            assessment,
            {'5m': 'CALL', '15m': 'PUT'},
        )

        assert suppressed['direction'] == 'NO_SIGNAL'
        assert suppressed['reason'] == 'HIGHER_TIMEFRAME_TRENDS_DISAGREE'

    def test_micro_momentum_confirms_only_fresh_tick_direction(self):
        class Cursor:
            def sort(self, *_args):
                return self

            def limit(self, *_args):
                return self

            async def to_list(self, _length):
                return [
                    {'epoch': 101.0, 'price': 1.1000},
                    {'epoch': 104.0, 'price': 1.1002},
                    {'epoch': 109.0, 'price': 1.1005},
                ]

        class Ticks:
            def find(self, *_args, **_kwargs):
                return Cursor()

        service = SignalService(SimpleNamespace(db=SimpleNamespace(market_ticks=Ticks())))
        confirmed = asyncio.run(service._confirm_micro_momentum(
            'deriv', 'frxEURUSD', 'CALL', 110.0,
        ))
        conflict = asyncio.run(service._confirm_micro_momentum(
            'deriv', 'frxEURUSD', 'PUT', 110.0,
        ))

        assert confirmed['passed'] is True
        assert confirmed['sampleCount'] == 3
        assert confirmed['velocityPerSecond'] > 0
        assert conflict['passed'] is False
        assert conflict['reason'] == 'MICRO_MOMENTUM_CONFLICT'

    def test_insufficient_history_is_no_signal(self):
        result = evaluate(_series(1, 0.0004, count=MIN_CANDLES - 1))
        assert result['direction'] == 'NO_SIGNAL'
        assert result['reason'] == 'INSUFFICIENT_CLOSED_CANDLES'

    def test_strong_uptrend_votes_call(self):
        result = evaluate(_series(1, 0.0004))
        assert result['direction'] == 'CALL'
        assert result['agreeCount'] >= 5
        assert result['opposeCount'] == 0
        assert 50 <= result['confidence'] <= 99

    def test_strong_downtrend_votes_put(self):
        result = evaluate(_series(3, -0.0004))
        assert result['direction'] == 'PUT'
        assert result['agreeCount'] >= 5

    def test_random_walk_does_not_qualify_at_default_threshold(self):
        for seed in range(2, 8):
            result = evaluate(_series(seed, 0.0))
            ok, _ = qualifies(result, 85)
            assert ok is False

    def test_higher_timeframe_conflict_penalises(self):
        base = _series(1, 0.0004)
        higher = _series(3, -0.0004, count=60)
        plain = evaluate(base)
        deep = evaluate(base, higher_timeframe_candles=higher, deep=True)
        assert deep['confidence'] < plain['confidence']
        assert any(p['name'] == 'HIGHER_TIMEFRAME_CONFLICT' for p in deep['penalties'])

    def test_outcome_rules(self):
        assert outcome('CALL', {'open': 1.0, 'close': 1.1}) == 'WIN'
        assert outcome('CALL', {'open': 1.0, 'close': 0.9}) == 'LOSS'
        assert outcome('PUT', {'open': 1.0, 'close': 0.9}) == 'WIN'
        assert outcome('PUT', {'open': 1.0, 'close': 1.0}) == 'TIE'

    def test_candidate_snapshot_preserves_source_and_result_gate(self):
        candidates = SimpleNamespace(update_one=AsyncMock())
        database = SimpleNamespace(signal_research_candidates=candidates)
        service = SignalService(SimpleNamespace(db=database))
        assessment = {
            'direction': 'CALL', 'confidence': 82, 'agreeCount': 4, 'opposeCount': 0,
            'agreeing': ['ema_trend'], 'opposing': [],
            'penalties': [], 'votes': {'ema_trend': {'direction': 'CALL', 'detail': 'rising'}},
            'indicators': {'rsi': 61}, 'higherTimeframe': None,
        }

        asyncio.run(service.record_candidate(
            {'source': 'deriv', 'symbol': 'EURUSD', 'label': 'EUR/USD'},
            '1m', 120, assessment, False, 'BELOW_THRESHOLD', 'STANDARD',
        ))

        selector, update = candidates.update_one.await_args.args
        stored = update['$setOnInsert']
        assert selector == {'source': 'deriv', 'symbol': 'EURUSD', 'timeframe': '1m', 'entryEpoch': 120, 'mode': 'STANDARD'}
        assert stored['qualified'] is False
        assert stored['qualificationReason'] == 'BELOW_THRESHOLD'
        assert stored['provenance'] == 'LIVE_DERIV_PUBLIC'
        assert stored['trainingEligible'] is False
        assert len(stored['agentTrainingMask']) == 500
        assert stored['agentTrainingMask'].count('1') > 0
        assert stored['indicators'] == {'rsi': 61}

    def test_three_consecutive_losses_apply_pair_timeframe_cooldown(self):
        class Controls:
            def __init__(self):
                self.states = {}

            @staticmethod
            def key(selector):
                return tuple(selector[field] for field in ('source', 'symbol', 'timeframe'))

            async def find_one_and_update(self, selector, update, **_kwargs):
                state = self.states.setdefault(self.key(selector), {})
                if '$inc' in update:
                    state['consecutiveLosses'] = state.get('consecutiveLosses', 0) + update['$inc']['consecutiveLosses']
                else:
                    state['consecutiveLosses'] = update['$set']['consecutiveLosses']
                state.update(update.get('$set', {}))
                state.update(update.get('$setOnInsert', {}))
                return dict(state)

            async def update_one(self, selector, update, **_kwargs):
                state = self.states.setdefault(self.key(selector), {})
                state.update(update.get('$set', {}))
                return SimpleNamespace(modified_count=1)

            async def find_one(self, selector, _projection=None):
                state = self.states.get(self.key(selector))
                return dict(state) if state else None

        controls = Controls()
        service = SignalService(SimpleNamespace(db=SimpleNamespace(signal_market_controls=controls)))
        instrument = {'source': 'market-qx-observer-v2', 'symbol': 'EUR/USD', 'timeframe': '1m'}
        service._pre_signals[('market-qx-observer-v2', 'EUR/USD', '1m')] = {'entryEpoch': 200}
        now = 100

        async def apply_losses(count):
            for _ in range(count):
                await service._record_market_outcome(instrument, 'LOSS', now)

        asyncio.run(apply_losses(2))
        symbol_state = controls.states[('market-qx-observer-v2', 'EUR/USD', '*')]
        assert symbol_state['cooldownUntil'] == now + 15 * 60
        assert asyncio.run(service._is_blacklisted('market-qx-observer-v2', 'EUR/USD', '5m', now))

        asyncio.run(apply_losses(1))
        pair_state = controls.states[('market-qx-observer-v2', 'EUR/USD', '1m')]
        assert pair_state['consecutiveLosses'] == 3
        assert pair_state['blacklistedUntil'] == now + 24 * 60 * 60
        assert asyncio.run(service._is_blacklisted('market-qx-observer-v2', 'EUR/USD', '1m', now))
        assert ('market-qx-observer-v2', 'EUR/USD', '1m') not in service._pre_signals

    def test_online_retraining_is_queued_after_fifty_verified_deriv_outcomes(self):
        class Progress:
            def __init__(self):
                self.state = None

            async def update_one(self, _selector, update, upsert=False):
                if self.state is None and upsert:
                    self.state = {}
                if '$setOnInsert' in update and not self.state:
                    self.state.update(update['$setOnInsert'])
                self.state.update(update.get('$set', {}))
                return SimpleNamespace(modified_count=1)

            async def find_one_and_update(self, _selector, update, **_kwargs):
                self.state['verifiedOutcomes'] += update['$inc']['verifiedOutcomes']
                self.state.update(update.get('$set', {}))
                return dict(self.state)

            async def find_one(self, _selector, _projection=None):
                return dict(self.state)

        progress = Progress()
        service = SignalService(SimpleNamespace(db=SimpleNamespace(deep_model_online_progress=progress)))
        service.deep_model_service = SimpleNamespace()
        signal = {
            'source': 'deriv', 'symbol': 'frxEURUSD', 'timeframe': '1m',
            'entryCandleCompleteness': 'PROVIDER_OHLC',
        }

        async def record_outcomes(count):
            for _ in range(count):
                await service._record_online_outcome(signal, 'WIN')

        asyncio.run(record_outcomes(49))
        assert service._online_training_queue.empty()
        asyncio.run(record_outcomes(1))
        assert service._online_training_queue.qsize() == 1
        assert progress.state['trainingStatus'] == 'QUEUED'
        assert progress.state['queuedThrough'] == 50

    def test_pre_signal_requires_fresh_forming_candle_and_emits_once(self, monkeypatch):
        forming = {'epoch': 120, 'completeness': 'PARTIAL_TICK_COVERAGE'}
        database = SimpleNamespace(
            market_candles=SimpleNamespace(find_one=AsyncMock(return_value=forming)),
            market_ticks=SimpleNamespace(count_documents=AsyncMock(return_value=3)),
        )
        service = SignalService(SimpleNamespace(db=database))
        closed = [
            {'epoch': 120 - 60 * (MIN_CANDLES - 1 - index), 'open': 1.0, 'high': 1.1, 'low': 0.9, 'close': 1.0}
            for index in range(MIN_CANDLES - 1)
        ]
        service.closed_candles = AsyncMock(return_value=closed)
        service.db.signal_market_controls = SimpleNamespace(find_one=AsyncMock(return_value=None))
        service.deep_model_service = SimpleNamespace(predict_candles=lambda *_args: {
            'readyForLive': True, 'passesSignalThreshold': True, 'promotionTier': 'LIVE',
            'direction': 'CALL', 'confidence': 95, 'model': 'pytorch_lstm',
            'modelVersion': 'test-v4',
        })
        service.model_runner = SimpleNamespace(models={
            name: SimpleNamespace(state=SimpleNamespace(
                trained=True, metadata={'readyForLive': True},
            ))
            for name in ('xgboost', 'transformer')
        })
        service.model_runner.infer_all = lambda *_args: {
            'predictions': {
                'xgboost': {'direction': 'CALL'},
                'transformer': {'direction': 'CALL'},
            },
        }
        evaluations = []

        def evaluate_forming(candles, weights=None):
            evaluations.append(candles)
            return {'direction': 'CALL', 'confidence': 92, 'agreeCount': 6, 'opposeCount': 0}

        monkeypatch.setattr('signal_service.evaluate', evaluate_forming)
        instrument = {'source': 'deriv', 'symbol': 'frxEURUSD', 'label': 'EUR/USD', 'latestEpoch': 150}
        emitted = asyncio.run(service._maybe_emit_pre_signal(instrument, '1m', 150, 120))

        assert emitted['direction'] == 'CALL'
        assert emitted['setupConfidence'] == 92
        assert emitted['entryEpoch'] == 180
        assert len(evaluations[0]) == MIN_CANDLES
        assert asyncio.run(service._maybe_emit_pre_signal(instrument, '1m', 155, 120)) == emitted
        assert len(evaluations) == 1
        assert service.current_pre_signal('deriv', 'frxEURUSD', '1m', 151)['countdownSeconds'] == 29
        assert service.current_pre_signal('deriv', 'frxEURUSD', '1m', 180) is None

    def test_pre_signal_rejects_confidence_below_ninety(self, monkeypatch):
        forming = {'epoch': 120, 'completeness': 'PARTIAL_TICK_COVERAGE'}
        database = SimpleNamespace(
            market_candles=SimpleNamespace(find_one=AsyncMock(return_value=forming)),
            market_ticks=SimpleNamespace(count_documents=AsyncMock(return_value=3)),
        )
        service = SignalService(SimpleNamespace(db=database))
        closed = [
            {'epoch': 120 - 60 * (MIN_CANDLES - 1 - index), 'open': 1.0, 'high': 1.1, 'low': 0.9, 'close': 1.0}
            for index in range(MIN_CANDLES - 1)
        ]
        service.closed_candles = AsyncMock(return_value=closed)
        service.db.signal_market_controls = SimpleNamespace(find_one=AsyncMock(return_value=None))
        monkeypatch.setattr('signal_service.evaluate', lambda candles, weights=None: {
            'direction': 'PUT', 'confidence': 89, 'agreeCount': 7, 'opposeCount': 0,
        })
        instrument = {'source': 'deriv', 'symbol': 'frxEURUSD', 'latestEpoch': 150}

        assert asyncio.run(service._maybe_emit_pre_signal(instrument, '1m', 150, 120)) is None
        assert service.current_pre_signal('deriv', 'frxEURUSD', '1m', 150) is None

    def test_pre_signal_rejects_insufficient_tick_density(self, monkeypatch):
        forming = {'epoch': 120, 'completeness': 'PARTIAL_TICK_COVERAGE'}
        database = SimpleNamespace(
            market_candles=SimpleNamespace(find_one=AsyncMock(return_value=forming)),
            market_ticks=SimpleNamespace(count_documents=AsyncMock(return_value=2)),
        )
        service = SignalService(SimpleNamespace(db=database))
        service.db.signal_market_controls = SimpleNamespace(find_one=AsyncMock(return_value=None))
        monkeypatch.setattr('signal_service.evaluate', lambda *_args, **_kwargs: pytest.fail('evaluation must be skipped'))
        instrument = {'source': 'deriv', 'symbol': 'frxEURUSD', 'latestEpoch': 150}

        assert asyncio.run(service._maybe_emit_pre_signal(instrument, '1m', 150, 120)) is None


class TestSignalApi:
    def test_settings_roundtrip_and_validation(self, api_client, base_url):
        operator_key = os.environ.get('TEST_PROVIDER_CONTROL_KEY')
        if not operator_key:
            pytest.skip('TEST_PROVIDER_CONTROL_KEY missing; operator mutation API is protected')
        headers = {'X-Provider-Control-Key': operator_key}
        current = api_client.get(f'{base_url}/api/v1/signals/settings', timeout=20)
        assert current.status_code == 200
        original = current.json()['settings']['threshold']
        updated = api_client.post(f'{base_url}/api/v1/signals/settings', json={'threshold': 88}, headers=headers, timeout=20)
        assert updated.status_code == 200 and updated.json()['settings']['threshold'] == 88
        assert api_client.post(f'{base_url}/api/v1/signals/settings', json={'threshold': 20}, headers=headers, timeout=20).status_code == 422
        assert api_client.post(f'{base_url}/api/v1/signals/settings', json={'timeframes': ['2m']}, headers=headers, timeout=20).status_code == 422
        assert api_client.post(f'{base_url}/api/v1/signals/settings', json={}, headers=headers, timeout=20).status_code == 422
        restore = api_client.post(f'{base_url}/api/v1/signals/settings', json={'threshold': original}, headers=headers, timeout=20)
        assert restore.status_code == 200 and restore.json()['settings']['threshold'] == original

    def test_live_stats_history_shapes(self, api_client, base_url):
        live = api_client.get(f'{base_url}/api/v1/signals/live?source=all&limit=10', timeout=20)
        assert live.status_code == 200
        body = live.json()
        assert isinstance(body['upcoming'], list) and isinstance(body['recent'], list)
        assert 'engine' in body and 'settings' in body['engine']
        for signal in body['upcoming']:
            assert signal['direction'] in ('CALL', 'PUT')
            assert signal['expiryEpoch'] == signal['entryEpoch'] + signal['timeframeSeconds']
            assert signal['entryEpoch'] % signal['timeframeSeconds'] == 0
        stats = api_client.get(f'{base_url}/api/v1/signals/stats?hours=24', timeout=20)
        assert stats.status_code == 200
        assert stats.json()['measurement'] == 'ENTRY_CANDLE_OPEN_VS_CLOSE'
        assert api_client.get(f'{base_url}/api/v1/signals/history?limit=5&status=WIN', timeout=20).status_code == 200
        assert api_client.get(f'{base_url}/api/v1/signals/live?source=bogus', timeout=20).status_code == 422

    def test_check_reports_observer_and_engine(self, api_client, base_url):
        response = api_client.get(f'{base_url}/api/v1/signals/check', timeout=120)
        assert response.status_code == 200
        body = response.json()
        assert body['verdict'] in ('NOT_CONNECTED', 'RECEIVING', 'STALE', 'RECEIVING_WARMING_UP', 'RECEIVING_SIGNALS_ACTIVE')
        assert body['connectionStatus'] in ('NOT_CONNECTED', 'CONNECTED')
        assert 'market-qx-observer-v2' in body['sources'] and 'deriv' in body['sources']
        assert body['engine']['settings']['threshold'] >= 55
        if not any(source['signalsLastHour'] for source in body['sources'].values()):
            assert body['verdict'] != 'RECEIVING_SIGNALS_ACTIVE'
