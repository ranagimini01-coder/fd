import asyncio
import math
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / 'backend' / '.env')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core_pipeline import CorePipeline
from feature_engineering import (
    FeatureEngineeringPipeline,
    compute_indicator_bundle,
    compute_multi_timeframe_features,
)
from master_agent import BASE_WEIGHTS, MasterAgent
from market_agent_registry import MarketAgentRegistry
from market_ml_orchestrator import MarketMLOrchestrator
from pairs_config import get_currently_active_deriv_symbols, is_forex_market_open
from signal_formatter import format_binary_signal
from signal_service import SignalService


class FakeCollection:
    def __init__(self):
        self.update = None

    async def create_index(self, *args, **kwargs):
        return 'created'

    async def update_one(self, selector, update, upsert=False):
        self.update = (selector, update, upsert)
        return SimpleNamespace(modified_count=1)

    async def find_one(self, *args, **kwargs):
        return None


def make_candles(count=80):
    now = time.time()
    start = int(now // 60) * 60 - count * 60
    rows = []
    for index in range(count):
        open_price = 1.1 + index * 0.0002
        close = open_price + 0.00015
        rows.append({
            'epoch': start + index * 60,
            'open': open_price,
            'high': close + 0.00005,
            'low': open_price - 0.00005,
            'close': close,
            'completeness': 'PROVIDER_OHLC',
        })
    return rows, now


class TestMasterAgent(unittest.TestCase):
    def test_weights_wait_for_minimum_evidence_and_stay_bounded(self):
        state = {'families': {'rsi': {'wins': 180, 'total': 200}, 'macd': {'wins': 0, 'total': 200}}}
        weights = MasterAgent.candidate_weights_from_state(state, min_outcomes=200)
        self.assertGreater(weights['rsi'], BASE_WEIGHTS['rsi'])
        self.assertLess(weights['macd'], BASE_WEIGHTS['macd'])
        self.assertEqual(weights['ema_trend'], BASE_WEIGHTS['ema_trend'])
        self.assertLessEqual(max(weights[key] / BASE_WEIGHTS[key] for key in weights), 1.25)
        insufficient = {'families': {'rsi': {'wins': 9, 'total': 10}}}
        candidate = MasterAgent.candidate_weights_from_state(insufficient, min_outcomes=200)
        self.assertEqual(candidate, BASE_WEIGHTS)
        self.assertEqual(MasterAgent.weights_from_state(state, min_outcomes=200), BASE_WEIGHTS)
        approved = {**state, 'validation': {'readyForLive': True, 'datasetVersion': 'oos-v1'}}
        self.assertEqual(MasterAgent.weights_from_state(approved, min_outcomes=200), weights)

    def test_only_verified_deriv_settlements_update_weights(self):
        collection = FakeCollection()
        agent = MasterAgent(SimpleNamespace(agent_weight_states=collection), min_outcomes=1)
        candidate = {
            'source': 'deriv', 'symbol': 'EUR/USD', 'timeframe': '1m',
            'trainingEligible': True, 'inputCompleteness': 'PROVIDER_OHLC',
            'votes': {'ema_trend': {'direction': 'CALL'}, 'rsi': {'direction': 'PUT'}},
        }
        accepted = asyncio.run(agent.record_settlement(candidate, 'WIN', 'UP', 'PROVIDER_OHLC'))
        rejected = asyncio.run(agent.record_settlement(
            {**candidate, 'source': 'market-qx-observer-v2'}, 'WIN', 'UP', 'OBSERVED_UNVERIFIED',
        ))
        self.assertTrue(accepted['learned'])
        self.assertFalse(rejected['learned'])
        increments = collection.update[1]['$inc']
        self.assertEqual(increments['families.ema_trend.wins'], 1)
        self.assertEqual(increments['families.rsi.wins'], 0)

    def test_orchestrator_ranks_top_fifteen_and_selects_unique_top_three(self):
        candidates = []
        for index in range(20):
            candidates.append({
                'instrument': {'source': 'deriv', 'symbol': f'PAIR{index // 2}'},
                'timeframe': '1m', 'entry': 100 + index,
                'assessment': {'direction': 'CALL', 'confidence': 60 + index},
                'qualityScore': 70 + index, 'qualified': True,
            })
        candidates.append({
            'instrument': {'source': 'deriv', 'symbol': 'REJECTED'}, 'timeframe': '1m',
            'entry': 999, 'assessment': {'direction': 'PUT', 'confidence': 99},
            'qualityScore': 100, 'qualified': False,
        })
        result = MasterAgent.orchestrate(candidates)
        self.assertEqual(len(result['top15']), 15)
        self.assertEqual(len(result['selected']), 3)
        self.assertEqual(len({item['instrument']['symbol'] for item in result['selected']}), 3)
        self.assertTrue(all(item['qualified'] for item in result['selected']))


class TestCorePipeline(unittest.TestCase):
    def test_macd_signal_and_histogram_use_the_macd_series(self):
        closes = [100.0 + index * 0.1 + 0.5 * math.sin(index / 3.0) for index in range(80)]
        candles = [
            {
                'open': close - 0.02,
                'high': close + 0.05,
                'low': close - 0.05,
                'close': close,
            }
            for close in closes
        ]

        def ema_series(values, period):
            alpha = 2.0 / (period + 1.0)
            result = [float(values[0])]
            for value in values[1:]:
                result.append(alpha * float(value) + (1.0 - alpha) * result[-1])
            return result

        expected_line = [
            fast - slow
            for fast, slow in zip(ema_series(closes, 12), ema_series(closes, 26))
        ]
        expected_macd = expected_line[-1]
        expected_signal = ema_series(expected_line, 9)[-1]
        features = compute_indicator_bundle(candles)

        self.assertAlmostEqual(features['macd'], expected_macd)
        self.assertAlmostEqual(features['macd_signal'], expected_signal)
        self.assertAlmostEqual(features['macd_hist'], expected_macd - expected_signal)

    def test_registry_retains_only_bounded_active_market_contexts(self):
        registry = MarketAgentRegistry(max_agents=2)
        first = registry.sync_active([
            ('deriv', 'R_10', '1m'),
            ('deriv', 'R_25', '1m'),
        ])
        first[0].attach_features({'momentum': 0.2})

        active = registry.sync_active([
            ('deriv', 'R_10', '1m'),
            ('market-qx-observer-v2', 'EUR/USD', '1m'),
            ('deriv', 'R_50', '5m'),
        ])

        self.assertEqual(len(active), 2)
        self.assertEqual(registry.snapshot()['active_agents'], 2)
        self.assertEqual(
            {(agent.source, agent.symbol, agent.timeframe) for agent in active},
            {('deriv', 'R_10', '1m'), ('market-qx-observer-v2', 'EUR/USD', '1m')},
        )
        self.assertEqual(active[0].snapshot()['feature_summary'], {'momentum': 0.2})

    def test_standard_assessment_loads_higher_timeframe_candles(self):
        candles, now = make_candles()

        class Store:
            db = SimpleNamespace()

            def __init__(self):
                self.timeframes = []

            async def candles(self, source, symbol, timeframe, limit):
                self.timeframes.append(timeframe)
                return candles

        store = Store()
        service = SignalService(store)
        assessment, _reason, _entry = asyncio.run(service.assess(
            {'source': 'deriv', 'symbol': 'R_10'}, '1m', now,
        ))

        self.assertIn('5m', store.timeframes)
        self.assertIsNotNone(assessment['higherTimeframe'])

    def test_live_confidence_uses_only_oos_validated_pair_calibration(self):
        profile = {'agentId': 'specialist_test', 'threshold': 55, 'minAgree': 2, 'maxOppose': 0}
        calibration = {
            'agentId': profile['agentId'], 'readyForLive': True, 'datasetVersion': 'deriv:R_10:1m:oos-1',
            'profile': profile,
            'result': {
                'readyForLive': True, 'status': 'READY',
                'knots': [{'upperBound': 0.82, 'probability': 0.91}],
                'test': {'accuracyLower95': 0.92, 'sampleSize': 200},
            },
        }

        class Cursor:
            def sort(self, *_args):
                return self

            def limit(self, *_args):
                return self

            async def to_list(self, _length):
                return [calibration]

        class Collection:
            def find(self, *_args, **_kwargs):
                return Cursor()

        service = SignalService(SimpleNamespace(db=SimpleNamespace(signal_calibration_runs=Collection())))
        assessment = {
            'direction': 'CALL', 'confidence': 82, 'agreeCount': 4, 'opposeCount': 0,
        }

        calibrated = asyncio.run(service._apply_live_calibration(assessment, 'deriv', 'R_10', '1m'))

        self.assertEqual(calibrated['confidence'], 91.0)
        self.assertEqual(calibrated['rawConfidence'], 82)
        self.assertEqual(calibrated['calibratedProfile'], profile)
        self.assertEqual(calibrated['calibration']['status'], 'OUT_OF_SAMPLE_VALIDATED')

    def test_feature_rows_align_to_their_future_candle_labels(self):
        closes = list(range(1, 21)) + [19, 21, 20]
        candles = [
            {'open': close, 'high': close + 0.1, 'low': close - 0.1, 'close': close}
            for close in closes
        ]
        pipeline = FeatureEngineeringPipeline(sequence_window=20, feature_horizon=1)

        bundle = pipeline.build_bundle(candles, symbol='R_10', timeframe='1m')

        self.assertEqual(bundle['tabular_matrix'].shape[0], 3)
        self.assertEqual(len(bundle['sequence_rows']), 3)
        self.assertEqual(bundle['labels'], [0, 1, 0])

    def test_market_features_encode_regime_tick_activity_and_three_timeframe_alignment(self):
        def rising(count):
            return [
                {
                    'epoch': index * 60, 'open': 100.0 + index,
                    'high': 101.1 + index, 'low': 99.9 + index,
                    'close': 101.0 + index, 'tickVolume': 12,
                }
                for index in range(count)
            ]

        one_minute = rising(30)
        features = compute_indicator_bundle(one_minute)
        aligned = compute_multi_timeframe_features({
            '1m': one_minute, '5m': rising(30), '15m': rising(30),
        })
        conflicting = compute_multi_timeframe_features({
            '1m': one_minute, '5m': rising(30), '15m': list(reversed(rising(30))),
        })

        self.assertEqual(features['trend_regime'], 1.0)
        self.assertEqual(features['volatility_regime_trending'], 1.0)
        self.assertGreater(features['tick_velocity'], 0.0)
        self.assertGreater(features['tick_range_atr'], 0.0)
        self.assertEqual(aligned['multi_timeframe_aligned'], 1.0)
        self.assertEqual(aligned['multi_timeframe_confluence'], 1.0)
        self.assertEqual(conflicting['multi_timeframe_aligned'], 0.0)
        self.assertEqual(FeatureEngineeringPipeline().sequence_window, 200)

    def test_signal_cycle_bounds_parallel_market_evaluations(self):
        service = SignalService(SimpleNamespace(db=SimpleNamespace()), max_concurrent_markets=2)
        service.settings['timeframes'] = ['5m', '10m', '15m', '30m', '1h']
        service.settings['evaluateAfterProgress'] = 0
        service.last_signal_at = time.time()
        active = 0
        peak_active = 0

        async def fresh_instruments():
            return [
                {'source': 'deriv', 'symbol': 'R_10'},
                {'source': 'deriv', 'symbol': 'R_25'},
            ]

        async def assess(instrument, timeframe, now):
            nonlocal active, peak_active
            active += 1
            peak_active = max(peak_active, active)
            await asyncio.sleep(0.005)
            active -= 1
            return {
                'direction': 'NO_SIGNAL', 'confidence': 0,
                'agreeCount': 0, 'opposeCount': 0,
            }, 'NO_SIGNAL', int(now // 60) * 60 + 60

        async def record_candidate(*args, **kwargs):
            return None

        service.fresh_instruments = fresh_instruments
        service.assess = assess
        service.record_candidate = record_candidate

        asyncio.run(service.cycle())

        self.assertLessEqual(peak_active, 2)
        self.assertGreater(peak_active, 1)
        self.assertEqual(service.evaluated_last_cycle, 10)

    def test_market_agents_only_receive_their_own_feature_payload(self):
        candles, _now = make_candles(220)
        orchestrator = MarketMLOrchestrator(max_agents=5)
        orchestrator.registry.register_asset('deriv', 'R_25', '1m')

        result = orchestrator.prepare('deriv', 'R_10', '1m', candles)

        drivers = result['distribution']['drivers']
        self.assertEqual(len(drivers), 1)
        self.assertEqual(drivers[0]['source'], 'deriv')
        self.assertEqual(drivers[0]['symbol'], 'R_10')
        self.assertEqual(drivers[0]['timeframe'], '1m')
        self.assertEqual(result['distribution']['meta']['matched_agents'], 1)

    def test_observation_model_does_not_block_but_live_conflict_vetoes_signal(self):
        baseline = {'direction': 'CALL', 'confidence': 80, 'agreeCount': 3, 'agreeing': ['ema_trend'], 'votes': {}}
        ignored = SignalService._apply_validated_model(
            dict(baseline), {
                'readyForLive': False, 'promotionTier': 'PAPER',
                'direction': 'PUT', 'confidence': 99,
            },
        )
        self.assertEqual(ignored['direction'], 'CALL')
        self.assertEqual(ignored['paperModelPrediction']['promotionTier'], 'PAPER')

        vetoed = SignalService._apply_validated_model(
            dict(baseline), {
                'readyForLive': True, 'promotionTier': 'LIVE', 'passesSignalThreshold': True,
                'direction': 'PUT', 'confidence': 95,
                'model': 'pytorch_lstm', 'modelVersion': 'test-v2',
            },
        )
        self.assertEqual(vetoed['direction'], 'NO_SIGNAL')
        self.assertIn('VALIDATED_MODEL_DIRECTION_CONFLICT', vetoed['vetoes'])

    def test_matching_validated_model_can_only_reduce_confidence(self):
        assessment = {'direction': 'CALL', 'confidence': 82, 'agreeCount': 3, 'agreeing': [], 'votes': {}}

        combined = SignalService._apply_validated_model(
            assessment, {
                'readyForLive': True, 'promotionTier': 'LIVE', 'passesSignalThreshold': True,
                'direction': 'CALL', 'confidence': 95,
                'model': 'pytorch_lstm', 'modelVersion': 'test-v2',
            },
        )

        self.assertEqual(combined['direction'], 'CALL')
        self.assertEqual(combined['confidence'], 82)
        self.assertIn('validated_deep_model', combined['agreeing'])

    def test_live_tier_model_below_sixty_five_percent_is_vetoed(self):
        assessment = {'direction': 'CALL', 'confidence': 95, 'agreeCount': 4, 'agreeing': [], 'votes': {}}
        filtered = SignalService._apply_validated_model(
            assessment,
            {
                'readyForLive': True, 'promotionTier': 'LIVE',
                'passesSignalThreshold': False, 'direction': 'CALL', 'confidence': 64.9,
            },
        )
        self.assertEqual(filtered['direction'], 'NO_SIGNAL')
        self.assertEqual(filtered['reason'], 'MODEL_PROBABILITY_BELOW_LIVE_TIER_THRESHOLD')

    def test_live_model_ensemble_requires_promoted_lstm_xgboost_and_transformer_agreement(self):
        service = SignalService(SimpleNamespace(db=SimpleNamespace()))
        assessment = {
            'direction': 'CALL',
            'confidence': 90,
            'validatedModel': {
                'promotionTier': 'LIVE', 'readyForLive': True,
                'passesSignalThreshold': True, 'direction': 'CALL',
            },
        }
        unavailable = asyncio.run(service._require_live_model_ensemble(
            dict(assessment), 'deriv', 'R_10', '1m', [],
        ))
        self.assertEqual(unavailable['direction'], 'NO_SIGNAL')
        self.assertEqual(unavailable['reason'], 'ENSEMBLE_MODELS_NOT_PROMOTED')

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

        agreed = asyncio.run(service._require_live_model_ensemble(
            dict(assessment), 'deriv', 'R_10', '1m', [],
        ))
        self.assertEqual(agreed['direction'], 'CALL')
        self.assertTrue(agreed['modelEnsemble']['passed'])

        service.model_runner.infer_all = lambda *_args: {
            'predictions': {
                'xgboost': {'direction': 'CALL'},
                'transformer': {'direction': 'PUT'},
            },
        }
        disagreed = asyncio.run(service._require_live_model_ensemble(
            dict(assessment), 'deriv', 'R_10', '1m', [],
        ))
        self.assertEqual(disagreed['direction'], 'NO_SIGNAL')
        self.assertEqual(disagreed['reason'], 'ENSEMBLE_MODEL_DISAGREEMENT')

    def test_execution_eligibility_requires_tier_two_and_never_submits_orders(self):
        signal = {
            'id': 'signal-1', 'source': 'deriv', 'symbol': 'frxEURUSD',
            'timeframe': '1m', 'status': 'PENDING', 'entryEpoch': time.time() + 60,
            'direction': 'CALL',
            'validatedModel': {
                'promotionTier': 'LIVE', 'readyForLive': True,
                'passesSignalThreshold': True, 'confidence': 90, 'direction': 'CALL',
            },
            'modelEnsemble': {
                'passed': True,
                'membersReady': {'lstm': True, 'xgboost': True, 'transformer': True},
                'predictions': {'xgboost': 'CALL', 'transformer': 'CALL'},
            },
        }

        class Collection:
            async def find_one(self, selector, *_args, **_kwargs):
                if selector.get('id') == 'signal-1':
                    return signal
                return None

        service = SignalService(SimpleNamespace(db=SimpleNamespace(
            live_signals=Collection(), signal_market_controls=Collection(),
        )))

        allowed = asyncio.run(service.execution_eligibility('signal-1'))
        signal['validatedModel']['confidence'] = 70
        below_threshold = asyncio.run(service.execution_eligibility('signal-1'))
        signal['validatedModel']['confidence'] = 90
        signal['validatedModel']['promotionTier'] = 'PAPER'
        rejected = asyncio.run(service.execution_eligibility('signal-1'))

        self.assertTrue(allowed['eligible'])
        self.assertFalse(allowed['executionEnabled'])
        self.assertFalse(allowed['submitted'])
        self.assertIn('LIVE_TIER_MODEL_REQUIRED', below_threshold['reasons'])
        self.assertIn('LIVE_TIER_MODEL_REQUIRED', rejected['reasons'])

    def test_gatekeeper_otc_flag_routes_to_observation_only_predictor(self):
        class Predictor:
            def __init__(self):
                self.called = False

            def analyze_sequence(self, candles):
                self.called = True
                self.asserted_count = len(candles)
                return {'direction': 'CALL', 'confidence': 0.88, 'reason': 'OTC synthetic predictor test'}

        candles, now = make_candles()
        for candle in candles:
            candle['completeness'] = 'OBSERVED_UNVERIFIED'
        predictor = Predictor()
        report = CorePipeline(indicator_engine=lambda _: {'values': {}}, otc_predictor=predictor).evaluate(
            'market-qx-observer-v2', 'EUR/USD', '1m', candles, 60, now=now, is_otc=True,
        )
        self.assertTrue(predictor.called)
        self.assertEqual(predictor.asserted_count, len(candles))
        self.assertTrue(report['is_otc'])
        self.assertFalse(report['verified'])
        self.assertFalse(report['dataQuality']['trainingEligible'])
        self.assertEqual(report['signal']['direction'], 'CALL')
        self.assertEqual(report['signal']['confidence'], 88)
        self.assertEqual(report['signal']['model'], 'OTC_TIME_SERIES_OBSERVATION_ONLY')

    def test_signal_service_assesses_gatekeeper_otc_via_forecaster(self):
        candles, now = make_candles()
        for candle in candles:
            candle['completeness'] = 'OBSERVED_UNVERIFIED'

        class Store:
            db = SimpleNamespace()

            async def candles(self, source, symbol, timeframe, limit):
                return candles

        service = SignalService(Store())
        instrument = {
            'source': 'market-qx-observer-v2', 'symbol': 'EUR/USD (OTC)',
            'is_otc': True, 'verificationStatus': 'OTC_OBSERVATION_ONLY',
        }
        assessment, _reason, entry = asyncio.run(service.assess(instrument, '1m', now))
        self.assertEqual(assessment['model'], 'OTC_TIME_SERIES_OBSERVATION_ONLY')
        self.assertTrue(assessment['is_otc'])
        self.assertEqual(assessment['direction'], 'CALL')
        self.assertEqual(entry, int(now // 60) * 60 + 60)


class TestSignalOutput(unittest.TestCase):
    def test_market_hours_gate_real_pairs_but_keep_crypto_open(self):
        saturday = datetime(2026, 9, 26, 12, tzinfo=timezone.utc)
        sunday_before_open = datetime(2026, 9, 27, 21, 59, tzinfo=timezone.utc)
        sunday_open = datetime(2026, 9, 27, 22, 0, tzinfo=timezone.utc)
        friday_close = datetime(2026, 9, 25, 22, 0, tzinfo=timezone.utc)

        self.assertFalse(is_forex_market_open(saturday))
        self.assertFalse(is_forex_market_open(sunday_before_open))
        self.assertTrue(is_forex_market_open(sunday_open))
        self.assertFalse(is_forex_market_open(friday_close))
        self.assertEqual(get_currently_active_deriv_symbols(saturday), ['cryBTCUSD', 'cryETHUSD'])
        self.assertEqual(len(get_currently_active_deriv_symbols(sunday_open)), 39)

    def test_binary_signal_formatter_uses_exact_aligned_utc_entry(self):
        entry = int(datetime(2026, 9, 29, 14, 36, tzinfo=timezone.utc).timestamp())

        formatted = format_binary_signal('frxEURUSD', 'call', 94.6, 1, entry)

        self.assertEqual(formatted['raw_data']['symbol'], 'EUR/USD')
        self.assertEqual(formatted['raw_data']['entry_epoch'], entry)
        self.assertEqual(formatted['raw_data']['entry_time'], '02:36 PM UTC')
        self.assertIn('CONFIDENCE: 95%', formatted['text_payload'])
        self.assertIn('DIRECTION: CALL', formatted['text_payload'])

    def test_otc_candidate_is_not_counted_as_specialist_profiles(self):
        candidates = FakeCollection()
        store = SimpleNamespace(db=SimpleNamespace(signal_research_candidates=candidates))
        service = SignalService(store)
        instrument = {'source': 'market-qx-observer-v2', 'symbol': 'EUR/USD (OTC)', 'is_otc': True}
        assessment = {
            'direction': 'CALL', 'confidence': 88, 'agreeCount': 2, 'opposeCount': 0,
            'agreeing': ['micro_momentum', 'repetitive_action'], 'opposing': [],
            'votes': {'micro_momentum': {'direction': 'CALL'}, 'repetitive_action': {'direction': 'CALL'}},
            'indicators': {}, 'is_otc': True, 'trainingInputCompleteness': 'OBSERVED_UNVERIFIED',
        }
        asyncio.run(service.record_candidate(instrument, '1m', 1800000000, assessment, True, 'QUALIFIED', 'OTC_FORECAST'))
        document = candidates.update[1]['$setOnInsert']
        self.assertEqual(document['agentPoolVersion'], 'otc-time-series-observation-only-v1')
        self.assertEqual(document['agentTrainingMask'], '')
        self.assertEqual(document['qualifiedAgentCount'], 0)
        self.assertFalse(document['trainingEligible'])

    def test_signal_persists_exact_entry_expiry_and_otc_provenance(self):
        class SignalCollection:
            document = None

            async def insert_one(self, document):
                self.document = document

        class Store:
            db = SimpleNamespace(
                live_signals=SignalCollection(),
                signal_history=SignalCollection(),
                binary_signal_decisions=SignalCollection(),
            )

            async def event(self, *args, **kwargs):
                return None

        store = Store()
        service = SignalService(store)
        instrument = {'source': 'market-qx-observer-v2', 'symbol': 'EUR/USD (OTC)', 'is_otc': True}
        assessment = {
            'direction': 'CALL', 'confidence': 88, 'agreeing': ['micro_momentum'],
            'opposing': [], 'votes': {'micro_momentum': {'direction': 'CALL', 'detail': 'test'}},
            'indicators': {}, 'is_otc': True, 'forecast': {'direction': 'CALL', 'confidence': 0.88},
        }
        entry = 1800000000
        emitted = asyncio.run(service.emit(instrument, '1m', entry, assessment, 'OTC_FORECAST'))
        document = store.db.live_signals.document
        self.assertTrue(emitted)
        self.assertEqual(document['entryEpoch'], entry)
        self.assertEqual(document['expiryEpoch'], entry + 60)
        self.assertEqual(document['formattedSignal']['raw_data']['entry_epoch'], entry)
        self.assertEqual(document['formattedSignal']['raw_data']['timeframe'], '1m')
        self.assertIn('ENTRY TIME: 08:00 AM UTC', document['formattedSignal']['text_payload'])
        self.assertEqual(document['verification'], 'OTC_FORECAST_UNVERIFIED')
        self.assertTrue(document['is_otc'])

    def test_stages_run_and_verified_deriv_candles_are_eligible(self):
        candles, now = make_candles()
        pipeline = CorePipeline(
            indicator_engine=lambda _: {'state': 'COMPUTED', 'values': {f'i{i}': float(i) for i in range(53)}},
        )
        report = pipeline.evaluate('deriv', 'EUR/USD', '1m', candles, 60, now=now)
        self.assertEqual(report['indicatorEngine']['indicatorCoverage'], '50_PLUS')
        self.assertTrue(report['dataQuality']['trainingEligible'])
        self.assertEqual(report['pairAndCandleType']['cot'], 'UNAVAILABLE_NO_COT_SOURCE')
        self.assertIn('signal', report)

    def test_unverified_and_invalid_data_fail_closed(self):
        candles, now = make_candles()
        candles[-1]['completeness'] = 'OBSERVED_UNVERIFIED'
        report = CorePipeline(indicator_engine=lambda _: {'values': {}}).evaluate(
            'market-qx-observer-v2', 'EUR/USD (OTC)', '1m', candles, 60, now=now,
        )
        self.assertFalse(report['dataQuality']['trainingEligible'])
        invalid = [dict(candles[-1], high=0)]
        rejected = CorePipeline(indicator_engine=lambda _: {'values': {}}).evaluate(
            'deriv', 'EUR/USD', '1m', invalid, 60, now=now,
        )
        self.assertEqual(rejected['signal']['direction'], 'NO_SIGNAL')

    def test_failed_breakout_is_vetoed(self):
        candles, now = make_candles()
        prior_high = max(row['high'] for row in candles[-21:-1])
        last = candles[-1]
        last.update(open=prior_high - 0.002, high=prior_high + 0.001, low=prior_high - 0.003, close=prior_high - 0.001)
        report = CorePipeline(indicator_engine=lambda _: {'values': {}}).evaluate(
            'deriv', 'EUR/USD', '1m', candles, 60, now=now,
        )
        self.assertTrue(report['behaviourFinder']['falseBreakoutRisk'])
        self.assertIn('FAILED_BREAKOUT_GATE', report['vetoes'])


if __name__ == '__main__':
    unittest.main()
