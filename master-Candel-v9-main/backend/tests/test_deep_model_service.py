import asyncio
import sys
import unittest
from pathlib import Path

import numpy as np
import torch
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / 'backend' / '.env', override=True)
sys.path.insert(0, str(ROOT / 'backend'))

from deep_model_service import DeepModelService, _CandlestickSequenceModel
from deriv_service import DERIV_USER_AGENT, websocket_user_agent_options
from feature_engineering import _stochastic, compute_indicator_bundle
from ml_model_adapters import Step8ModelRunner, _sigmoid, ml_router


class TestDeepModelService(unittest.TestCase):
    def test_legacy_model_sigmoid_is_finite_for_extreme_logits(self):
        self.assertEqual(_sigmoid(-1e6), 1.0 / (1.0 + np.exp(40.0)))
        self.assertEqual(_sigmoid(1e6), 1.0 / (1.0 + np.exp(-40.0)))

    def test_deriv_websocket_user_agent_uses_installed_client_api(self):
        options = websocket_user_agent_options()

        self.assertIn(options, (
            {'user_agent_header': DERIV_USER_AGENT},
            {'additional_headers': {'User-Agent': DERIV_USER_AGENT}},
            {'extra_headers': {'User-Agent': DERIV_USER_AGENT}},
        ))

    def test_stochastic_handles_backfilled_history_without_recursion(self):
        closes = [100.0 + index * 0.01 for index in range(3000)]
        highs = [close + 0.02 for close in closes]
        lows = [close - 0.02 for close in closes]

        current_k, current_d = _stochastic(highs, lows, closes)

        self.assertTrue(np.isfinite(current_k))
        self.assertTrue(np.isfinite(current_d))
        self.assertGreaterEqual(current_k, 0.0)
        self.assertLessEqual(current_k, 100.0)
    def test_insufficient_history_uses_bounded_provider_backfill(self):
        class Cursor:
            def sort(self, *args, **kwargs):
                return self

            def limit(self, *args, **kwargs):
                return self

            async def to_list(self, length):
                return []

        class Collection:
            def __init__(self):
                self.inserted = None

            def find(self, *args, **kwargs):
                return Cursor()

            async def insert_one(self, document):
                self.inserted = document

        class Database:
            def __init__(self):
                self.market_candles = Collection()
                self.deep_model_registry = Collection()
                self.deep_model_training_runs = Collection()

        class DerivHistory:
            def __init__(self):
                self.request = None

            async def history(self, symbol, timeframe, count, force):
                self.request = (symbol, timeframe, count, force)

        database = Database()
        deriv = DerivHistory()
        service = DeepModelService(database, deriv)
        service._training_samples = lambda *args: (np.empty((0, 0)), np.empty((0,), dtype=int), [])
        service._fit_and_evaluate = lambda *args: {
            'status': 'NOT_READY', 'reason': 'INSUFFICIENT_PURGED_CHRONOLOGICAL_SAMPLES',
        }

        report = asyncio.run(service.train_market('deriv', 'R_10', '1m'))

        self.assertEqual(deriv.request, ('R_10', '1m', DeepModelService.BACKFILL_CANDLES, True))
        self.assertEqual(report['status'], 'NOT_READY')
        self.assertEqual(report['backfill']['status'], 'INSUFFICIENT_PROVIDER_HISTORY')
        self.assertFalse(service.models)

    def test_observer_data_is_never_eligible_for_live_model_training(self):
        report = asyncio.run(DeepModelService(None).train_market('market-qx-observer-v2', 'R_10', '1m'))

        self.assertEqual(report['status'], 'NOT_READY')
        self.assertEqual(report['reason'], 'VERIFIED_DERIV_SOURCE_REQUIRED')

    def test_step8_inference_fails_closed_when_history_has_no_model_samples(self):
        candles = [
            {
                'source': 'deriv', 'symbol': 'R_10', 'timeframe': '1m',
                'epoch': index * 60, 'open': 100 + index, 'high': 101 + index,
                'low': 99 + index, 'close': 100.5 + index,
            }
            for index in range(200)
        ]

        result = Step8ModelRunner(max_agents=2).infer_all(
            'deriv', 'R_10', '1m', candles,
        )

        self.assertFalse(result['readyForLive'])
        self.assertEqual(result['reason'], 'INSUFFICIENT_HISTORY_FOR_MODEL_INPUT')
        self.assertEqual(result['decision'], 'NO_SIGNAL')
        self.assertEqual(result['predictions'], {})

    def test_step8_training_uses_targets_aligned_with_sequence_windows(self):
        class Model:
            def __init__(self):
                self.targets = None

            def fit(self, _features, targets):
                self.targets = np.asarray(targets).tolist()
                return {'status': 'trained'}

        runner = Step8ModelRunner(max_agents=2)
        models = {name: Model() for name in runner.models}
        runner.models = models
        sequence_features = np.asarray([[1.0], [2.0]])
        all_features = np.asarray([[1.0], [2.0], [3.0], [4.0]])
        labels = [0, 1, 1, 0]
        prepared = {
            'feature_bundle': {
                'targets': {'lstm': labels, 'marl': labels},
                'metadata': {'ml_ready': True},
                'feature_key': 'deriv:R_10:1m:4',
            },
            'model_inputs': {
                'lstm': sequence_features,
                'transformer': sequence_features,
                'xgboost': all_features,
                'lightgbm': all_features,
                'catboost': all_features,
                'random_forest': all_features,
                'marl': {'state': sequence_features},
            },
        }
        runner.prepare_market = lambda *_args: prepared

        report = runner.train_all('deriv', 'R_10', '1m', [{}] * 4)

        self.assertEqual(report['status'], 'TRAINED')
        self.assertEqual(models['lstm'].targets, [1, 0])
        self.assertEqual(models['transformer'].targets, [1, 0])
        self.assertEqual(models['marl'].targets, [1, 0])
        self.assertEqual(models['xgboost'].targets, labels)
        self.assertEqual(report['training_record']['samples'], len(labels))
        self.assertEqual(runner.active_training, {})

    def test_training_samples_align_next_close_and_exclude_flat_outcomes(self):
        prices = [100 + index * 0.1 for index in range(260)]
        candles = []
        for index, close in enumerate(prices):
            candles.append({
                'source': 'deriv', 'symbol': 'R_10', 'timeframe': '1m',
                'epoch': index * 60, 'open': close - 0.05, 'high': close + 0.1,
                'low': close - 0.1, 'close': close, 'completeness': 'PROVIDER_OHLC',
                'tickVolume': index % 7,
            })
        candles.extend([
            {
                'source': 'deriv', 'symbol': 'R_10', 'timeframe': '1m',
                'epoch': 260 * 60, 'open': prices[-1], 'high': prices[-1] + 0.2,
                'low': prices[-1] - 0.1, 'close': prices[-1] + 0.1,
                'completeness': 'PROVIDER_OHLC', 'tickVolume': 4,
            },
            {
                'source': 'deriv', 'symbol': 'R_10', 'timeframe': '1m',
                'epoch': 261 * 60, 'open': prices[-1] + 0.1, 'high': prices[-1] + 0.2,
                'low': prices[-1] - 0.1, 'close': prices[-1] - 0.1,
                'completeness': 'PROVIDER_OHLC',
            },
        ])

        service = DeepModelService(None)
        boundary_features, boundary_labels, _ = service._training_samples(
            candles[:260], 'deriv', 'R_10', '1m',
        )
        features, labels, names = service._training_samples(candles, 'deriv', 'R_10', '1m')

        self.assertEqual(boundary_features.shape, (1, 200, len(names)))
        self.assertEqual(boundary_labels.tolist(), [1])
        self.assertEqual(features.shape, (3, 200, len(names)))
        self.assertEqual(labels.tolist(), [1, 1, 0])
        self.assertIn('tick_volume_available', names)
        self.assertIn('volatility_regime_trending', names)
        self.assertIn('tick_velocity', names)
        self.assertEqual(features[0, -1, names.index('tick_volume_available')], 1.0)
        self.assertEqual(features[1, -1, names.index('tick_volume_available')], 1.0)
        self.assertEqual(
            DeepModelService._feature_rows(candles)[-1, names.index('tick_volume_available')],
            0.0,
        )

    def test_chronological_splits_purge_full_feature_lookback(self):
        purge = DeepModelService.SEQUENCE_WINDOW + DeepModelService.FEATURE_CONTEXT - 1
        train, validation, calibration, calibration_check, test = DeepModelService._split_indices(4000, purge=purge)

        self.assertEqual(train, (0, 2200))
        self.assertEqual(validation, (2459, 2600))
        self.assertEqual(calibration, (2859, 3000))
        self.assertEqual(calibration_check, (3259, 3400))
        self.assertEqual(test, (3659, 4000))
        self.assertGreaterEqual(validation[0] - train[1], purge)
        self.assertGreaterEqual(calibration[0] - validation[1], purge)
        self.assertGreaterEqual(calibration_check[0] - calibration[1], purge)
        self.assertGreaterEqual(test[0] - calibration_check[1], purge)

    def test_insufficient_samples_never_promote_a_model(self):
        report = DeepModelService(None)._fit_and_evaluate(
            np.ones((100, 4), dtype=float), np.zeros(100, dtype=int), ['a', 'b', 'c', 'd'],
        )

        self.assertEqual(report['status'], 'NOT_READY')
        self.assertNotIn('artifact', report)

    def test_tiered_gate_uses_assumed_payout_and_chronological_win_rate(self):
        tier, ev = DeepModelService._promotion_tier(0.58)
        self.assertEqual(tier, 'PAPER')
        self.assertAlmostEqual(ev, 0.044)
        tier, ev = DeepModelService._promotion_tier(0.65)
        self.assertEqual(tier, 'PAPER')
        self.assertAlmostEqual(ev, 0.17)
        tier, ev = DeepModelService._promotion_tier(0.80)
        self.assertEqual(tier, 'LIVE')
        self.assertAlmostEqual(ev, 0.44)
        tier, ev = DeepModelService._promotion_tier(0.80, calibration_pass=False)
        self.assertEqual(tier, 'PAPER')
        self.assertAlmostEqual(ev, 0.44)
        self.assertEqual(DeepModelService.MIN_LIVE_PROBABILITY, 0.85)
        tier, ev = DeepModelService._promotion_tier(0.55)
        self.assertIsNone(tier)
        self.assertLess(ev, 0)

    def test_paper_fallback_keeps_live_calibration_gate_separate(self):
        paper, _ = DeepModelService._promotion_tier(0.58, calibration_pass=False)
        live, _ = DeepModelService._promotion_tier(0.80, calibration_pass=True)

        self.assertEqual(paper, 'PAPER')
        self.assertEqual(live, 'LIVE')
        self.assertGreater(
            DeepModelService.MIN_LIVE_PROBABILITY,
            DeepModelService.OBSERVATION_MIN_WIN_RATE,
        )

    def test_failed_refresh_does_not_remove_a_previously_promoted_model(self):
        class Cursor:
            def sort(self, *_args):
                return self

            def limit(self, *_args):
                return self

            async def to_list(self, _limit):
                return []

        class Collection:
            def __init__(self):
                self.inserted = []
                self.updates = []

            def find(self, *_args):
                return Cursor()

            async def insert_one(self, document):
                self.inserted.append(document)

            async def update_one(self, *args, **kwargs):
                self.updates.append((args, kwargs))

        class Database:
            def __init__(self):
                self.market_candles = Collection()
                self.deep_model_training_runs = Collection()
                self.deep_model_registry = Collection()

        database = Database()
        service = DeepModelService(database)
        existing = {'model': 'pytorch_lstm', 'version': DeepModelService.MODEL_VERSION}
        key = ('deriv', 'R_10', '1m')
        service.models[key] = existing
        service._training_samples = lambda *_args: (
            np.empty((0, 1, 1)), np.empty((0,), dtype=int), ['feature'],
        )
        service._fit_and_evaluate = lambda *_args: {
            'status': 'BELOW_TIER_GATES',
            'sampleCounts': {'test': DeepModelService.MIN_TEST_SAMPLES},
        }

        report = asyncio.run(service.train_market(*key))

        self.assertEqual(report['registryAction'], 'RETAINED_PREVIOUS_PROMOTED_MODEL')
        self.assertIs(service.models[key], existing)
        self.assertEqual(database.deep_model_registry.updates, [])
        self.assertEqual(len(database.deep_model_training_runs.inserted), 1)

    def test_trains_baseline_and_mlp_with_held_out_metrics(self):
        rng = np.random.default_rng(2026)
        features = rng.normal(size=(4000, 4))
        labels = (features[:, 0] + 0.15 * features[:, 1] > 0).astype(int)

        report = DeepModelService(None)._fit_and_evaluate(
            features, labels, ['trend', 'momentum', 'range', 'volatility'],
        )

        self.assertIn(report['status'], {'PAPER_READY', 'LIVE_READY', 'BELOW_TIER_GATES'})
        self.assertIn('pytorch_lstm', report['candidateModels'])
        self.assertEqual(report['sampleCounts']['purgeSamples'], 259)
        self.assertIn('accuracyLower95', report['test'])
        self.assertEqual(report['payoutAssumption']['netPayoutOnWin'], 0.80)
        if report['status'] in {'PAPER_READY', 'LIVE_READY'}:
            self.assertIn('artifact', report)
            self.assertEqual(report['artifact']['version'], DeepModelService.MODEL_VERSION)
        else:
            self.assertNotIn('artifact', report)

    def test_live_prediction_requires_a_promoted_deriv_artifact(self):
        candles = [
            {
                'open': 100 + index, 'high': 101 + index, 'low': 99 + index,
                'close': 100.5 + index, 'epoch': index * 60,
                'completeness': 'PROVIDER_OHLC',
            }
            for index in range(DeepModelService.SEQUENCE_WINDOW + DeepModelService.FEATURE_CONTEXT - 1)
        ]
        names = list(DeepModelService.FEATURE_NAMES)
        service = DeepModelService(None)
        model = _CandlestickSequenceModel(len(names))
        with torch.no_grad():
            for parameter in model.parameters():
                parameter.zero_()
            model.head[-1].bias.fill_(6.0)
        service.models[('deriv', 'R_10', '1m')] = {
            'version': DeepModelService.MODEL_VERSION,
            'model': 'pytorch_lstm',
            'hiddenSize': 64,
            'featureNames': names,
            'scalerMean': [0.0] * len(names),
            'scalerScale': [1.0] * len(names),
            'stateDict': {
                name: value.detach().cpu().numpy().astype(float).tolist()
                for name, value in model.state_dict().items()
            },
            'calibration': {'method': 'isotonic', 'x': [0.0, 1.0], 'y': [0.0, 1.0]},
        }

        approved = service.predict_candles('deriv', 'R_10', '1m', candles)
        observer = service.predict_candles('market-qx-observer-v2', 'R_10', '1m', candles)

        self.assertTrue(approved['readyForLive'])
        self.assertEqual(approved['direction'], 'CALL')
        self.assertTrue(approved['passesSignalThreshold'])
        self.assertGreaterEqual(approved['confidence'], 90.0)
        self.assertEqual(observer['direction'], 'NO_SIGNAL')
        candles[-1]['completeness'] = 'PARTIAL_TICK_COVERAGE'
        self.assertFalse(service.predict_candles('deriv', 'R_10', '1m', candles)['readyForLive'])
        candles[-1]['completeness'] = 'PROVIDER_OHLC'
        candles[-1]['epoch'] += 60
        session_gap = service.predict_candles('deriv', 'R_10', '1m', candles)
        self.assertTrue(session_gap['readyForLive'])
        self.assertGreater(
            service._feature_rows(candles)[-1, names.index('missing_intervals_log1p')],
            0.0,
        )
        candles[-1]['epoch'] += DeepModelService.MAX_SESSION_GAP_SECONDS
        self.assertEqual(
            service.predict_candles('deriv', 'R_10', '1m', candles)['reason'],
            'GAPPED_PROVIDER_WINDOW',
        )

    def test_training_keeps_normal_session_gaps_and_encodes_them(self):
        candles = []
        for index in range(240):
            epoch = index * 60
            if index >= 120:
                epoch += 12 * 60 * 60
            open_price = 100.0 + index * 0.01
            close = open_price + (0.02 if index % 2 else -0.02)
            candles.append({
                'epoch': epoch, 'open': open_price, 'high': open_price + 0.03,
                'low': open_price - 0.03, 'close': close,
                'completeness': 'PROVIDER_OHLC',
            })

        service = DeepModelService(None)
        features, labels, feature_names = service._training_samples(candles, 'deriv', 'R_10', '1m')

        self.assertEqual(features.shape, (0, 200, len(feature_names)))
        self.assertEqual(len(labels), 0)
        gap_index = feature_names.index('missing_intervals_log1p')
        self.assertGreater(service._feature_rows(candles)[120, gap_index], 0.0)

    def test_live_prediction_reports_below_strict_threshold(self):
        candles = [
            {
                'open': 100 + index, 'high': 101 + index, 'low': 99 + index,
                'close': 100.5 + index, 'epoch': index * 60,
                'completeness': 'PROVIDER_OHLC',
            }
            for index in range(DeepModelService.SEQUENCE_WINDOW + DeepModelService.FEATURE_CONTEXT - 1)
        ]
        names = list(DeepModelService.FEATURE_NAMES)
        model = _CandlestickSequenceModel(len(names))
        with torch.no_grad():
            for parameter in model.parameters():
                parameter.zero_()
        service = DeepModelService(None)
        service.models[('deriv', 'R_10', '1m')] = {
            'version': DeepModelService.MODEL_VERSION,
            'model': 'pytorch_lstm',
            'hiddenSize': 64,
            'featureNames': names,
            'scalerMean': [0.0] * len(names),
            'scalerScale': [1.0] * len(names),
            'stateDict': {
                name: value.detach().cpu().numpy().astype(float).tolist()
                for name, value in model.state_dict().items()
            },
            'calibration': {'method': 'isotonic', 'x': [0.0, 1.0], 'y': [0.0, 1.0]},
        }

        prediction = service.predict_candles('deriv', 'R_10', '1m', candles)
        self.assertTrue(prediction['readyForLive'])
        self.assertFalse(prediction['passesSignalThreshold'])

    def test_ml_api_delegates_training_to_shared_persisted_model_service(self):
        class DeepModelsStub:
            def __init__(self):
                self.calls = []

            def status(self):
                return {'readyMarketCount': 0}

            async def evaluation_status(self):
                return {
                    'expectedModels': 104,
                    'evaluated': 0,
                    'pending': 104,
                    'tier1Count': 0,
                    'tier2Count': 0,
                    'rejectedCount': 0,
                    'backfill': {'fullTargetCount': 0},
                }

            async def train_market(self, source, symbol, timeframe):
                self.calls.append(('train', source, symbol, timeframe))
                return {'status': 'NOT_READY', 'reason': 'INSUFFICIENT_SAMPLES'}

            async def infer_market(self, source, symbol, timeframe):
                self.calls.append(('infer', source, symbol, timeframe))
                return {'readyForLive': False, 'direction': 'NO_SIGNAL'}

        deep_models = DeepModelsStub()
        router = ml_router(Step8ModelRunner(max_agents=2), deep_models)
        endpoints = {route.path.rsplit('/', 2)[-2:][0] + '/' + route.path.rsplit('/', 1)[-1]: route.endpoint for route in router.routes}

        status = asyncio.run(endpoints['ml/status']())
        trained = asyncio.run(endpoints['ml/train']({'source': 'deriv', 'symbol': 'R_10', 'timeframe': '1m'}))
        inferred = asyncio.run(endpoints['ml/infer']({'source': 'deriv', 'symbol': 'R_10', 'timeframe': '1m'}))

        self.assertEqual(status['deepModels']['evaluation']['expectedModels'], 104)
        self.assertEqual(trained['status'], 'NOT_READY')
        self.assertEqual(inferred['direction'], 'NO_SIGNAL')
        self.assertEqual(deep_models.calls, [('train', 'deriv', 'R_10', '1m'), ('infer', 'deriv', 'R_10', '1m')])


if __name__ == '__main__':
    unittest.main()