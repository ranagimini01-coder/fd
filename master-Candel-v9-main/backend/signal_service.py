"""Live future-signal service.

Every cycle: for each fresh (source, symbol, timeframe) evaluate the closed
candles once per upcoming candle and emit at most one signal per entry epoch.
Signals are verified after expiry against the entry candle's real close so the
displayed accuracy is measured, never assumed. A "deep scan" runs when no
signal has qualified for a configurable idle window: it re-evaluates every
market with higher-timeframe confirmation and emits only the best candidate
that still clears a floor. Missing/stale data always yields NO_SIGNAL.
"""
import asyncio
import logging
import math
import os
import time
import uuid

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from market_config import TIMEFRAMES, FRESHNESS
from deriv_service import HISTORY_WARMUP_CANDLES, HISTORY_WARMUP_TIMEFRAMES
from signal_engine import evaluate, qualifies, outcome, market_safety_veto, trend_direction, MIN_CANDLES, DEEP_MIN_CANDLES
from economic_calendar import CALENDAR_REFRESH_SECONDS, EconomicCalendar
from ml_model_adapters import Step8ModelRunner
from signal_research import build_profiles, build_training_mask, walk_forward
from signal_calibration import apply_calibration, calibrate as calibrate_signal_confidence
from core_pipeline import CorePipeline
from forecasting.time_series_predictor import TimeSeriesPredictor
from ensemble_fusion import EnsembleFusion
from forecasting.signal_confluence import SignalConfluenceEngine
from forecasting.risk_manager import RiskManager
from signal_formatter import format_binary_signal
from market_agent_registry import MarketAgentRegistry
from feature_engineering import compute_indicator_bundle, compute_multi_timeframe_features

logger = logging.getLogger(__name__)

SOURCES = ['deriv', 'market-qx-observer-v2']
SIGNAL_TIMEFRAMES = ['1m', '5m', '10m', '15m', '30m', '1h']
HIGHER = {'1m': '5m', '5m': '30m', '10m': '1h', '15m': '1h', '30m': '1h', '1h': None}
PRE_SIGNAL_MIN_TICKS = max(1, int(os.environ.get('PRE_SIGNAL_MIN_TICKS', '3') or 3))
MIN_SIGNAL_CONFIDENCE = 85.0
MIN_LIVE_MODEL_PROBABILITY = 85.0
DEFAULT_SETTINGS = {
    'enabled': True,
    'threshold': 85,
    'sources': list(SOURCES),
    'timeframes': ['1m', '5m', '10m', '30m', '1h'],
    'minAgree': 4,
    'maxOppose': 1,
    'deepScanAfterMinutes': 60,
    'deepScanFloor': 70,
    'evaluateAfterProgress': 0.5,
}


def label_for(instrument):
    return instrument.get('label') or instrument['symbol']


class SignalService:
    def __init__(self, store, deriv=None, master_agent=None, max_concurrent_markets=None, market_registry=None):
        self.store = store
        self.db = store.db
        self.deriv = deriv
        self.master_agent = master_agent
        self.postgres_service = None
        self.deep_model_service = None
        configured_concurrency = max_concurrent_markets or os.environ.get('SIGNAL_MAX_CONCURRENT_MARKETS', '8')
        self.max_concurrent_markets = max(1, min(500, int(configured_concurrency)))
        self.market_registry = market_registry or MarketAgentRegistry(max_agents=500)
        self.active_market_evaluations = 0
        self.core_pipeline = CorePipeline()
        self.settings = dict(DEFAULT_SETTINGS)
        self.cycles = 0
        self.last_cycle = None
        self.last_cycle_ms = None
        self.evaluated_last_cycle = 0
        self.evaluated_markets_last_cycle = 0
        self.fresh_markets_last_cycle = 0
        self.evaluation_targets_last_cycle = 0
        self.last_signal_at = None
        self.last_deep_scan = None
        self.deep_scan_runs = 0
        self.deep_scan_last_result = None
        self.last_portfolio = {'ranked': 0, 'selected': []}
        self.error = None
        self.history_loaded = {}
        self.model_runner = Step8ModelRunner(max_agents=500)
        self.time_series_predictor = TimeSeriesPredictor(confidence_threshold=0.68)
        self.ensemble_fusion = EnsembleFusion()
        self.confluence_engine = SignalConfluenceEngine(
            min_agree=self.settings['minAgree'],
            max_oppose=self.settings['maxOppose'],
            confidence_threshold=max(MIN_SIGNAL_CONFIDENCE / 100.0, self.settings['threshold'] / 100.0),
        )
        self.risk_manager = RiskManager(min_confidence=max(MIN_SIGNAL_CONFIDENCE / 100.0, self.settings['threshold'] / 100.0))
        self._evaluated = {}  # (source, symbol, tf) -> entry epoch already evaluated
        self._insufficient_retry = {}
        self._pre_signals = {}
        self._live_calibration_cache = {}
        self._bayesian_weight_cache = {}
        self._bayesian_booster_weight_cache = {}
        self._calibration_last_run = {}
        self.economic_calendar = EconomicCalendar()
        self._online_training_queue = asyncio.Queue()
        self._online_training_queued = set()
        self._threshold_cache = {}
        self._blacklist_cache = {}
        self.model_refresh_interval = max(
            60, int(os.environ.get('DEEP_MODEL_REFRESH_INTERVAL_SECONDS', '21600') or '21600'),
        )
        self.max_scheduled_model_markets = max(
            1, int(os.environ.get('DEEP_MODEL_REFRESH_MAX_MARKETS', '20') or '20'),
        )
        self.model_bootstrap_interval = max(
            30, int(os.environ.get('DEEP_MODEL_BOOTSTRAP_INTERVAL_SECONDS', '900') or '900'),
        )
        self.model_bootstrap_cooldown = max(
            self.model_bootstrap_interval,
            int(os.environ.get('DEEP_MODEL_BOOTSTRAP_RETRY_SECONDS', '86400') or '86400'),
        )
        self.last_scheduled_model_refresh = None
        self.scheduled_model_refresh_result = None
        self.last_model_bootstrap_scan = None
        self.current_model_bootstrap_market = None
        self.model_bootstrap_result = None
        self._task = None
        self._history_task = None
        self._training_task = None
        self._scheduled_training_task = None
        self._bootstrap_training_task = None
        self._calendar_task = None

    # ----- settings -----------------------------------------------------------------
    def apply_settings(self, changes):
        for key, value in changes.items():
            if key in DEFAULT_SETTINGS and value is not None:
                self.settings[key] = value
        self.settings['timeframes'] = [t for t in self.settings['timeframes'] if t in TIMEFRAMES and t in SIGNAL_TIMEFRAMES] or ['1m']
        self.settings['sources'] = [s for s in self.settings['sources'] if s in SOURCES] or list(SOURCES)
        self._evaluated.clear()
        return dict(self.settings)

    async def load_settings(self):
        saved = await self.db.runtime_settings.find_one({'id': 'signal_engine'}, {'_id': 0, 'id': 0})
        if saved:
            self.apply_settings(saved)
        await self.db.live_signals.create_index([('source', 1), ('symbol', 1), ('timeframe', 1), ('entryEpoch', 1)], unique=True)
        await self.db.live_signals.create_index([('status', 1), ('expiryEpoch', 1)])
        await self.db.live_signals.create_index([('generatedAt', -1)])
        await self.db.signal_research_candidates.create_index([('source', 1), ('symbol', 1), ('timeframe', 1), ('entryEpoch', 1), ('mode', 1)], unique=True)
        await self.db.signal_research_candidates.create_index([('labelStatus', 1), ('expiryEpoch', 1)])
        await self.db.signal_research_candidates.create_index([('generatedAt', -1)])
        await self.db.signal_research_runs.create_index([('source', 1), ('symbol', 1), ('timeframe', 1), ('latestEpoch', 1)], unique=True)
        await self.db.signal_calibration_runs.create_index([('source', 1), ('symbol', 1), ('timeframe', 1), ('datasetVersion', 1)], unique=True)
        await self.db.signal_history.create_index(
            [('source', 1), ('symbol', 1), ('timeframe', 1), ('entryEpoch', 1)],
            unique=True, partialFilterExpression={'entryEpoch': {'$exists': True}},
        )
        await self.db.binary_signal_decisions.create_index([('source', 1), ('symbol', 1), ('timeframe', 1), ('entryEpoch', 1)], unique=True)
        await self.db.deep_model_online_progress.create_index(
            [('source', 1), ('symbol', 1), ('timeframe', 1)], unique=True,
        )
        await self.db.deep_model_observations.create_index(
            [('source', 1), ('symbol', 1), ('timeframe', 1), ('entryEpoch', 1)], unique=True,
        )
        await self.db.deep_model_observations.create_index(
            [('status', 1), ('entryEpoch', 1)],
        )
        await self.db.model_observations.create_index(
            [('signalId', 1)], unique=True,
        )
        await self.db.model_observations.create_index(
            [('source', 1), ('symbol', 1), ('timeframe', 1), ('status', 1), ('verifiedAt', -1)],
        )
        await self.db.calibrations.create_index(
            [('source', 1), ('symbol', 1), ('timeframe', 1), ('modelName', 1)], unique=True,
        )
        await self.db.signal_market_controls.create_index(
            [('source', 1), ('symbol', 1), ('timeframe', 1)], unique=True,
        )
        last = await self.db.live_signals.find_one({}, {'_id': 0, 'generatedAt': 1}, sort=[('generatedAt', -1)])
        if last:
            self.last_signal_at = last['generatedAt']

    async def save_settings(self, changes):
        settings = self.apply_settings(changes)
        await self.db.runtime_settings.update_one({'id': 'signal_engine'}, {'$set': settings}, upsert=True)
        return settings

    def _dynamic_feature_vector(self, candles):
        if not candles:
            return {'count': 0, 'close': 0.0, 'open': 0.0, 'low': 0.0, 'high': 0.0, 'momentum': 0.0, 'volatility': 0.0}
        closes = [float(c.get('close', 0.0)) for c in candles if 'close' in c]
        opens = [float(c.get('open', 0.0)) for c in candles if 'open' in c]
        highs = [float(c.get('high', 0.0)) for c in candles if 'high' in c]
        lows = [float(c.get('low', 0.0)) for c in candles if 'low' in c]
        short_ma = sum(closes[-5:]) / max(1, min(5, len(closes[-5:])))
        long_ma = sum(closes[-20:]) / max(1, min(20, len(closes[-20:])))
        momentum = (short_ma - long_ma) / max(1e-9, abs(long_ma))
        volatility = sum(max(h, 0.0) - max(l, 0.0) for h, l in zip(highs[-10:], lows[-10:])) / max(1, min(10, len(highs[-10:]))) if highs and lows else 0.0
        return {
            'count': len(closes),
            'close': closes[-1] if closes else 0.0,
            'open': opens[-1] if opens else 0.0,
            'low': lows[-1] if lows else 0.0,
            'high': highs[-1] if highs else 0.0,
            'momentum': float(momentum),
            'volatility': float(volatility),
            'short_ma': float(short_ma),
            'long_ma': float(long_ma),
        }

    async def _bayesian_model_weights(self, source, symbol, timeframe):
        key = (source, symbol, timeframe)
        cached = self._bayesian_weight_cache.get(key)
        now = time.time()
        if cached and now - cached[0] < 60:
            return cached[1]
        collection = getattr(self.db, 'calibrations', None)
        if collection is None:
            self._bayesian_booster_weight_cache[key] = (
                now,
                EnsembleFusion.bayesian_weights({}, {
                    name: 1.0 / 3.0 for name in ('xgboost', 'lightgbm', 'catboost')
                }),
            )
            return {'sequence': 0.45, 'tree': 0.30, 'rule': 0.25}
        rows = await collection.find(
            {'source': source, 'symbol': symbol, 'timeframe': timeframe},
            {'_id': 0, 'modelName': 1, 'wins': 1, 'losses': 1},
        ).to_list(20)
        outcomes = {
            row['modelName']: {'wins': row.get('wins', 0), 'losses': row.get('losses', 0)}
            for row in rows if row.get('modelName')
        }
        weights = EnsembleFusion.bayesian_weights(outcomes)
        self._bayesian_booster_weight_cache[key] = (
            now,
            EnsembleFusion.bayesian_weights(
                outcomes,
                {name: 1.0 / 3.0 for name in ('xgboost', 'lightgbm', 'catboost')},
            ),
        )
        self._bayesian_weight_cache[key] = (now, weights)
        return weights

    def _live_signal_stack(self, candles, model_weights=None, tree_probability=0.5):
        feature_vector = self._dynamic_feature_vector(candles)
        feature_vector.update(compute_indicator_bundle(candles))
        forecast = self.time_series_predictor.analyze_sequence(candles)
        forecast_confidence = float(forecast.get('confidence', 0.0))
        if forecast_confidence > 1:
            forecast_confidence /= 100.0
        forecast_confidence = max(0.0, min(1.0, forecast_confidence))
        if forecast.get('direction') == 'PUT':
            sequence_probability = 1.0 - forecast_confidence
        elif forecast.get('direction') == 'CALL':
            sequence_probability = forecast_confidence
        else:
            sequence_probability = 0.5
        sequence_prediction = {'probability': sequence_probability}
        trend_vote = float(feature_vector.get('trend_direction', 0.0))
        momentum = float(feature_vector.get('directional_bias', 0.0))
        momentum_vote = 1.0 if momentum > 0 else -1.0 if momentum < 0 else 0.0
        rule_probability = max(
            0.1, min(0.9, 0.5 + 0.2 * trend_vote + 0.1 * momentum_vote),
        )
        ensemble = self.ensemble_fusion.fuse(
            sequence_prediction=sequence_prediction,
            tree_prediction={'probability': tree_probability},
            rule_prediction={'probability': rule_probability},
            model_weights=model_weights,
        )
        confluence = self.confluence_engine.analyze_market_signal(candles)
        risk_state = self.risk_manager.current_state()
        return {
            'feature_vector': feature_vector,
            'forecast': forecast,
            'ensemble': ensemble,
            'confluence': confluence,
            'risk_state': risk_state,
            'model_probabilities': ensemble.get('probabilities', {}),
        }

    # ----- lifecycle ----------------------------------------------------------------
    def start(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run())
        if self._training_task is None or self._training_task.done():
            self._training_task = asyncio.create_task(self._online_training_worker())
        if self.deep_model_service is not None and (
            self._scheduled_training_task is None or self._scheduled_training_task.done()
        ):
            self._scheduled_training_task = asyncio.create_task(self._scheduled_model_refresh_loop())
        if self.deep_model_service is not None and (
            self._bootstrap_training_task is None or self._bootstrap_training_task.done()
        ):
            self._bootstrap_training_task = asyncio.create_task(self._model_bootstrap_loop())
        if self._calendar_task is None or self._calendar_task.done():
            self._calendar_task = asyncio.create_task(self._calendar_refresh_loop())
        if self.deriv is not None:
            self._history_task = asyncio.create_task(self.warm_history())

    async def stop(self):
        tasks = [
            self._task, self._history_task, self._training_task,
            self._scheduled_training_task, self._bootstrap_training_task, self._calendar_task,
        ]
        for task in tasks:
            if task and not task.done():
                task.cancel()
        await asyncio.gather(*(task for task in tasks if task), return_exceptions=True)

    async def _train_market_models(self, source, symbol, timeframe):
        legacy_result = {'status': 'NOT_READY', 'reason': 'ADVISORY_MODEL_RUNNER_UNAVAILABLE'}
        seconds = TIMEFRAMES.get(timeframe)
        if source == 'deriv' and seconds and self.model_runner is not None:
            rows = await self.db.market_candles.find(
                {
                    'source': source, 'symbol': symbol, 'timeframe': timeframe,
                    'completeness': 'PROVIDER_OHLC',
                    'epoch': {'$lte': time.time() - seconds},
                },
                {'_id': 0},
            ).sort('epoch', -1).limit(5_000).to_list(5_000)
            rows.reverse()
            if len(rows) < 260:
                legacy_result = {
                    'status': 'NOT_READY', 'reason': 'INSUFFICIENT_CLOSED_PROVIDER_CANDLES',
                    'closedProviderCandles': len(rows),
                }
            else:
                try:
                    trained = await asyncio.to_thread(
                        self.model_runner.train_all, source, symbol, timeframe, rows,
                    )
                    legacy_result = {
                        'status': trained.get('status', 'UNKNOWN'),
                        'sampleCount': trained.get('sampleCount', 0),
                        'closedProviderCandles': len(rows),
                        'trainedAt': time.time(),
                    }
                    if trained.get('reason'):
                        legacy_result['reason'] = trained['reason']
                except Exception as exc:
                    legacy_result = {
                        'status': 'FAILED', 'reason': type(exc).__name__,
                        'closedProviderCandles': len(rows),
                    }
                    logger.exception(
                        'Legacy advisory model training failed for %s/%s/%s',
                        source, symbol, timeframe,
                    )
        if self.deep_model_service is None:
            return {'status': 'NOT_READY', 'reason': 'DEEP_MODEL_SERVICE_UNAVAILABLE', 'legacyAdapters': legacy_result}
        report = await self.deep_model_service.train_market(source, symbol, timeframe)
        report['legacyAdapters'] = legacy_result
        return report

    async def _scheduled_model_refresh_loop(self):
        while True:
            await asyncio.sleep(self.model_refresh_interval)
            markets = sorted(set(self.deep_model_service.models) | set(self.deep_model_service.paper_models))
            due_reports = await self.db.deep_model_training_runs.aggregate([
                {'$match': {
                    'source': 'deriv',
                    'modelVersion': getattr(
                        self.deep_model_service, 'MODEL_VERSION', None,
                    ),
                }},
                {'$sort': {'generatedAt': -1}},
                {'$group': {
                    '_id': {
                        'source': '$source', 'symbol': '$symbol',
                        'timeframe': '$timeframe',
                    },
                    'report': {'$first': '$$ROOT'},
                }},
                {'$replaceRoot': {'newRoot': '$report'}},
                {'$match': {'generatedAt': {'$lte': time.time() - self.model_refresh_interval}}},
                {'$sort': {'generatedAt': 1}},
                {'$limit': self.max_scheduled_model_markets},
            ]).to_list(self.max_scheduled_model_markets)
            markets = sorted(set(markets) | {
                (row['source'], row['symbol'], row['timeframe'])
                for row in due_reports
                if row.get('source') and row.get('symbol') and row.get('timeframe')
            })
            self.last_scheduled_model_refresh = time.time()
            if not markets:
                self.scheduled_model_refresh_result = {
                    'status': 'SKIPPED_NO_DUE_MODEL_MARKETS', 'markets': 0,
                }
                continue
            results = {'LIVE_READY': 0, 'PAPER_READY': 0, 'BELOW_TIER_GATES': 0, 'NOT_READY': 0, 'FAILED': 0}
            for source, symbol, timeframe in markets:
                try:
                    report = await self._train_market_models(source, symbol, timeframe)
                    result_status = report.get('status', 'FAILED')
                    results[result_status] = results.get(result_status, 0) + 1
                except asyncio.CancelledError:
                    raise
                except Exception:
                    results['FAILED'] += 1
                    logger.exception(
                        'Scheduled deep-model refresh failed for %s/%s/%s',
                        source, symbol, timeframe,
                    )
            self.scheduled_model_refresh_result = {
                'status': 'COMPLETED', 'markets': len(markets), 'results': results,
                'completedAt': time.time(),
            }

    async def _next_model_bootstrap_market(self, now=None):
        now = time.time() if now is None else now
        deriv = getattr(self, 'deriv', None)
        symbols = list(getattr(deriv, 'symbols', []) or []) if deriv is not None else None
        signal_symbols = getattr(deriv, 'candle_symbols', None)
        if signal_symbols is not None:
            symbols = list(signal_symbols)
        if symbols == []:
            return None
        query = {'source': 'deriv', 'latestEpoch': {'$gte': now - FRESHNESS}}
        if symbols is not None:
            query['symbol'] = {'$in': symbols}
        instruments = await self.db.market_instruments.find(
            query,
            {'_id': 0, 'symbol': 1, 'market': 1, 'latestEpoch': 1},
        ).to_list(500)
        instruments.sort(key=lambda row: (
            row.get('market') not in {'synthetic_index', 'cryptocurrency'},
            -float(row.get('latestEpoch') or 0),
        ))
        trained = set(self.deep_model_service.models) | set(self.deep_model_service.paper_models)
        timeframes = dict.fromkeys(HISTORY_WARMUP_TIMEFRAMES + tuple(self.settings['timeframes']))
        fresh_symbols = [row['symbol'] for row in instruments if row.get('symbol')]
        minimum_candles = HISTORY_WARMUP_CANDLES
        candles_ready = {}
        for timeframe in timeframes:
            if timeframe not in TIMEFRAMES or not fresh_symbols:
                continue
            counts = await self.db.market_candles.aggregate([
                {'$match': {
                    'source': 'deriv', 'symbol': {'$in': fresh_symbols},
                    'timeframe': timeframe, 'completeness': 'PROVIDER_OHLC',
                    'epoch': {'$lte': now - TIMEFRAMES[timeframe]},
                }},
                {'$group': {'_id': '$symbol', 'closedCandles': {'$sum': 1}}},
                {'$match': {
                    'closedCandles': {'$gte': minimum_candles},
                }},
            ]).to_list(None)
            candles_ready[timeframe] = {row['_id'] for row in counts}
        for instrument in instruments:
            symbol = instrument.get('symbol')
            if not symbol:
                continue
            for timeframe in timeframes:
                if timeframe not in TIMEFRAMES:
                    continue
                key = ('deriv', symbol, timeframe)
                if key in trained or symbol not in candles_ready.get(timeframe, set()):
                    continue
                recent = await self.db.deep_model_training_runs.find_one(
                    {
                        'source': 'deriv', 'symbol': symbol, 'timeframe': timeframe,
                        'generatedAt': {'$gte': now - self.model_bootstrap_cooldown},
                    },
                    {'_id': 1},
                )
                if recent is None:
                    return key
        return None

    async def _model_bootstrap_loop(self):
        while True:
            self.last_model_bootstrap_scan = time.time()
            self.current_model_bootstrap_market = None
            next_scan_delay = self.model_bootstrap_interval
            try:
                market = await self._next_model_bootstrap_market()
                if market is None:
                    self.model_bootstrap_result = {
                        'status': 'WAITING_FOR_WARMUP_HISTORY_OR_RETRY_WINDOW',
                        'completedAt': time.time(),
                    }
                else:
                    self.current_model_bootstrap_market = {
                        'source': market[0], 'symbol': market[1], 'timeframe': market[2],
                    }
                    report = await self._train_market_models(*market)
                    self.model_bootstrap_result = {
                        'source': market[0], 'symbol': market[1], 'timeframe': market[2],
                        'status': report.get('status', 'UNKNOWN'),
                        'reason': report.get('reason'), 'completedAt': time.time(),
                    }
                    logger.info(
                        'Model bootstrap completed for %s/%s/%s: %s',
                        *market, report.get('status', 'UNKNOWN'),
                    )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - background training must not stop signal evaluation.
                self.model_bootstrap_result = {
                    'status': 'FAILED', 'reason': type(exc).__name__, 'completedAt': time.time(),
                }
                logger.exception('Automatic model bootstrap failed')
            finally:
                self.current_model_bootstrap_market = None
            await asyncio.sleep(next_scan_delay)

    async def _calendar_refresh_loop(self):
        while True:
            await self.economic_calendar.refresh()
            await asyncio.sleep(CALENDAR_REFRESH_SECONDS)

    async def _schedule_online_training(self, source, symbol, timeframe):
        key = {'source': source, 'symbol': symbol, 'timeframe': timeframe}
        state = await self.db.deep_model_online_progress.find_one(key, {'_id': 0})
        if not state:
            return
        verified = int(state.get('verifiedOutcomes', 0))
        attempted = int(state.get('attemptedThrough', state.get('trainedThrough', 0)))
        if verified - attempted < 50 or (source, symbol, timeframe) in self._online_training_queued:
            return
        claimed = await self.db.deep_model_online_progress.update_one(
            {
                **key,
                'verifiedOutcomes': verified,
                'attemptedThrough': attempted,
                'trainingStatus': {'$nin': ['QUEUED', 'RUNNING']},
            },
            {'$set': {
                'trainingStatus': 'QUEUED',
                'attemptedThrough': verified,
                'queuedThrough': verified,
                'queuedAt': time.time(),
            }},
        )
        if not getattr(claimed, 'modified_count', 0):
            return
        self._online_training_queued.add((source, symbol, timeframe))
        self._online_training_queue.put_nowait((source, symbol, timeframe, verified))

    async def _resume_online_training(self):
        rows = await self.db.deep_model_online_progress.find(
            {'trainingStatus': {'$in': ['QUEUED', 'RUNNING', 'FAILED']}},
            {'_id': 0},
        ).to_list(1000)
        for row in rows:
            key = (row['source'], row['symbol'], row['timeframe'])
            if row.get('trainingStatus') == 'QUEUED':
                self._online_training_queued.add(key)
                self._online_training_queue.put_nowait((*key, int(row.get('queuedThrough', 0))))
            else:
                if row.get('trainingStatus') in {'RUNNING', 'FAILED'}:
                    await self.db.deep_model_online_progress.update_one(
                        {'source': key[0], 'symbol': key[1], 'timeframe': key[2]},
                        {'$set': {
                            'trainingStatus': 'FAILED',
                            'lastTrainingError': 'TRAINING_RETRY_AFTER_RESTART',
                            'attemptedThrough': int(row.get('trainedThrough', 0)),
                        }},
                    )
                await self._schedule_online_training(*key)

    async def _online_training_worker(self):
        await self._resume_online_training()
        while True:
            source, symbol, timeframe, target = await self._online_training_queue.get()
            key = {'source': source, 'symbol': symbol, 'timeframe': timeframe}
            status = 'FAILED'
            try:
                await self.db.deep_model_online_progress.update_one(
                    key,
                    {'$set': {'trainingStatus': 'RUNNING', 'startedAt': time.time()}},
                )
                if self.deep_model_service is None:
                    raise RuntimeError('DEEP_MODEL_SERVICE_UNAVAILABLE')
                report = await self._train_market_models(source, symbol, timeframe)
                status = str(report.get('status', 'UNKNOWN'))
                await self.db.deep_model_online_progress.update_one(
                    key,
                    {'$set': {
                        'trainingStatus': 'COMPLETED',
                        'trainedThrough': target,
                        'completedAt': time.time(),
                        'lastTrainingStatus': status,
                        'lastTrainingReason': report.get('reason'),
                        'lastPromotionReady': report.get('status') in {'PAPER_READY', 'LIVE_READY'},
                        'lastTrainingSamples': report.get('sampleCounts', {}),
                        'legacyAdapterStatus': (report.get('legacyAdapters') or {}).get('status'),
                    }, '$unset': {'lastTrainingError': ''}},
                )
                logger.info('Online model retraining completed for %s/%s/%s: %s', source, symbol, timeframe, status)
            except asyncio.CancelledError:
                await self.db.deep_model_online_progress.update_one(
                    key,
                    {'$set': {'trainingStatus': 'QUEUED', 'queuedThrough': target}},
                )
                raise
            except Exception as exc:
                await self.db.deep_model_online_progress.update_one(
                    key,
                    {'$set': {
                        'trainingStatus': 'FAILED',
                        'lastTrainingError': type(exc).__name__,
                        'completedAt': time.time(),
                    }},
                )
                logger.exception('Online model retraining failed for %s/%s/%s', source, symbol, timeframe)
            finally:
                self._online_training_queued.discard((source, symbol, timeframe))
                self._online_training_queue.task_done()
            if status != 'FAILED':
                await self._schedule_online_training(source, symbol, timeframe)

    async def _record_online_outcome(self, signal, result):
        if (
            signal.get('source') != 'deriv'
            or signal.get('entryCandleCompleteness') != 'PROVIDER_OHLC'
            or result not in {'WIN', 'LOSS'}
        ):
            return
        key = {
            'source': signal['source'],
            'symbol': signal['symbol'],
            'timeframe': signal['timeframe'],
        }
        await self.db.deep_model_online_progress.update_one(
            key,
            {'$setOnInsert': {
                **key,
                'verifiedOutcomes': 0,
                'trainedThrough': 0,
                'attemptedThrough': 0,
                'trainingStatus': 'IDLE',
            }},
            upsert=True,
        )
        await self.db.deep_model_online_progress.find_one_and_update(
            key,
            {
                '$inc': {'verifiedOutcomes': 1},
                '$set': {'updatedAt': time.time()},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        await self._schedule_online_training(**key)

    async def _required_confidence(self, source, symbol, timeframe):
        base = max(int(self.settings['threshold']), int(MIN_SIGNAL_CONFIDENCE))
        risk_manager = getattr(self, 'risk_manager', None)
        if risk_manager:
            base = max(base, int(math.ceil(risk_manager.threshold * 100.0)))
        if source != 'deriv':
            return base
        key = (source, symbol, timeframe)
        cached = self._threshold_cache.get(key)
        now = time.time()
        if cached and now - cached[0] < 60:
            return max(base, cached[1])
        signals = getattr(self.db, 'live_signals', None)
        if signals is None:
            return base
        rows = await signals.find(
            {
                'source': source,
                'symbol': symbol,
                'timeframe': timeframe,
                'status': {'$in': ['WIN', 'LOSS']},
                'entryCandleCompleteness': 'PROVIDER_OHLC',
            },
            {'_id': 0, 'status': 1},
        ).sort('verifiedAt', -1).limit(50).to_list(50)
        threshold = max(
            MIN_SIGNAL_CONFIDENCE,
            base,
            self.adjusted_confidence_threshold(base, [row['status'] for row in rows]),
        )
        self._threshold_cache[key] = (now, threshold)
        return threshold

    @staticmethod
    def adjusted_confidence_threshold(base, trailing_results):
        if len(trailing_results) < 50:
            return int(base)
        wins = sum(result == 'WIN' for result in trailing_results)
        return max(int(base), 90) if wins / len(trailing_results) < 0.60 else int(base)

    @staticmethod
    def _apply_multi_timeframe_filter(assessment, trends):
        if assessment.get('direction') not in {'CALL', 'PUT'}:
            return assessment
        directions = list(trends.values())
        if any(direction not in {'CALL', 'PUT', 'NEUTRAL'} for direction in directions):
            reason = 'HIGHER_TIMEFRAME_TREND_UNAVAILABLE'
        else:
            directional = {direction for direction in directions if direction in {'CALL', 'PUT'}}
            if len(directional) > 1:
                reason = 'HIGHER_TIMEFRAME_TRENDS_DISAGREE'
            elif directional and assessment['direction'] not in directional:
                reason = 'HIGHER_TIMEFRAME_TREND_CONFLICT'
            else:
                return assessment
        assessment['direction'] = 'NO_SIGNAL'
        assessment['confidence'] = 0
        assessment['reason'] = reason
        assessment['vetoes'] = list(assessment.get('vetoes', [])) + [reason]
        return assessment

    async def _is_blacklisted(self, source, symbol, timeframe, now=None):
        now = time.time() if now is None else now
        key = (source, symbol, timeframe)
        cached = self._blacklist_cache.get(key)
        if cached and now - cached[0] < 15:
            return cached[1] > now
        controls = getattr(self.db, 'signal_market_controls', None)
        if controls is None:
            return False
        selector = {'source': source, 'symbol': symbol, 'timeframe': timeframe}
        state = await controls.find_one(selector, {'_id': 0})
        symbol_state = await controls.find_one(
            {'source': source, 'symbol': symbol, 'timeframe': '*'}, {'_id': 0},
        )
        blacklist_until = float((state or {}).get('blacklistedUntil') or 0)
        cooldown_until = float((symbol_state or {}).get('cooldownUntil') or 0)
        until = max(blacklist_until, cooldown_until)
        if blacklist_until and blacklist_until <= now:
            await self.db.signal_market_controls.update_one(
                selector,
                {'$set': {
                    'consecutiveLosses': 0,
                    'blacklistedUntil': None,
                    'updatedAt': now,
                }},
            )
            blacklist_until = 0
        if cooldown_until and cooldown_until <= now:
            await self.db.signal_market_controls.update_one(
                {'source': source, 'symbol': symbol, 'timeframe': '*'},
                {'$set': {'cooldownUntil': None, 'updatedAt': now}},
            )
            cooldown_until = 0
        until = max(blacklist_until, cooldown_until)
        self._blacklist_cache[key] = (now, until)
        return until > now

    async def run(self):
        while True:
            started = time.time()
            try:
                if self.settings['enabled']:
                    await self.cycle()
                await self.verify_pending()
                self.error = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                self.error = type(exc).__name__
                logger.warning('Signal cycle failed: %s', exc)
            self.cycles += 1
            self.last_cycle = time.time()
            self.last_cycle_ms = int((self.last_cycle - started) * 1000)
            await asyncio.sleep(max(1.0, 5 - (time.time() - started)))

    async def warm_history(self):
        """Keep Deriv provider OHLC history loaded for every signal timeframe (>=1m)."""
        await asyncio.sleep(8)
        while True:
            try:
                symbols = list(getattr(self.deriv, 'symbols', []) or [])
                signal_symbols = getattr(self.deriv, 'candle_symbols', None)
                if signal_symbols is not None:
                    symbols = list(signal_symbols)
                instruments = await self.db.market_instruments.find(
                    {'source': 'deriv'},
                    {'_id': 0, 'symbol': 1, 'market': 1, 'latestEpoch': 1},
                ).to_list(None)
                metadata = {row['symbol']: row for row in instruments if row.get('symbol')}
                priority_symbols = {
                    symbol for symbol in symbols
                    if metadata.get(symbol, {}).get('market') in {'synthetic_index', 'cryptocurrency'}
                    or symbol.startswith(('R_', '1HZ', 'cry'))
                }
                symbols = sorted(priority_symbols.intersection(symbols)) + [
                    symbol for symbol in symbols if symbol not in priority_symbols
                ]
                timeframes = dict.fromkeys(HISTORY_WARMUP_TIMEFRAMES + tuple(self.settings['timeframes']))
                for symbol in symbols:
                    for timeframe in timeframes:
                        seconds = TIMEFRAMES.get(timeframe, 0)
                        if seconds < 60:
                            continue
                        key = (symbol, timeframe)
                        if time.time() - self.history_loaded.get(key, 0) < max(seconds, 120):
                            continue
                        try:
                            await asyncio.wait_for(
                                self.deriv.history(symbol, timeframe, count=HISTORY_WARMUP_CANDLES),
                                20,
                            )
                            self.history_loaded[key] = time.time()
                        except asyncio.CancelledError:
                            raise
                        except Exception:  # noqa: BLE001
                            self.history_loaded[key] = time.time() - max(seconds, 120) + 30
                        await asyncio.sleep(0.35)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning('History warm-up failed: %s', exc)
            await asyncio.sleep(10)

    # ----- evaluation ---------------------------------------------------------------
    async def fresh_instruments(self):
        rows = await self.db.market_instruments.find(
            {'source': {'$in': self.settings['sources']}, 'latestEpoch': {'$gte': time.time() - FRESHNESS}}, {'_id': 0}).to_list(None)
        signal_symbols = (
            set(self.deriv.candle_symbols)
            if self.deriv is not None and hasattr(self.deriv, 'candle_symbols')
            else None
        )
        return [
            row for row in rows
            if (
                row.get('source') == 'deriv'
                and (
                    signal_symbols is None
                    or row.get('symbol') in signal_symbols
                )
            )
            or row.get('verificationStatus') == 'CROSS_VALIDATED'
            or (row.get('source') == 'market-qx-observer-v2' and row.get('is_otc') is True and row.get('verificationStatus') == 'OTC_OBSERVATION_ONLY')
        ]

    async def closed_candles(self, source, symbol, timeframe, now, limit=300):
        seconds = TIMEFRAMES[timeframe]
        rows = await self.store.candles(source, symbol, timeframe, limit)
        return [c for c in rows if c['epoch'] + seconds <= now]

    def _merge_model_consensus(self, assessment, source, symbol, timeframe, candles):
        """Combine the rule-based signal with the Step 8 model ensemble."""
        if not candles:
            return assessment
        try:
            inference = self.model_runner.infer_all(source, symbol, timeframe, candles)
            if not inference.get('readyForLive'):
                return assessment
            model_decision = inference.get('decision', assessment.get('direction', 'NO_SIGNAL'))
            model_confidence = float(inference.get('confidence', 0.0))
            model_predictions = inference.get('predictions', {})
            if model_decision in {'CALL', 'PUT'}:
                assessment['modelConsensus'] = {
                    'decision': model_decision,
                    'confidence': round(model_confidence, 2),
                    'models': model_predictions,
                    'behaviour': inference.get('behaviour', {}),
                }
                final_confidence = max(0, min(100, int(round((assessment.get('confidence', 0) * 0.6) + (model_confidence * 0.4)))))
                assessment['confidence'] = final_confidence
                assessment['finalModelScore'] = round(0.5 * max(0.0, min(100.0, float(assessment.get('qualityPairScore', final_confidence)))) + 0.3 * float(final_confidence) + 0.2 * float(model_confidence), 2)
                assessment['votes'] = {**assessment.get('votes', {}), 'model_consensus': {'direction': model_decision, 'weight': 1.25, 'detail': f"Step8 ensemble {model_decision} at {model_confidence:.1f}% confidence"}}
                assessment['agreeing'] = list(dict.fromkeys((assessment.get('agreeing', []) + ['model_consensus'])))
                if assessment.get('direction') not in {'CALL', 'PUT'}:
                    assessment['direction'] = model_decision
                    assessment['reason'] = 'MODEL_ENSEMBLE_SUPERSEDES_RULE_BASED_SIGNAL'
        except Exception as exc:  # noqa: BLE001 - model layer is advisory; do not block the signal pipeline.
            logger.warning('Step8 model ensemble unavailable for %s/%s/%s: %s', source, symbol, timeframe, exc)
        return assessment

    @staticmethod
    def _apply_validated_model(assessment, prediction):
        tier = prediction.get('promotionTier')
        if tier == 'PAPER':
            assessment['paperModelPrediction'] = prediction
            return assessment
        if tier != 'LIVE':
            return assessment
        if assessment.get('direction') not in {'CALL', 'PUT'}:
            return assessment
        assessment['validatedModel'] = prediction
        if not prediction.get('readyForLive'):
            reason = prediction.get('reason', 'VALIDATED_MODEL_UNAVAILABLE')
            assessment['direction'] = 'NO_SIGNAL'
            assessment['confidence'] = 0
            assessment['reason'] = reason
            assessment['vetoes'] = list(assessment.get('vetoes', [])) + [reason]
            return assessment
        model_confidence = float(prediction.get('confidence', 0.0))
        assessment['modelProbability'] = model_confidence / 100.0
        if not prediction.get('passesSignalThreshold', model_confidence >= MIN_LIVE_MODEL_PROBABILITY):
            assessment['direction'] = 'NO_SIGNAL'
            assessment['confidence'] = 0
            assessment['reason'] = 'MODEL_PROBABILITY_BELOW_LIVE_TIER_THRESHOLD'
            assessment['vetoes'] = list(assessment.get('vetoes', [])) + [assessment['reason']]
            return assessment
        model_direction = prediction['direction']
        if model_direction != assessment['direction']:
            assessment['direction'] = 'NO_SIGNAL'
            assessment['confidence'] = 0
            assessment['reason'] = 'VALIDATED_MODEL_DIRECTION_CONFLICT'
            assessment['vetoes'] = list(assessment.get('vetoes', [])) + ['VALIDATED_MODEL_DIRECTION_CONFLICT']
            return assessment

        votes = dict(assessment.get('votes', {}))
        votes['validated_deep_model'] = {
            'direction': model_direction,
            'weight': 1.0,
            'detail': f"{prediction['model']} · {prediction['modelVersion']} · calibrated",
        }
        assessment['votes'] = votes
        assessment['agreeing'] = list(dict.fromkeys(assessment.get('agreeing', []) + ['validated_deep_model']))
        assessment['agreeCount'] = int(assessment.get('agreeCount', 0)) + 1
        assessment['confidence'] = min(
            float(assessment.get('confidence', 0.0)),
            float(prediction['confidence']),
        )
        return assessment

    def _adapter_ready_for_live(self, name):
        model = getattr(self.model_runner, 'models', {}).get(name)
        state = getattr(model, 'state', None)
        metadata = getattr(state, 'metadata', {}) or {}
        return bool(getattr(state, 'trained', False) and metadata.get('readyForLive') is True)

    async def _require_live_model_ensemble(self, assessment, source, symbol, timeframe, candles):
        if source != 'deriv' or assessment.get('direction') not in {'CALL', 'PUT'}:
            return assessment
        lstm_prediction = assessment.get('validatedModel') or {}
        members = {
            'lstm': bool(
                lstm_prediction.get('promotionTier') == 'LIVE'
                and lstm_prediction.get('readyForLive')
                and lstm_prediction.get('passesSignalThreshold')
            ),
            'xgboost': self._adapter_ready_for_live('xgboost'),
            'transformer': self._adapter_ready_for_live('transformer'),
        }
        ensemble = {
            'requiredModels': ['lstm', 'xgboost', 'transformer'],
            'membersReady': members,
            'predictions': {},
            'passed': False,
        }
        if not all(members.values()):
            ensemble['reason'] = 'ENSEMBLE_MODELS_NOT_PROMOTED'
            if not any(members.values()):
                ensemble['shadowEligible'] = True
                assessment['signalTier'] = 'PAPER_SHADOW'
                assessment['modelEnsemble'] = ensemble
                return assessment
        else:
            inference = await asyncio.to_thread(
                self.model_runner.infer_all, source, symbol, timeframe, candles,
            )
            predictions = inference.get('predictions', {})
            ensemble['predictions'] = {
                name: predictions.get(name, {}).get('direction')
                for name in ('xgboost', 'transformer')
            }
            directions = {
                lstm_prediction.get('direction'),
                ensemble['predictions'].get('xgboost'),
                ensemble['predictions'].get('transformer'),
            }
            ensemble['direction'] = next(iter(directions)) if len(directions) == 1 else 'NO_SIGNAL'
            ensemble['passed'] = (
                len(directions) == 1
                and ensemble['direction'] == assessment['direction']
            )
            if not ensemble['passed']:
                ensemble['reason'] = 'ENSEMBLE_MODEL_DISAGREEMENT'
            else:
                assessment['signalTier'] = 'LIVE_VALIDATED'
        assessment['modelEnsemble'] = ensemble
        if not ensemble['passed']:
            reason = ensemble['reason']
            assessment['direction'] = 'NO_SIGNAL'
            assessment['confidence'] = 0
            assessment['reason'] = reason
            assessment['vetoes'] = list(assessment.get('vetoes', [])) + [reason]
        return assessment

    async def _record_paper_model_prediction(self, source, symbol, timeframe, entry_epoch, prediction):
        if (
            source != 'deriv'
            or prediction.get('promotionTier') != 'PAPER'
            or prediction.get('direction') not in {'CALL', 'PUT'}
        ):
            return
        seconds = TIMEFRAMES[timeframe]
        generated_at = time.time()
        observation = {
            'source': source, 'symbol': symbol, 'timeframe': timeframe,
            'entryEpoch': entry_epoch, 'expiryEpoch': entry_epoch + seconds,
            'direction': prediction['direction'],
            'predictedDirection': prediction['direction'],
            'confidence': float(prediction.get('confidence', 0.0)),
            'probabilityUp': float(prediction.get('probabilityUp', 0.5)),
            'promotionTier': 'PAPER',
            'modelVersion': prediction.get('modelVersion'),
            'generatedAt': generated_at,
            'payoutAssumption': getattr(self.deep_model_service, 'ASSUMED_NET_PAYOUT', 0.80),
            'status': 'PENDING',
        }
        await self.db.deep_model_observations.update_one(
            {
                'source': source, 'symbol': symbol, 'timeframe': timeframe,
                'entryEpoch': entry_epoch,
            },
            {'$setOnInsert': observation},
            upsert=True,
        )
        if self.postgres_service is not None:
            mirror = await self.postgres_service.record_deep_model_observation(observation)
            if not mirror.get('stored') and mirror.get('reason') != 'postgres-disabled':
                logger.warning('Paper prediction PostgreSQL mirror failed for %s/%s/%s', source, symbol, timeframe)

    async def _settle_paper_model_predictions(self, now):
        pending = await self.db.deep_model_observations.find(
            {'status': 'PENDING', 'entryEpoch': {'$lte': now - 3}},
            {'_id': 0},
        ).sort('entryEpoch', 1).limit(500).to_list(500)
        for observation in pending:
            candle = await self.db.market_candles.find_one(
                {
                    'source': observation['source'],
                    'symbol': observation['symbol'],
                    'timeframe': observation['timeframe'],
                    'epoch': observation['entryEpoch'],
                    'completeness': 'PROVIDER_OHLC',
                },
                {'_id': 0},
            )
            if candle:
                result = outcome(observation['direction'], candle)
                actual_direction = (
                    'CALL' if float(candle['close']) > float(candle['open'])
                    else 'PUT' if float(candle['close']) < float(candle['open'])
                    else 'TIE'
                )
                await self.db.deep_model_observations.update_one(
                    {
                        'source': observation['source'],
                        'symbol': observation['symbol'],
                        'timeframe': observation['timeframe'],
                        'entryEpoch': observation['entryEpoch'],
                        'status': 'PENDING',
                    },
                    {'$set': {
                        'status': result,
                        'result': result,
                        'actualDirection': actual_direction,
                        'verifiedAt': now,
                        'entryOpen': candle['open'],
                        'exitClose': candle['close'],
                        'entryCandleCompleteness': candle.get('completeness'),
                    }},
                )
                if self.postgres_service is not None:
                    mirror = await self.postgres_service.settle_deep_model_observation({
                        **observation,
                        'actualDirection': actual_direction,
                        'result': result,
                        'status': result,
                        'verifiedAt': now,
                    })
                    if not mirror.get('stored') and mirror.get('reason') != 'postgres-disabled':
                        logger.warning(
                            'Paper outcome PostgreSQL mirror failed for %s/%s/%s',
                            observation['source'], observation['symbol'], observation['timeframe'],
                        )
            elif now > observation['expiryEpoch'] + 2 * TIMEFRAMES[observation['timeframe']] + 30:
                await self.db.deep_model_observations.update_one(
                    {
                        'source': observation['source'],
                        'symbol': observation['symbol'],
                        'timeframe': observation['timeframe'],
                        'entryEpoch': observation['entryEpoch'],
                        'status': 'PENDING',
                    },
                    {'$set': {
                        'status': 'VOID', 'result': 'NO_ENTRY_CANDLE_DATA',
                        'actualDirection': None, 'verifiedAt': now,
                        'reason': 'NO_PROVIDER_ENTRY_CANDLE',
                    }},
                )
                if self.postgres_service is not None:
                    mirror = await self.postgres_service.settle_deep_model_observation({
                        **observation,
                        'actualDirection': None,
                        'result': 'NO_ENTRY_CANDLE_DATA',
                        'status': 'VOID',
                        'verifiedAt': now,
                    })
                    if not mirror.get('stored') and mirror.get('reason') != 'postgres-disabled':
                        logger.warning(
                            'Paper void PostgreSQL mirror failed for %s/%s/%s',
                            observation['source'], observation['symbol'], observation['timeframe'],
                        )

    async def assess(self, instrument, timeframe, now, deep=False):
        """Evaluate one market for the next candle. Returns (assessment | None, reason, entry_epoch)."""
        source, symbol = instrument['source'], instrument['symbol']
        seconds = TIMEFRAMES[timeframe]
        bucket = int(now // seconds) * seconds
        entry = bucket + seconds
        candles = await self.closed_candles(source, symbol, timeframe, now)
        is_otc = bool(instrument.get('is_otc') or '(OTC)' in symbol.upper() or '[OTC]' in symbol.upper())
        if source == 'market-qx-observer-v2':
            completeness = 'OBSERVED_UNVERIFIED' if is_otc else 'CROSS_VALIDATED'
            candles = [candle for candle in candles if candle.get('completeness') == completeness]
        safety_reason = market_safety_veto(candles)
        if safety_reason:
            blocked = {
                'direction': 'NO_SIGNAL', 'confidence': 0, 'reason': safety_reason,
                'vetoes': [safety_reason], 'votes': {}, 'agreeing': [], 'opposing': [],
                'agreeCount': 0, 'opposeCount': 0,
            }
            return blocked, safety_reason, entry
        if self.economic_calendar.blackout_event(symbol, now):
            reason = 'HIGH_IMPACT_ECONOMIC_EVENT'
            blocked = {
                'direction': 'NO_SIGNAL', 'confidence': 0, 'reason': reason,
                'vetoes': [reason], 'votes': {}, 'agreeing': [], 'opposing': [],
                'agreeCount': 0, 'opposeCount': 0,
            }
            return blocked, reason, entry
        if source == 'market-qx-observer-v2' and is_otc:
            report = await asyncio.to_thread(
                self.core_pipeline.evaluate, source, symbol, timeframe, candles, seconds,
                learned_weights=None, now=now, is_otc=True,
            )
            assessment = dict(report.get('signal') or {})
            assessment['trainingInputCompleteness'] = 'OBSERVED_UNVERIFIED'
            assessment['is_otc'] = True
            assessment['qualityPairScore'] = report.get('qualityPair', {}).get('rankingScore', 0)
            assessment['pipelineState'] = report.get('state')
            assessment['vetoes'] = report.get('vetoes', [])
            assessment['forecast'] = (assessment.get('forecast') or {})
            return assessment, assessment.get('reason', ''), entry
        minimum = DEEP_MIN_CANDLES if deep else MIN_CANDLES
        if len(candles) < minimum:
            return None, f'INSUFFICIENT_CLOSED_CANDLES_{len(candles)}_OF_{minimum}', entry
        # The most recent closed candle must be the one immediately before the forming candle.
        if candles[-1]['epoch'] != bucket - seconds:
            return None, 'GAP_BEFORE_CURRENT_CANDLE', entry
        higher = None
        if HIGHER.get(timeframe):
            higher = await self.closed_candles(source, symbol, HIGHER[timeframe], now, 120)
            if source == 'market-qx-observer-v2':
                higher = [candle for candle in higher if candle.get('completeness') == 'CROSS_VALIDATED']
        multi_timeframe = None
        multi_timeframe_features = {}
        if source == 'deriv':
            timeframe_candles = {timeframe: candles}
            for confluence_timeframe in ('1m', '5m', '15m'):
                if confluence_timeframe not in TIMEFRAMES:
                    timeframe_candles[confluence_timeframe] = []
                elif confluence_timeframe == timeframe:
                    timeframe_candles[confluence_timeframe] = candles
                elif confluence_timeframe == HIGHER.get(timeframe) and higher is not None:
                    timeframe_candles[confluence_timeframe] = higher
                else:
                    timeframe_candles[confluence_timeframe] = await self.closed_candles(
                        source, symbol, confluence_timeframe, now, 120,
                    )
            multi_timeframe = {
                confluence_timeframe: trend_direction(timeframe_candles[confluence_timeframe])
                for confluence_timeframe in ('1m', '5m', '15m')
            }
            multi_timeframe_features = compute_multi_timeframe_features(timeframe_candles)
        weights = await self.master_agent.weights(source, symbol, timeframe) if self.master_agent else None
        assessment = evaluate(candles, higher_timeframe_candles=higher, deep=deep, weights=weights)
        if multi_timeframe is not None:
            assessment['multiTimeframeTrend'] = multi_timeframe
            assessment['multiTimeframeFeatures'] = multi_timeframe_features
        assessment['trainingInputCompleteness'] = candles[-1].get('completeness')
        model_weights = await self._bayesian_model_weights(source, symbol, timeframe)
        booster_weights = self._bayesian_booster_weight_cache.get(
            (source, symbol, timeframe), (time.time(), {}),
        )[1]
        tree_probability = 0.5
        boosted_tree_probabilities = {}
        if len(candles) >= 200 and any(
            getattr(getattr(self.model_runner.models.get(name), 'state', None), 'trained', False)
            for name in ('xgboost', 'lightgbm', 'catboost')
        ):
            try:
                inference = await asyncio.to_thread(
                    self.model_runner.infer_all, source, symbol, timeframe, candles,
                )
                boosted_tree_probabilities = {
                    name: float(prediction['probability'])
                    for name, prediction in inference.get('predictions', {}).items()
                    if name in {'xgboost', 'lightgbm', 'catboost'}
                    and getattr(self.model_runner.models.get(name).state, 'trained', False)
                    and isinstance(prediction.get('probability'), (int, float))
                }
                available_weight = sum(
                    booster_weights.get(name, 0.0)
                    for name in boosted_tree_probabilities
                )
                if available_weight > 0:
                    tree_probability = sum(
                        probability * booster_weights.get(name, 0.0)
                        for name, probability in boosted_tree_probabilities.items()
                    ) / available_weight
            except Exception as exc:  # noqa: BLE001 - advisory boosters must not block verified signal gates.
                logger.warning(
                    'Boosted-tree inference unavailable for %s/%s/%s: %s',
                    source, symbol, timeframe, type(exc).__name__,
                )
        live_stack = self._live_signal_stack(candles, model_weights, tree_probability)
        assessment['feature_vector'] = live_stack['feature_vector']
        assessment['feature_vector'].update(multi_timeframe_features)
        assessment['forecast'] = live_stack['forecast']
        assessment['ensemble'] = live_stack['ensemble']
        assessment['modelProbabilities'] = live_stack['model_probabilities']
        assessment['boostedTreeProbabilities'] = boosted_tree_probabilities
        assessment['confluence'] = live_stack['confluence']
        assessment['risk_state'] = live_stack['risk_state']

        if live_stack['confluence'].get('direction') in {'CALL', 'PUT'}:
            assessment['direction'] = live_stack['confluence']['direction']
            assessment['confidence'] = max(float(assessment.get('confidence', 0.0)), float(live_stack['confluence'].get('confidence', 0.0)) * 100.0)
            assessment['reason'] = 'LIVE_CONFLUENCE_FUSION_TRIGGERED'

        if live_stack['ensemble'].get('direction') in {'CALL', 'PUT'} and assessment.get('direction') not in {'CALL', 'PUT'}:
            assessment['direction'] = live_stack['ensemble']['direction']
            assessment['confidence'] = max(float(assessment.get('confidence', 0.0)), float(live_stack['ensemble'].get('confidence', 0.0)) * 100.0)
            assessment['reason'] = 'LIVE_ENSEMBLE_FUSION_TRIGGERED'

        assessment = self._merge_model_consensus(assessment, source, symbol, timeframe, candles)
        if source == 'deriv':
            if self.deep_model_service is None:
                prediction = {'readyForLive': False, 'promotionTier': None, 'direction': 'NO_SIGNAL', 'reason': 'DEEP_MODEL_SERVICE_UNAVAILABLE'}
            else:
                prediction = await asyncio.to_thread(
                    self.deep_model_service.predict_candles,
                    source, symbol, timeframe, candles,
                )
            await self._record_paper_model_prediction(
                source, symbol, timeframe, entry, prediction,
            )
            assessment = self._apply_validated_model(assessment, prediction)
            assessment = await self._require_live_model_ensemble(
                assessment, source, symbol, timeframe, candles,
            )
        if multi_timeframe is not None:
            assessment = self._apply_multi_timeframe_filter(assessment, multi_timeframe)
        assessment = await self._apply_live_calibration(assessment, source, symbol, timeframe)
        assessment['requiredConfidenceThreshold'] = await self._required_confidence(source, symbol, timeframe)
        if self.postgres_service is not None:
            try:
                await self.postgres_service.log_signal_analysis(
                    source=source,
                    symbol=symbol,
                    timeframe=timeframe,
                    entry_epoch=entry,
                    direction=assessment.get('direction', 'NO_SIGNAL'),
                    confidence=float(assessment.get('confidence', 0.0)),
                    feature_vector=assessment.get('feature_vector', {}),
                    micro_momentum=assessment.get('microMomentum', {}),
                    confluence=assessment.get('confluence', {}),
                    threshold=float(assessment['requiredConfidenceThreshold']) / 100.0,
                    embedding=assessment.get('feature_vector'),
                )
            except Exception as exc:  # noqa: BLE001 - PostgreSQL vectors are advisory persistence only.
                logger.warning('Feature vector persistence unavailable for %s/%s/%s: %s', source, symbol, timeframe, exc)
        return assessment, assessment.get('reason', ''), entry

    async def _live_calibrators(self, source, symbol, timeframe):
        if source != 'deriv':
            return []
        key = (source, symbol, timeframe)
        cached = self._live_calibration_cache.get(key)
        if cached and time.time() - cached[0] < 60:
            return cached[1]
        collection = getattr(self.db, 'signal_calibration_runs', None)
        if collection is None:
            return []
        try:
            rows = await collection.find(
                {**dict(zip(('source', 'symbol', 'timeframe'), key)), 'readyForLive': True},
                {'_id': 0},
            ).sort('generatedAt', -1).limit(500).to_list(500)
        except Exception as exc:  # noqa: BLE001 - missing calibration storage must not block signal evaluation.
            logger.warning('Live calibration lookup unavailable for %s/%s/%s: %s', source, symbol, timeframe, type(exc).__name__)
            return []
        latest_by_profile = {}
        for row in rows:
            profile_id = row.get('agentId')
            if profile_id and profile_id not in latest_by_profile:
                latest_by_profile[profile_id] = row
        calibrators = list(latest_by_profile.values())
        self._live_calibration_cache[key] = (time.time(), calibrators)
        return calibrators

    async def _apply_live_calibration(self, assessment, source, symbol, timeframe):
        if assessment.get('direction') not in {'CALL', 'PUT'}:
            return assessment
        raw_confidence = float(assessment.get('confidence', 0.0))
        eligible = []
        for row in await self._live_calibrators(source, symbol, timeframe):
            profile = row.get('profile') or {}
            result = row.get('result') or {}
            if not result.get('readyForLive') or result.get('status') != 'READY':
                continue
            accepted, _reason = qualifies(
                assessment,
                profile.get('threshold', 100),
                profile.get('minAgree', 10),
                profile.get('maxOppose', 0),
            )
            if not accepted:
                continue
            calibrated = apply_calibration(raw_confidence / 100.0, result.get('knots', []))
            if calibrated is None:
                continue
            test = result.get('test') or {}
            eligible.append((
                float(test.get('accuracyLower95') or 0.0),
                int(test.get('sampleSize') or result.get('splitCounts', {}).get('test', 0)),
                calibrated, profile, row,
            ))
        if not eligible:
            return assessment
        _lower_bound, _sample_size, calibrated, profile, row = max(eligible, key=lambda item: (item[0], item[1]))
        return {
            **assessment,
            'rawConfidence': raw_confidence,
            'confidence': round(calibrated * 100.0, 2),
            'calibratedProfile': profile,
            'calibration': {
                'status': 'OUT_OF_SAMPLE_VALIDATED',
                'agentId': row['agentId'],
                'datasetVersion': row.get('datasetVersion'),
                'testAccuracyLower95': _lower_bound,
                'testSampleSize': _sample_size,
                'rawConfidence': raw_confidence,
                'calibratedConfidence': round(calibrated * 100.0, 2),
            },
        }

    async def _evaluate_cycle_market(self, instrument, timeframe, now, semaphore, progress_gate, market_context=None):
        async with semaphore:
            seconds = TIMEFRAMES[timeframe]
            bucket = int(now // seconds) * seconds
            await self._maybe_emit_pre_signal(instrument, timeframe, now, bucket)
            entry = bucket + seconds
            if (
                instrument['source'] == 'deriv'
                and timeframe == '1m'
                and not 5 <= entry - now <= 10
            ):
                return {'evaluated': 0, 'candidate': None}
            if (now - bucket) / seconds < progress_gate:
                return {'evaluated': 0, 'candidate': None}

            key = (instrument['source'], instrument['symbol'], timeframe)
            if await self._is_blacklisted(*key, now=now):
                return {'evaluated': 0, 'candidate': None}
            if market_context is not None:
                market_context.ingest_snapshot({'timestamp': now, 'entryEpoch': entry})
            if self._evaluated.get(key) == entry:
                return {'evaluated': 0, 'candidate': None}
            retry_at = self._insufficient_retry.get(key)
            if retry_at and now < retry_at:
                return {'evaluated': 0, 'candidate': None}

            self.active_market_evaluations += 1
            try:
                assessment, reason, entry = await self.assess(instrument, timeframe, now)
                if (
                    assessment is not None
                    and instrument['source'] == 'deriv'
                    and timeframe == '1m'
                    and assessment.get('direction') in {'CALL', 'PUT'}
                ):
                    momentum = await self._confirm_micro_momentum(
                        instrument['source'], instrument['symbol'], assessment['direction'], now,
                    )
                    assessment['microMomentum'] = momentum
                    feature_vector = assessment.setdefault('feature_vector', {})
                    feature_vector['micro_tick_velocity_per_second'] = float(momentum.get('velocityPerSecond', 0.0))
                    feature_vector['micro_tick_range'] = float(momentum.get('tickRange', 0.0))
                    feature_vector['micro_ticks_per_second'] = float(momentum.get('ticksPerSecond', 0.0))
                    if not momentum['passed']:
                        assessment['direction'] = 'NO_SIGNAL'
                        assessment['confidence'] = 0
                        assessment['reason'] = momentum['reason']
                        assessment['vetoes'] = list(assessment.get('vetoes', [])) + [momentum['reason']]
            finally:
                self.active_market_evaluations = max(0, self.active_market_evaluations - 1)
            if assessment is None:
                if reason.startswith('INSUFFICIENT'):
                    self._insufficient_retry[key] = now + 60
                else:
                    self._evaluated[key] = entry
                return {'evaluated': 1, 'candidate': None}

            if market_context is not None:
                market_context.attach_features(assessment.get('feature_vector') or {})
                market_context.attach_behaviour(assessment.get('behaviour') or {})

            self._evaluated[key] = entry
            is_otc = bool(instrument.get('is_otc') or '(OTC)' in instrument['symbol'].upper() or '[OTC]' in instrument['symbol'].upper())
            if is_otc:
                ok, gate = qualifies(assessment, max(MIN_SIGNAL_CONFIDENCE, self.settings['threshold']), min_agree=2, max_oppose=0)
            else:
                profile = assessment.get('calibratedProfile') or {}
                ok, gate = qualifies(
                    assessment,
                    max(MIN_SIGNAL_CONFIDENCE, int(assessment.get('requiredConfidenceThreshold', self.settings['threshold'])), int(profile.get('threshold', 0))),
                    max(self.settings['minAgree'], int(profile.get('minAgree', 0))),
                    min(self.settings['maxOppose'], int(profile.get('maxOppose', self.settings['maxOppose']))),
                )
            if assessment.get('vetoes'):
                ok, gate = False, assessment['vetoes'][0]
            candidate_mode = 'OTC_FORECAST' if is_otc else 'STANDARD'
            await self.record_candidate(instrument, timeframe, entry, assessment, ok, gate, candidate_mode)
            if not ok:
                return {'evaluated': 1, 'candidate': None}

            quality_score = assessment.get('qualityPairScore', assessment.get('qualityScore', assessment.get('confidence', 0)))
            final_score = float(assessment.get('finalModelScore', quality_score))
            assessment['finalSelectionScore'] = final_score
            candidate = {
                'instrument': instrument, 'timeframe': timeframe, 'entry': entry,
                'assessment': assessment, 'qualified': True, 'qualityScore': quality_score,
                'finalScore': final_score, 'mode': candidate_mode,
            }
            return {'evaluated': 1, 'candidate': candidate}

    async def _confirm_micro_momentum(self, source, symbol, direction, now, window_seconds=10):
        ticks = await self.db.market_ticks.find(
            {
                'source': source, 'symbol': symbol,
                'epoch': {'$gte': now - window_seconds, '$lt': now},
            },
            {'_id': 0, 'price': 1, 'epoch': 1},
        ).sort('epoch', 1).limit(100).to_list(100)
        ticks = [
            tick for tick in ticks
            if isinstance(tick.get('price'), (int, float))
            and isinstance(tick.get('epoch'), (int, float))
            and float(tick['price']) > 0
        ]
        if (
            len(ticks) < PRE_SIGNAL_MIN_TICKS
            or now - float(ticks[-1]['epoch']) > min(3.0, FRESHNESS)
        ):
            return {
                'passed': False, 'direction': 'NEUTRAL', 'velocityPerSecond': 0.0,
                'tickRange': 0.0, 'ticksPerSecond': 0.0,
                'sampleCount': len(ticks), 'windowSeconds': window_seconds,
                'reason': 'MICRO_MOMENTUM_DATA_UNAVAILABLE',
            }
        elapsed = max(1e-6, float(ticks[-1]['epoch']) - float(ticks[0]['epoch']))
        delta = float(ticks[-1]['price']) - float(ticks[0]['price'])
        minimum_delta = max(1e-12, float(ticks[-1]['price']) * 1e-8)
        momentum_direction = (
            'CALL' if delta > minimum_delta else
            'PUT' if delta < -minimum_delta else 'NEUTRAL'
        )
        passed = momentum_direction == direction
        return {
            'passed': passed,
            'direction': momentum_direction,
            'delta': delta,
            'velocityPerSecond': delta / elapsed,
            'tickRange': max(float(tick['price']) for tick in ticks) - min(float(tick['price']) for tick in ticks),
            'ticksPerSecond': (len(ticks) - 1) / elapsed,
            'sampleCount': len(ticks),
            'windowSeconds': window_seconds,
            'reason': None if passed else 'MICRO_MOMENTUM_CONFLICT',
        }

    async def _maybe_emit_pre_signal(self, instrument, timeframe, now, bucket):
        seconds = TIMEFRAMES[timeframe]
        entry = bucket + seconds
        remaining = entry - now
        if not 20 <= remaining <= 40:
            return None

        source, symbol = instrument['source'], instrument['symbol']
        key = (source, symbol, timeframe)
        if await self._is_blacklisted(source, symbol, timeframe, now):
            self._pre_signals.pop(key, None)
            return None
        existing = self._pre_signals.get(key)
        if existing and existing['entryEpoch'] == entry:
            return existing

        latest_epoch = instrument.get('latestEpoch')
        if latest_epoch is None or now - float(latest_epoch) > FRESHNESS or float(latest_epoch) > now + 2:
            return None

        forming = await self.db.market_candles.find_one(
            {'source': source, 'symbol': symbol, 'timeframe': timeframe, 'epoch': bucket},
            {'_id': 0},
        )
        if not forming or forming.get('completeness') != 'PARTIAL_TICK_COVERAGE':
            return None
        tick_count = await self.db.market_ticks.count_documents({
            'source': source, 'symbol': symbol,
            'epoch': {'$gte': bucket, '$lt': now},
        })
        if tick_count < PRE_SIGNAL_MIN_TICKS:
            return None

        closed = await self.closed_candles(source, symbol, timeframe, now)
        if len(closed) < MIN_CANDLES - 1 or closed[-1]['epoch'] != bucket - seconds:
            return None
        if market_safety_veto(closed) or self.economic_calendar.blackout_event(symbol, now):
            return None

        weights = await self.master_agent.weights(source, symbol, timeframe) if self.master_agent else None
        assessment = evaluate(closed[-(MIN_CANDLES - 1):] + [forming], weights=weights)
        if assessment.get('direction') not in {'CALL', 'PUT'} or assessment.get('confidence', 0) < 90:
            return None
        if assessment.get('agreeCount', 0) < 5 or assessment.get('opposeCount', 0) > 1:
            return None
        if source == 'deriv':
            if self.deep_model_service is not None:
                prediction = await asyncio.to_thread(
                    self.deep_model_service.predict_candles,
                    source, symbol, timeframe, closed,
                )
                await self._record_paper_model_prediction(
                    source, symbol, timeframe, entry, prediction,
                )
                if prediction.get('promotionTier') == 'LIVE' and (
                    not prediction.get('readyForLive')
                    or not prediction.get('passesSignalThreshold')
                    or prediction.get('direction') != assessment['direction']
                ):
                    return None
                assessment = self._apply_validated_model(assessment, prediction)
                assessment = await self._require_live_model_ensemble(
                    assessment, source, symbol, timeframe, closed,
                )
                if (
                    assessment.get('direction') not in {'CALL', 'PUT'}
                    or assessment.get('signalTier') != 'LIVE_VALIDATED'
                ):
                    return None

        payload = {
            'id': f'{source}:{symbol}:{timeframe}:{entry}',
            'source': source,
            'symbol': symbol,
            'pair': instrument.get('label') or symbol,
            'direction': assessment['direction'],
            'timeframe': timeframe,
            'setupConfidence': assessment['confidence'],
            'validationTier': assessment.get('signalTier', 'OBSERVATION_ONLY'),
            'entryEpoch': entry,
            'generatedAt': now,
        }
        self._pre_signals[key] = payload
        return payload

    def current_pre_signal(self, source, symbol, timeframe, now=None):
        now = time.time() if now is None else now
        payload = self._pre_signals.get((source, symbol, timeframe))
        if (
            not payload
            or payload.get('validationTier') != 'LIVE_VALIDATED'
            or payload['entryEpoch'] <= now
        ):
            return None
        return {**payload, 'countdownSeconds': max(0, int(payload['entryEpoch'] - now + 0.999))}

    async def cycle(self):
        now = time.time()
        instruments = await self.fresh_instruments()
        self.fresh_markets_last_cycle = len({(item['source'], item['symbol']) for item in instruments})
        evaluated = 0
        evaluated_markets = set()
        emitted = 0
        qualified_candidates = []
        progress_gate = float(self.settings['evaluateAfterProgress'])
        semaphore = asyncio.Semaphore(self.max_concurrent_markets)
        instruments_by_key = {(item['source'], item['symbol']): item for item in instruments}
        market_contexts = self.market_registry.sync_active(
            (instrument['source'], instrument['symbol'], timeframe)
            for instrument in instruments
            for timeframe in self.settings['timeframes']
        )
        self.evaluation_targets_last_cycle = len(market_contexts)
        tasks = [
            self._evaluate_cycle_market(
                instruments_by_key[(context.source, context.symbol)], context.timeframe,
                now, semaphore, progress_gate, context,
            )
            for context in market_contexts
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for context, result in zip(market_contexts, results):
            if isinstance(result, BaseException):
                if isinstance(result, asyncio.CancelledError):
                    raise result
                logger.warning('Market evaluation failed: %s', type(result).__name__)
                continue
            evaluated += result['evaluated']
            if result['evaluated']:
                evaluated_markets.add((context.source, context.symbol))
            if result['candidate'] is not None:
                qualified_candidates.append(result['candidate'])
        if self.master_agent:
            selection = self.master_agent.orchestrate(qualified_candidates, top_n=15, select_n=3)
        else:
            ranked = sorted(qualified_candidates, key=lambda item: (item['qualityScore'], item['assessment']['confidence']), reverse=True)
            selection = {'top15': ranked[:15], 'selected': ranked[:3]}
        self.last_portfolio = {
            'ranked': len(selection['top15']),
            'selected': [f"{item['instrument']['symbol']}:{item['timeframe']}" for item in selection['selected']],
        }
        for candidate in selection['selected']:
            candidate['assessment']['finalSelectionScore'] = float(candidate.get('finalScore', candidate['assessment'].get('finalModelScore', candidate['assessment'].get('confidence', 0))))
            if await self.emit(candidate['instrument'], candidate['timeframe'], candidate['entry'], candidate['assessment'], candidate['mode']):
                emitted += 1
        self.evaluated_last_cycle = evaluated
        self.evaluated_markets_last_cycle = len(evaluated_markets)
        idle_for = now - (self.last_signal_at or 0)
        deep_after = self.settings['deepScanAfterMinutes'] * 60
        if not emitted and idle_for >= deep_after and (self.last_deep_scan is None or now - self.last_deep_scan >= 300):
            await self.deep_scan(instruments, now)

    async def deep_scan(self, instruments=None, now=None, manual=False):
        """Re-evaluate every fresh market with higher-timeframe confirmation; emit only the best candidate."""
        now = now or time.time()
        instruments = instruments if instruments is not None else await self.fresh_instruments()
        self.last_deep_scan = now
        self.deep_scan_runs += 1
        best = None
        scanned = 0
        for instrument in instruments:
            for timeframe in self.settings['timeframes']:
                if await self._is_blacklisted(instrument['source'], instrument['symbol'], timeframe, now):
                    continue
                seconds = TIMEFRAMES[timeframe]
                bucket = int(now // seconds) * seconds
                if (now - bucket) / seconds < 0.3 and not manual:
                    continue
                entry = bucket + seconds
                if await self.db.live_signals.find_one({'source': instrument['source'], 'symbol': instrument['symbol'], 'timeframe': timeframe, 'entryEpoch': entry}, {'_id': 1}):
                    continue
                assessment, _reason, entry = await self.assess(instrument, timeframe, now, deep=True)
                if assessment is None:
                    continue
                scanned += 1
                is_otc = bool(instrument.get('is_otc') or '(OTC)' in instrument['symbol'].upper() or '[OTC]' in instrument['symbol'].upper())
                if is_otc:
                    ok, gate = qualifies(assessment, 85, min_agree=2, max_oppose=0)
                    candidate_mode = 'OTC_FORECAST'
                else:
                    profile = assessment.get('calibratedProfile') or {}
                    ok, gate = qualifies(
                        assessment,
                        max(
                            MIN_SIGNAL_CONFIDENCE,
                            self.settings['deepScanFloor'],
                            int(assessment.get('requiredConfidenceThreshold', self.settings['threshold'])),
                            int(profile.get('threshold', 0)),
                        ),
                        max(3, self.settings['minAgree'] - 1, int(profile.get('minAgree', 0))),
                        min(self.settings['maxOppose'], int(profile.get('maxOppose', self.settings['maxOppose']))),
                    )
                    candidate_mode = 'DEEP_SCAN'
                if assessment.get('vetoes'):
                    ok, gate = False, assessment['vetoes'][0]
                await self.record_candidate(instrument, timeframe, entry, assessment, ok, gate, candidate_mode)
                if ok and (best is None or assessment['confidence'] > best[3]['confidence']):
                    best = (instrument, timeframe, entry, assessment)
        result = {'at': now, 'scanned': scanned, 'emitted': None, 'manual': manual}
        if best:
            instrument, timeframe, entry, assessment = best
            output_mode = 'OTC_FORECAST' if instrument.get('is_otc') or assessment.get('is_otc') else 'DEEP_SCAN'
            if await self.emit(instrument, timeframe, entry, assessment, output_mode):
                result['emitted'] = {'symbol': instrument['symbol'], 'timeframe': timeframe, 'direction': assessment['direction'], 'confidence': assessment['confidence']}
        self.deep_scan_last_result = result
        return result

    async def research(self, source, symbol, timeframe):
        if source not in SOURCES or timeframe not in SIGNAL_TIMEFRAMES:
            raise ValueError('UNSUPPORTED_RESEARCH_SLICE')
        rows = await self.store.candles(source, symbol, timeframe, limit=5000)
        now = time.time()
        seconds = TIMEFRAMES[timeframe]
        closed = [row for row in rows if row['epoch'] + seconds <= now]
        result = walk_forward(closed)
        latest_epoch = closed[-1]['epoch'] if closed else None
        eligible_candle_count = sum(
            row.get('completeness') == 'PROVIDER_OHLC' for row in closed
        )
        training_eligible = source == 'deriv' and eligible_candle_count == len(closed) and bool(closed)
        if not training_eligible:
            result['readyForLive'] = False
            if result.get('status') == 'VALIDATED_90':
                result['status'] = 'OBSERVATION_ONLY'
                result['reason'] = 'SOURCE_OR_CANDLE_PROVENANCE_NOT_ELIGIBLE_FOR_LIVE_VALIDATION'
        report = {
            'source': source, 'symbol': symbol, 'timeframe': timeframe,
            'latestEpoch': latest_epoch, 'generatedAt': now,
            'pool': {
                'count': len(build_profiles()),
                'type': 'DETERMINISTIC_RULE_PROFILES_NOT_INDEPENDENT_AI_AGENTS',
            },
            'trainingData': {
                'closedCandles': len(closed), 'providerVerifiedCandles': eligible_candle_count,
                'trainingEligible': training_eligible,
            },
            'result': result,
        }
        if latest_epoch is not None:
            key = {name: report[name] for name in ('source', 'symbol', 'timeframe', 'latestEpoch')}
            await self.db.signal_research_runs.update_one(key, {'$setOnInsert': report}, upsert=True)
        return report

    async def calibration_status(self, source, symbol, timeframe):
        if source not in SOURCES or timeframe not in SIGNAL_TIMEFRAMES:
            raise ValueError('UNSUPPORTED_CALIBRATION_SLICE')
        base = {'source': source, 'symbol': symbol, 'timeframe': timeframe}
        settled = {**base, 'mode': 'STANDARD', 'labelStatus': 'LABELED', 'result': {'$in': ['WIN', 'LOSS']}}
        eligible_field = 'trainingEligible' if source == 'deriv' else 'observationEligible'
        verified_count = await self.db.signal_research_candidates.count_documents({**settled, eligible_field: True})
        pending_count = await self.db.signal_research_candidates.count_documents({**base, 'labelStatus': 'PENDING'})
        cursor = self.db.signal_calibration_runs.find(
            {**base, 'poolVersion': 'specialist-threshold-grid-v1'}, {'_id': 0},
        ).sort('generatedAt', -1).limit(500)
        runs = await cursor.to_list(500)
        latest = runs[0] if runs else None
        live_ready = source == 'deriv' and any(row.get('readyForLive') for row in runs)
        return {
            'source': source, 'symbol': symbol, 'timeframe': timeframe,
            'labeledPredictionRows': verified_count, 'pendingOutcomes': pending_count,
            'agentCount': len(build_profiles()), 'minimumSamplesPerAgent': 1000,
            'status': 'READY' if live_ready else latest.get('result', {}).get('status', 'NOT_READY') if latest else 'NOT_READY',
            'latestRun': latest, 'readyForLive': live_ready,
            'dataUse': 'TRAINING_AND_VALIDATION' if source == 'deriv' else 'OBSERVATION_ONLY_UNVERIFIED',
        }

    async def calibrate(self, source, symbol, timeframe):
        if source not in SOURCES or timeframe not in SIGNAL_TIMEFRAMES:
            raise ValueError('UNSUPPORTED_CALIBRATION_SLICE')
        eligible_field = 'trainingEligible' if source == 'deriv' else 'observationEligible'
        rows = await self.db.signal_research_candidates.find({
            'source': source, 'symbol': symbol, 'timeframe': timeframe,
            'mode': 'STANDARD', 'labelStatus': 'LABELED', 'result': {'$in': ['WIN', 'LOSS']}, eligible_field: True,
        }, {'_id': 0, 'entryEpoch': 1, 'confidence': 1, 'result': 1, 'agentTrainingMask': 1}).sort('entryEpoch', -1).limit(5000).to_list(5000)
        rows.reverse()
        profiles = build_profiles()
        profile_samples = [[] for _ in profiles]
        for row in rows:
            mask = row.get('agentTrainingMask', '')
            confidence = row.get('confidence')
            timestamp = row.get('entryEpoch')
            if not isinstance(confidence, (int, float)) or not isinstance(timestamp, (int, float)):
                continue
            sample = {'timestamp': timestamp, 'probability': float(confidence) / 100.0, 'correct': row['result'] == 'WIN'}
            for index, active in enumerate(mask[:len(profiles)]):
                if active == '1':
                    profile_samples[index].append(sample)

        generated_at = time.time()
        items = []
        for profile, samples in zip(profiles, profile_samples):
            result = calibrate_signal_confidence(samples)
            first_epoch = rows[0].get('entryEpoch', '') if rows else ''
            last_epoch = rows[-1].get('entryEpoch', '') if rows else ''
            dataset_version = f"{source}:{symbol}:{timeframe}:{profile['agentId']}:{len(samples)}:{first_epoch}:{last_epoch}"
            report = {
                'source': source, 'symbol': symbol, 'timeframe': timeframe,
                'agentId': profile['agentId'], 'profile': profile,
                'poolVersion': 'specialist-threshold-grid-v1',
                'datasetVersion': dataset_version, 'generatedAt': generated_at,
                'sampleCount': len(samples), 'dataUse': 'TRAINING_AND_VALIDATION' if source == 'deriv' else 'OBSERVATION_ONLY_UNVERIFIED',
                'calibrator': 'ISOTONIC_CHRONOLOGICAL_60_20_20', 'result': result,
                'readyForLive': source == 'deriv' and result.get('readyForLive') is True,
            }
            if source != 'deriv' and result['status'] == 'READY':
                report['result'] = {**result, 'status': 'OBSERVATION_ONLY', 'reason': 'SOURCE_NOT_INDEPENDENTLY_VERIFIED', 'readyForLive': False}
            await self.db.signal_calibration_runs.update_one(
                {'source': source, 'symbol': symbol, 'timeframe': timeframe, 'agentId': profile['agentId'], 'datasetVersion': dataset_version},
                {'$set': report}, upsert=True,
            )
            items.append(report)
        return {
            'status': 'CALIBRATION_COMPLETE' if any(item['sampleCount'] for item in items) else 'NOT_READY',
            'source': source, 'symbol': symbol, 'timeframe': timeframe,
            'agentCount': len(items),
            'sampleReadyAgentCount': sum(item['sampleCount'] >= 1000 for item in items),
            'validated90AgentCount': sum(item['result']['status'] == 'READY' for item in items),
            'readyForLive': source == 'deriv' and any(item['readyForLive'] for item in items), 'items': items,
        }

    async def emit(self, instrument, timeframe, entry, assessment, mode):
        seconds = TIMEFRAMES[timeframe]
        now = time.time()
        if assessment.get('direction') not in {'CALL', 'PUT'}:
            return False
        if await self._is_blacklisted(instrument['source'], instrument['symbol'], timeframe, now):
            return False
        if assessment['confidence'] < max(
            MIN_SIGNAL_CONFIDENCE,
            int(assessment.get('requiredConfidenceThreshold', self.settings['threshold'])),
        ):
            return False
        if instrument['source'] == 'deriv':
            model = assessment.get('validatedModel') or {}
            if model.get('promotionTier') == 'LIVE' and (
                not model.get('readyForLive')
                or not model.get('passesSignalThreshold')
                or float(model.get('confidence', 0.0)) < MIN_LIVE_MODEL_PROBABILITY
            ):
                return False
            model_ensemble = assessment.get('modelEnsemble') or {}
            if not model_ensemble.get('passed') and not model_ensemble.get('shadowEligible'):
                return False
        model_consensus = assessment.get('modelConsensus') or {}
        model_probabilities = {
            **(assessment.get('modelProbabilities') or {}),
            **(assessment.get('boostedTreeProbabilities') or {}),
        }
        model_directions = {
            name: 'CALL' if float(probability) > 0.5 else 'PUT' if float(probability) < 0.5 else 'NO_SIGNAL'
            for name, probability in model_probabilities.items()
            if name in {'sequence', 'tree', 'rule', 'xgboost', 'lightgbm', 'catboost'}
        }
        final_selection_score = float(assessment.get('finalSelectionScore', assessment.get('finalModelScore', assessment.get('confidence', 0))))
        formatted_signal = format_binary_signal(
            symbol=instrument['symbol'],
            direction=assessment['direction'],
            confidence=assessment['confidence'],
            timeframe_min=seconds // 60,
            entry_epoch=entry,
        )
        validation_tier = assessment.get('signalTier') or (
            'LIVE_VALIDATED' if instrument['source'] == 'deriv' else 'OBSERVATION_ONLY'
        )
        document = {
            'id': str(uuid.uuid4()), 'source': instrument['source'], 'symbol': instrument['symbol'], 'label': label_for(instrument),
            'timeframe': timeframe, 'timeframeSeconds': seconds, 'direction': assessment['direction'], 'confidence': assessment['confidence'],
            'mode': mode, 'status': 'PENDING', 'generatedAt': now, 'entryEpoch': entry, 'expiryEpoch': entry + seconds,
            'agreeing': assessment.get('agreeing', []), 'opposing': assessment.get('opposing', []), 'penalties': assessment.get('penalties', []),
            'votes': {k: {'direction': v['direction'], 'detail': v.get('detail', '')} for k, v in assessment.get('votes', {}).items()},
            'indicators': assessment.get('indicators', {}), 'higherTimeframe': assessment.get('higherTimeframe'),
            'is_otc': bool(instrument.get('is_otc') or assessment.get('is_otc')),
            'verification': 'OTC_FORECAST_UNVERIFIED' if instrument.get('is_otc') or assessment.get('is_otc') else 'CROSS_VALIDATED_DERIV' if instrument['source'] == 'market-qx-observer-v2' else 'DERIV_PROVIDER',
            'validationTier': validation_tier,
            'forecast': assessment.get('forecast'),
            'provenance': 'LIVE_DERIV_PUBLIC' if instrument['source'] == 'deriv' else 'OTC_FORECAST_UNVERIFIED' if instrument.get('is_otc') or assessment.get('is_otc') else 'BROWSER_OBSERVED_CROSS_VALIDATED',
            'threshold': max(
                MIN_SIGNAL_CONFIDENCE,
                85 if mode == 'OTC_FORECAST' else int(assessment.get(
                    'requiredConfidenceThreshold',
                    self.settings['threshold'] if mode == 'STANDARD' else self.settings['deepScanFloor'],
                )),
            ),
            'calibration': assessment.get('calibration'),
            'calibratedProfile': assessment.get('calibratedProfile'),
            'modelConsensus': model_consensus,
            'modelEnsemble': assessment.get('modelEnsemble'),
            'modelProbabilities': model_probabilities,
            'modelDirections': model_directions,
            'multiTimeframeTrend': assessment.get('multiTimeframeTrend'),
            'multiTimeframeFeatures': assessment.get('multiTimeframeFeatures'),
            'paperModelPrediction': assessment.get('paperModelPrediction'),
            'microMomentum': assessment.get('microMomentum'),
            'finalSelectionScore': final_selection_score,
            'binarySignalType': 'CALL' if assessment['direction'] == 'CALL' else 'PUT' if assessment['direction'] == 'PUT' else 'NO_SIGNAL',
            'validatedModel': assessment.get('validatedModel'),
            'modelStack': ['pytorch_lstm', 'xgboost', 'lightgbm', 'catboost', 'transformer', 'technical_confluence'],
            'modelConfidence': float((assessment.get('validatedModel') or {}).get('confidence', assessment['confidence'])),
            'formattedSignal': formatted_signal,
        }
        try:
            await self.db.live_signals.insert_one(document)
        except DuplicateKeyError:
            return False
        await self.db.signal_history.insert_one({**document, 'historyType': 'binary_signal', 'settled': False})
        await self.db.binary_signal_decisions.insert_one({
            'source': document['source'], 'symbol': document['symbol'], 'timeframe': document['timeframe'],
            'entryEpoch': document['entryEpoch'], 'direction': document['direction'], 'confidence': document['confidence'],
            'validationTier': document['validationTier'],
            'finalSelectionScore': document['finalSelectionScore'], 'modelConsensus': document['modelConsensus'],
            'generatedAt': now,
        })
        try:
            await self.db.model_observations.update_one(
                {'signalId': document['id']},
                {'$setOnInsert': {
                    'signalId': document['id'],
                    'source': document['source'],
                    'symbol': document['symbol'],
                    'timeframe': document['timeframe'],
                    'entryEpoch': document['entryEpoch'],
                    'expiryEpoch': document['expiryEpoch'],
                    'direction': document['direction'],
                    'confidence': document['confidence'],
                    'modelProbabilities': model_probabilities,
                    'modelDirections': model_directions,
                    'status': 'PENDING',
                    'generatedAt': now,
                }},
                upsert=True,
            )
        except Exception:
            logger.exception(
                'Model observation persistence failed for signal %s',
                document['id'],
            )
        self.last_signal_at = now
        await self.store.event('SIGNAL', 'Signal Engine', f"{document['label']} · {timeframe} · {assessment['direction']} · {assessment['confidence']}% · {mode} · entry {time.strftime('%H:%M', time.gmtime(entry))} UTC")
        return True

    async def record_candidate(self, instrument, timeframe, entry, assessment, qualified, gate, mode):
        seconds = TIMEFRAMES[timeframe]
        source = instrument['source']
        is_otc = bool(instrument.get('is_otc') or assessment.get('is_otc'))
        raw_confidence = assessment.get('rawConfidence', assessment['confidence'])
        training_assessment = {**assessment, 'confidence': raw_confidence}
        if is_otc:
            profiles = []
            agent_training_mask = ''
        else:
            profiles = build_profiles()
            agent_training_mask = build_training_mask(training_assessment, profiles)
        model_probabilities = {
            **(assessment.get('modelProbabilities') or {}),
            **(assessment.get('boostedTreeProbabilities') or {}),
        }
        document = {
            'source': source, 'symbol': instrument['symbol'], 'label': label_for(instrument),
            'timeframe': timeframe, 'timeframeSeconds': seconds, 'entryEpoch': entry,
            'expiryEpoch': entry + seconds, 'generatedAt': time.time(),
            'direction': assessment['direction'], 'confidence': raw_confidence,
            'liveConfidence': assessment['confidence'],
            'qualified': qualified, 'qualificationReason': gate, 'mode': mode,
            'agreeing': assessment.get('agreeing', []), 'opposing': assessment.get('opposing', []),
            'penalties': assessment.get('penalties', []),
            'votes': {k: {'direction': v['direction'], 'detail': v.get('detail', '')} for k, v in assessment.get('votes', {}).items()},
            'indicators': assessment.get('indicators', {}), 'higherTimeframe': assessment.get('higherTimeframe'),
            'multiTimeframeTrend': assessment.get('multiTimeframeTrend'),
            'multiTimeframeFeatures': assessment.get('multiTimeframeFeatures'),
            'modelProbabilities': model_probabilities,
            'boostedTreeProbabilities': assessment.get('boostedTreeProbabilities'),
            'modelDirections': {
                name: 'CALL' if float(probability) > 0.5 else 'PUT' if float(probability) < 0.5 else 'NO_SIGNAL'
                for name, probability in model_probabilities.items()
                if name in {'sequence', 'tree', 'rule', 'xgboost', 'lightgbm', 'catboost'}
            },
            'modelEnsemble': assessment.get('modelEnsemble'),
            'microMomentum': assessment.get('microMomentum'),
            'paperModelPrediction': assessment.get('paperModelPrediction'),
            'is_otc': is_otc,
            'verification': 'OTC_FORECAST_UNVERIFIED' if instrument.get('is_otc') or assessment.get('is_otc') else 'CROSS_VALIDATED_DERIV' if source == 'market-qx-observer-v2' else 'DERIV_PROVIDER',
            'forecast': assessment.get('forecast'),
            'provenance': 'LIVE_DERIV_PUBLIC' if source == 'deriv' else 'OTC_FORECAST_UNVERIFIED' if instrument.get('is_otc') or assessment.get('is_otc') else 'BROWSER_OBSERVED_CROSS_VALIDATED',
            'inputCompleteness': assessment.get('trainingInputCompleteness'),
            'agentPoolVersion': 'otc-time-series-observation-only-v1' if is_otc else 'specialist-threshold-grid-v1',
            'agentTrainingMask': agent_training_mask,
            'qualifiedAgentCount': agent_training_mask.count('1'),
            'calibration': assessment.get('calibration'),
            'calibratedProfile': assessment.get('calibratedProfile'),
            'labelStatus': 'PENDING', 'actualDirection': None, 'result': None,
            'trainingEligible': False, 'observationEligible': False,
        }
        key = {name: document[name] for name in ('source', 'symbol', 'timeframe', 'entryEpoch', 'mode')}
        await self.db.signal_research_candidates.update_one(key, {'$setOnInsert': document}, upsert=True)

    async def _record_market_outcome(self, signal, result, now):
        key = {
            'source': signal['source'],
            'symbol': signal['symbol'],
            'timeframe': signal['timeframe'],
        }
        selector = {**key}
        if result == 'LOSS':
            state = await self.db.signal_market_controls.find_one_and_update(
                selector,
                {
                    '$inc': {'consecutiveLosses': 1},
                    '$set': {'lastResult': result, 'updatedAt': now},
                    '$setOnInsert': key,
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        else:
            state = await self.db.signal_market_controls.find_one_and_update(
                selector,
                {
                    '$set': {
                        'consecutiveLosses': 0, 'lastResult': result,
                        'updatedAt': now,
                    },
                    '$setOnInsert': key,
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        streak = int((state or {}).get('consecutiveLosses', 0))
        blacklist_until = float((state or {}).get('blacklistedUntil') or 0)
        if result == 'LOSS' and streak >= 3 and blacklist_until <= now:
            blacklist_until = now + 24 * 60 * 60
            await self.db.signal_market_controls.update_one(
                selector,
                {'$set': {'blacklistedUntil': blacklist_until, 'updatedAt': now}},
            )
            self._pre_signals.pop((signal['source'], signal['symbol'], signal['timeframe']), None)
            logger.warning(
                'Blacklisted %s/%s/%s for 24h after 3 consecutive losses',
                signal['source'], signal['symbol'], signal['timeframe'],
            )

        symbol_key = {
            'source': signal['source'], 'symbol': signal['symbol'], 'timeframe': '*',
        }
        if result == 'LOSS':
            symbol_state = await self.db.signal_market_controls.find_one_and_update(
                symbol_key,
                {
                    '$inc': {'consecutiveLosses': 1},
                    '$set': {'lastResult': result, 'updatedAt': now},
                    '$setOnInsert': symbol_key,
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        else:
            symbol_state = await self.db.signal_market_controls.find_one_and_update(
                symbol_key,
                {
                    '$set': {
                        'consecutiveLosses': 0, 'lastResult': result,
                        'cooldownUntil': None, 'updatedAt': now,
                    },
                    '$setOnInsert': symbol_key,
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        symbol_streak = int((symbol_state or {}).get('consecutiveLosses', 0))
        cooldown_until = float((symbol_state or {}).get('cooldownUntil') or 0)
        if result == 'LOSS' and symbol_streak >= 2 and cooldown_until <= now:
            cooldown_until = now + 15 * 60
            await self.db.signal_market_controls.update_one(
                symbol_key,
                {'$set': {'cooldownUntil': cooldown_until, 'updatedAt': now}},
            )
            self._pre_signals.pop((signal['source'], signal['symbol'], signal['timeframe']), None)
            logger.warning(
                'Paused %s/%s for 15m after 2 consecutive losses',
                signal['source'], signal['symbol'],
            )

        until = max(blacklist_until, cooldown_until)
        self._blacklist_cache[(signal['source'], signal['symbol'], signal['timeframe'])] = (now, until)
        self._threshold_cache.pop((signal['source'], signal['symbol'], signal['timeframe']), None)
        verified_outcome = (
            signal.get('source') == 'deriv'
            and signal.get('entryCandleCompleteness') == 'PROVIDER_OHLC'
        ) or (
            signal.get('source') == 'market-qx-observer-v2'
            and signal.get('entryCandleCompleteness') == 'CROSS_VALIDATED'
        )
        if verified_outcome and result in {'WIN', 'LOSS'} and signal.get('direction') in {'CALL', 'PUT'}:
            risk_manager = getattr(self, 'risk_manager', None)
            if risk_manager:
                actual_direction = (
                    'UP' if signal['direction'] == 'CALL' else 'DOWN'
                )
                if result == 'LOSS':
                    actual_direction = 'DOWN' if actual_direction == 'UP' else 'UP'
                risk_record = risk_manager.evaluate_signal(
                    {
                        'direction': signal['direction'],
                        'confidence': float(signal.get('confidence', 0.0)) / 100.0,
                    },
                    actual_direction,
                )
                logger.info(
                    'Risk feedback applied to %s/%s/%s: %s',
                    signal['source'], signal['symbol'], signal['timeframe'],
                    risk_record['reward'],
                )
        if signal.get('id') or signal.get('signalId'):
            try:
                await self._record_model_observation_outcome(signal, result, now)
            except Exception:
                logger.exception(
                    'Model outcome persistence failed for signal %s',
                    signal.get('id') or signal.get('signalId'),
                )
        await self._record_online_outcome(signal, result)

    async def _record_model_observation_outcome(self, signal, result, now):
        signal_id = signal.get('id') or signal.get('signalId')
        if result == 'WIN':
            actual_direction = signal.get('direction')
        elif result == 'LOSS':
            actual_direction = 'PUT' if signal.get('direction') == 'CALL' else 'CALL'
        elif result == 'TIE':
            actual_direction = 'TIE'
        else:
            actual_direction = None
        observation = {
            'signalId': signal_id,
            'source': signal['source'],
            'symbol': signal['symbol'],
            'timeframe': signal['timeframe'],
            'entryEpoch': signal.get('entryEpoch'),
            'expiryEpoch': signal.get('expiryEpoch'),
            'direction': signal.get('direction'),
            'confidence': signal.get('confidence'),
            'modelProbabilities': signal.get('modelProbabilities', {}),
            'modelDirections': signal.get('modelDirections', {}),
            'status': result,
            'result': result,
            'actualDirection': actual_direction,
            'verifiedAt': now,
            'entryOpen': signal.get('entryOpen'),
            'exitClose': signal.get('exitClose'),
            'entryCandleCompleteness': signal.get('entryCandleCompleteness'),
        }
        collection = self.db.model_observations
        settled = await collection.update_one(
            {'signalId': signal_id, 'status': 'PENDING'},
            {'$set': observation},
        )
        changed = bool(
            getattr(settled, 'modified_count', 0)
            or getattr(settled, 'upserted_id', None)
        )
        if not changed:
            existing = await collection.find_one({'signalId': signal_id}, {'_id': 1, 'status': 1})
            if existing:
                return
            inserted = await collection.update_one(
                {'signalId': signal_id},
                {'$setOnInsert': observation},
                upsert=True,
            )
            changed = bool(getattr(inserted, 'upserted_id', None))
        if not changed or result not in {'WIN', 'LOSS'}:
            return
        verified_outcome = (
            signal.get('source') == 'deriv'
            and signal.get('entryCandleCompleteness') == 'PROVIDER_OHLC'
        ) or (
            signal.get('source') == 'market-qx-observer-v2'
            and signal.get('entryCandleCompleteness') == 'CROSS_VALIDATED'
        )
        if not verified_outcome:
            return

        probabilities = signal.get('modelProbabilities') or {}
        model_directions = signal.get('modelDirections') or {
            name: 'CALL' if float(probability) > 0.5 else 'PUT' if float(probability) < 0.5 else 'NO_SIGNAL'
            for name, probability in probabilities.items()
            if name in {'sequence', 'tree', 'rule', 'xgboost', 'lightgbm', 'catboost'}
        }
        calibration_collection = self.db.calibrations
        scope = {
            'source': signal['source'],
            'symbol': signal['symbol'],
            'timeframe': signal['timeframe'],
        }
        model_names = ('sequence', 'tree', 'rule', 'xgboost', 'lightgbm', 'catboost')
        for model_name in model_names:
            predicted = model_directions.get(model_name)
            calibration_update = {
                '$setOnInsert': {**scope, 'modelName': model_name},
            }
            if predicted in {'CALL', 'PUT'}:
                won = predicted == actual_direction
                calibration_update['$inc'] = {'wins' if won else 'losses': 1}
                calibration_update['$set'] = {'updatedAt': now}
            await calibration_collection.update_one(
                {**scope, 'modelName': model_name},
                calibration_update,
                upsert=True,
            )
        rows = await calibration_collection.find(scope, {'_id': 0}).to_list(20)
        outcomes = {
            row['modelName']: {'wins': row.get('wins', 0), 'losses': row.get('losses', 0)}
            for row in rows if row.get('modelName')
        }
        weights = EnsembleFusion.bayesian_weights(outcomes)
        booster_weights = EnsembleFusion.bayesian_weights(
            outcomes,
            {name: 1.0 / 3.0 for name in ('xgboost', 'lightgbm', 'catboost')},
        )
        for row in rows:
            model_name = row.get('modelName')
            if model_name in weights or model_name in booster_weights:
                total = int(row.get('wins', 0)) + int(row.get('losses', 0))
                update = {
                    'posteriorAccuracy': (int(row.get('wins', 0)) + 1) / (total + 2),
                }
                if model_name in weights:
                    update['weight'] = weights[model_name]
                if model_name in booster_weights:
                    update['boosterWeight'] = booster_weights[model_name]
                await calibration_collection.update_one(
                    {**scope, 'modelName': model_name}, {'$set': update},
                )
        self._bayesian_weight_cache.pop(
            (scope['source'], scope['symbol'], scope['timeframe']), None,
        )
        self._bayesian_booster_weight_cache.pop(
            (scope['source'], scope['symbol'], scope['timeframe']), None,
        )

    # ----- verification -------------------------------------------------------------
    async def verify_pending(self):
        now = time.time()
        await self._settle_paper_model_predictions(now)
        calibration_markets = set()
        candidates = await self.db.signal_research_candidates.find({'labelStatus': 'PENDING', 'expiryEpoch': {'$lte': now - 3}}, {'_id': 0}).limit(500).to_list(500)
        for candidate in candidates:
            candle = await self.db.market_candles.find_one({'source': candidate['source'], 'symbol': candidate['symbol'], 'timeframe': candidate['timeframe'], 'epoch': candidate['entryEpoch']}, {'_id': 0})
            update = None
            if candle:
                actual = 'UP' if candle['close'] > candle['open'] else 'DOWN' if candle['close'] < candle['open'] else 'FLAT'
                result = outcome(candidate['direction'], candle) if candidate['direction'] in ('CALL', 'PUT') else 'NO_SIGNAL'
                update = {
                    'labelStatus': 'LABELED', 'actualDirection': actual, 'result': result,
                    'verifiedAt': now, 'entryOpen': candle['open'], 'exitClose': candle['close'],
                    'entryCandleCompleteness': candle.get('completeness'),
                    'trainingEligible': candidate['source'] == 'deriv' and candidate.get('inputCompleteness') == 'PROVIDER_OHLC' and candle.get('completeness') == 'PROVIDER_OHLC' and result in ('WIN', 'LOSS'),
                    'observationEligible': candidate['source'] == 'market-qx-observer-v2' and candidate.get('inputCompleteness') == 'OBSERVED_UNVERIFIED' and candle.get('completeness') == 'OBSERVED_UNVERIFIED' and result in ('WIN', 'LOSS'),
                }
            elif now > candidate['expiryEpoch'] + 2 * candidate['timeframeSeconds'] + 30:
                update = {'labelStatus': 'VOID', 'result': 'NO_ENTRY_CANDLE_DATA', 'verifiedAt': now}
            if update:
                settled = await self.db.signal_research_candidates.update_one(
                    {'source': candidate['source'], 'symbol': candidate['symbol'], 'timeframe': candidate['timeframe'], 'entryEpoch': candidate['entryEpoch'], 'labelStatus': 'PENDING'},
                    {'$set': update},
                )
                if getattr(settled, 'modified_count', 0) and update.get('trainingEligible'):
                    calibration_markets.add((candidate['source'], candidate['symbol'], candidate['timeframe']))
                    if self.master_agent:
                        try:
                            await self.master_agent.record_settlement(
                                {**candidate, **update}, update['result'], update['actualDirection'],
                                update.get('entryCandleCompleteness'),
                            )
                        except Exception as exc:  # noqa: BLE001 - model persistence must not block settlement.
                            logger.warning('Master Agent update failed: %s', type(exc).__name__)
        for source, symbol, timeframe in calibration_markets:
            key = (source, symbol, timeframe)
            if now - self._calibration_last_run.get(key, 0) < 300:
                continue
            eligible_count = await self.db.signal_research_candidates.count_documents({
                'source': source, 'symbol': symbol, 'timeframe': timeframe,
                'mode': 'STANDARD', 'labelStatus': 'LABELED', 'result': {'$in': ['WIN', 'LOSS']},
                'trainingEligible': True,
            })
            if eligible_count < 500:
                continue
            self._calibration_last_run[key] = now
            try:
                await self.calibrate(source, symbol, timeframe)
            except Exception as exc:  # noqa: BLE001 - calibration refresh must not block outcome settlement.
                logger.warning('Automatic calibration failed for %s/%s/%s: %s', source, symbol, timeframe, type(exc).__name__)
        pending = await self.db.live_signals.find({'status': 'PENDING', 'expiryEpoch': {'$lte': now - 3}}, {'_id': 0}).limit(200).to_list(200)
        for signal in pending:
            candle = await self.db.market_candles.find_one({'source': signal['source'], 'symbol': signal['symbol'], 'timeframe': signal['timeframe'], 'epoch': signal['entryEpoch']}, {'_id': 0})
            update = None
            if candle:
                result = outcome(signal['direction'], candle)
                update = {'status': result, 'verifiedAt': now, 'entryOpen': candle['open'], 'exitClose': candle['close'], 'entryCandleCompleteness': candle.get('completeness'), 'verification': 'ENTRY_CANDLE_OPEN_VS_CLOSE'}
            elif now > signal['expiryEpoch'] + 2 * signal['timeframeSeconds'] + 30:
                update = {'status': 'VOID', 'verifiedAt': now, 'verification': 'NO_ENTRY_CANDLE_DATA'}
            if update:
                settled = await self.db.live_signals.update_one(
                    {'id': signal['id'], 'status': 'PENDING'},
                    {'$set': update},
                )
                if getattr(settled, 'modified_count', 0):
                    settled_signal = {**signal, **update}
                    if update['status'] in {'WIN', 'LOSS', 'TIE'}:
                        await self._record_market_outcome(settled_signal, update['status'], now)
                    elif update['status'] == 'VOID':
                        await self._record_model_observation_outcome(
                            settled_signal, update['status'], now,
                        )
                if update['status'] in ('WIN', 'LOSS'):
                    await self.store.event('SIGNAL', 'Signal Engine', f"{signal['label']} · {signal['timeframe']} · {signal['direction']} → {update['status']}")

    # ----- reporting ----------------------------------------------------------------
    def _source_filter(self, source):
        if source and source != 'all':
            return {'source': source}
        return {'source': {'$in': SOURCES}}

    async def live(self, source='all', limit=50):
        now = time.time()
        base = self._source_filter(source)
        upcoming = await self.db.live_signals.find({
            **base, 'status': 'PENDING', 'expiryEpoch': {'$gte': now - 3},
            'validationTier': 'LIVE_VALIDATED',
        }, {'_id': 0}).sort('entryEpoch', 1).limit(limit).to_list(limit)
        recent = await self.db.live_signals.find({**base, 'status': {'$ne': 'PENDING'}}, {'_id': 0}).sort('generatedAt', -1).limit(limit).to_list(limit)
        pre_signals = [
            {**signal, 'countdownSeconds': max(0, int(signal['entryEpoch'] - now + 0.999))}
            for signal in self._pre_signals.values()
            if (
                signal.get('validationTier') == 'LIVE_VALIDATED'
                and signal['entryEpoch'] > now
                and (source == 'all' or signal['source'] == source)
            )
        ]
        pre_signals.sort(key=lambda signal: (signal['entryEpoch'], -signal['setupConfidence']))
        return {'now': now, 'upcoming': upcoming, 'recent': recent, 'preSignals': pre_signals[:limit], 'engine': self.status()}

    async def history(self, source='all', limit=200, status=None):
        query = self._source_filter(source)
        if status:
            query['status'] = status
        rows = await self.db.live_signals.find(query, {'_id': 0}).sort('generatedAt', -1).limit(limit).to_list(limit)
        return {'items': rows}

    async def stats(self, source='all', hours=24):
        since = time.time() - hours * 3600
        base = {**self._source_filter(source), 'generatedAt': {'$gte': since}}
        pipeline = [{
            '$match': base,
        }, {
            '$group': {
                '_id': {
                    'source': '$source', 'timeframe': '$timeframe',
                    'status': '$status',
                    'validationTier': {'$ifNull': ['$validationTier', 'LEGACY_UNSPECIFIED']},
                },
                'n': {'$sum': 1},
            },
        }]
        rows = await self.db.live_signals.aggregate(pipeline).to_list(1000)
        def empty_bucket():
            return {'WIN': 0, 'LOSS': 0, 'TIE': 0, 'PENDING': 0, 'VOID': 0}

        by_tf, by_source, by_tier, overall = {}, {}, {}, empty_bucket()
        for row in rows:
            key = row['_id']
            for bucket in (
                by_tf.setdefault(key['timeframe'], empty_bucket()),
                by_source.setdefault(key['source'], empty_bucket()),
                by_tier.setdefault(key['validationTier'], empty_bucket()),
                overall,
            ):
                bucket[key['status']] = bucket.get(key['status'], 0) + row['n']

        def finish(bucket):
            decided = bucket['WIN'] + bucket['LOSS']
            return {**bucket, 'decided': decided, 'accuracy': round(bucket['WIN'] / decided * 100, 1) if decided else None}
        pairs = await self.db.live_signals.aggregate([{'$match': base}, {'$group': {'_id': {'source': '$source', 'symbol': '$symbol', 'label': '$label'}, 'win': {'$sum': {'$cond': [{'$eq': ['$status', 'WIN']}, 1, 0]}}, 'loss': {'$sum': {'$cond': [{'$eq': ['$status', 'LOSS']}, 1, 0]}}, 'pending': {'$sum': {'$cond': [{'$eq': ['$status', 'PENDING']}, 1, 0]}}, 'total': {'$sum': 1}}}, {'$sort': {'total': -1}}, {'$limit': 100}]).to_list(100)
        return {
            'hours': hours, 'source': source,
            'overall': finish(overall),
            'byTimeframe': {k: finish(v) for k, v in by_tf.items()},
            'bySource': {k: finish(v) for k, v in by_source.items()},
            'byValidationTier': {k: finish(v) for k, v in by_tier.items()},
            'byPair': [{'source': p['_id']['source'], 'symbol': p['_id']['symbol'], 'label': p['_id'].get('label') or p['_id']['symbol'], 'win': p['win'], 'loss': p['loss'], 'pending': p['pending'], 'total': p['total'], 'accuracy': round(p['win'] / (p['win'] + p['loss']) * 100, 1) if p['win'] + p['loss'] else None} for p in pairs],
            'measurement': 'ENTRY_CANDLE_OPEN_VS_CLOSE',
        }

    async def paper_model_stats(self, hours=720):
        since = time.time() - hours * 3600
        match = {'source': 'deriv', 'generatedAt': {'$gte': since}}
        rows = await self.db.deep_model_observations.aggregate([
            {'$match': match},
            {'$group': {'_id': '$status', 'count': {'$sum': 1}}},
        ]).to_list(20)
        counts = {row['_id']: row['count'] for row in rows}
        decided = int(counts.get('WIN', 0)) + int(counts.get('LOSS', 0))
        total_observations = sum(int(count) for count in counts.values())
        confusion = await self.db.deep_model_observations.aggregate([
            {'$match': {**match, 'actualDirection': {'$in': ['CALL', 'PUT']}}},
            {'$group': {
                '_id': {'predicted': '$predictedDirection', 'actual': '$actualDirection'},
                'count': {'$sum': 1},
            }},
        ]).to_list(10)
        return {
            'hours': hours,
            'source': 'deriv',
            'counts': counts,
            'totalObservations': total_observations,
            'decided': decided,
            'accuracy': round(counts.get('WIN', 0) / decided * 100.0, 2) if decided else None,
            'directionConfusion': [
                {'predicted': row['_id']['predicted'], 'actual': row['_id']['actual'], 'count': row['count']}
                for row in confusion
            ],
            'measurement': 'PROVIDER_OHLC_ENTRY_CANDLE_OPEN_VS_CLOSE',
        }

    async def execution_eligibility(self, signal_id):
        signal = await self.db.live_signals.find_one({'id': signal_id}, {'_id': 0})
        if not signal:
            return {
                'signalId': signal_id, 'eligible': False, 'executionEnabled': False,
                'submitted': False, 'reasons': ['SIGNAL_NOT_FOUND'],
            }
        reasons = []
        now = time.time()
        model = signal.get('validatedModel') or {}
        ensemble = signal.get('modelEnsemble') or {}
        if signal.get('source') != 'deriv':
            reasons.append('DERIV_SOURCE_REQUIRED')
        if signal.get('status') != 'PENDING' or float(signal.get('entryEpoch', 0)) <= now:
            reasons.append('SIGNAL_NOT_PENDING_FOR_FUTURE_ENTRY')
        if (
            model.get('promotionTier') != 'LIVE'
            or not model.get('readyForLive')
            or not model.get('passesSignalThreshold')
            or float(model.get('confidence', 0.0)) < MIN_LIVE_MODEL_PROBABILITY
        ):
            reasons.append('LIVE_TIER_MODEL_REQUIRED')
        directions = {
            signal.get('direction'),
            model.get('direction'),
            (ensemble.get('predictions') or {}).get('xgboost'),
            (ensemble.get('predictions') or {}).get('transformer'),
        }
        if (
            not ensemble.get('passed')
            or not all((ensemble.get('membersReady') or {}).get(name) for name in ('lstm', 'xgboost', 'transformer'))
            or len(directions) != 1
        ):
            reasons.append('PROMOTED_ENSEMBLE_AGREEMENT_REQUIRED')
        if await self._is_blacklisted(
            signal['source'], signal['symbol'], signal['timeframe'], now,
        ):
            reasons.append('RISK_COOLDOWN_ACTIVE')
        return {
            'signalId': signal_id,
            'eligible': not reasons,
            'executionEnabled': False,
            'submitted': False,
            'reasons': reasons,
            'guard': 'TIER2_LIVE_ENSEMBLE_AND_RISK_REQUIRED',
        }

    def status(self):
        now = time.time()
        idle = now - self.last_signal_at if self.last_signal_at else None
        return {
            'enabled': self.settings['enabled'], 'settings': dict(self.settings), 'cycles': self.cycles, 'lastCycle': self.last_cycle,
            'lastCycleMs': self.last_cycle_ms, 'evaluatedLastCycle': self.evaluated_last_cycle, 'lastSignalAt': self.last_signal_at,
            'marketEvaluation': {
                'freshMarkets': self.fresh_markets_last_cycle,
                'targets': self.evaluation_targets_last_cycle,
                'evaluatedMarkets': self.evaluated_markets_last_cycle,
                'activeEvaluations': self.active_market_evaluations,
            },
            'idleSeconds': idle, 'deepScan': {'active': idle is not None and idle >= self.settings['deepScanAfterMinutes'] * 60 or self.last_signal_at is None,
                                              'runs': self.deep_scan_runs, 'last': self.last_deep_scan, 'lastResult': self.deep_scan_last_result},
            'portfolio': dict(self.last_portfolio),
            'onlineLearning': {
                'workerRunning': self._training_task is not None and not self._training_task.done(),
                'queuedMarkets': len(self._online_training_queued),
                'queueSize': self._online_training_queue.qsize(),
                'triggerEveryVerifiedOutcomes': 50,
            },
            'scheduledModelRefresh': {
                'workerRunning': (
                    self._scheduled_training_task is not None
                    and not self._scheduled_training_task.done()
                ),
                'intervalSeconds': self.model_refresh_interval,
                'backfillTargetCandles': getattr(
                    self.deep_model_service, 'BACKFILL_CANDLES', 5_000,
                ),
                'lastStartedAt': self.last_scheduled_model_refresh,
                'lastResult': self.scheduled_model_refresh_result,
            },
            'automaticModelBootstrap': {
                'workerRunning': (
                    self._bootstrap_training_task is not None
                    and not self._bootstrap_training_task.done()
                ),
                'intervalSeconds': self.model_bootstrap_interval,
                'retryCooldownSeconds': self.model_bootstrap_cooldown,
                'minimumProviderCandles': getattr(
                    self.deep_model_service, 'MIN_RAW_CANDLES', 5_000,
                ),
                'minimumWarmupCandles': HISTORY_WARMUP_CANDLES,
                'lastScanAt': self.last_model_bootstrap_scan,
                'currentMarket': self.current_model_bootstrap_market,
                'lastResult': self.model_bootstrap_result,
            },
            'safety': {
                'economicCalendar': self.economic_calendar.status(now),
                'atrSpikeMultiple': 2.5,
                'bollingerWidthSpikeMultiple': 2.5,
                'blacklistConsecutiveLosses': 3,
                'blacklistCooldownHours': 24,
                'symbolLossCooldownConsecutiveLosses': 2,
                'symbolLossCooldownMinutes': 15,
            },
            'accuracyBoosters': {
                'oneMinuteHigherTimeframes': ['5m', '15m'],
                'higherTimeframeConflictPolicy': 'SUPPRESS',
                'liveModelEnsemble': {
                    'required': ['lstm', 'xgboost', 'transformer'],
                    'membersReady': {
                        'lstm': bool(self.deep_model_service and self.deep_model_service.models),
                        'xgboost': self._adapter_ready_for_live('xgboost'),
                        'transformer': self._adapter_ready_for_live('transformer'),
                    },
                    'agreementRequired': True,
                },
                'oneMinuteMicroMomentum': {
                    'enabled': True, 'windowSeconds': 10, 'minimumTicks': PRE_SIGNAL_MIN_TICKS,
                },
            },
            'marketContexts': {
                'active': len(self.market_registry.agents),
                'maximum': self.market_registry.max_agents,
            },
            'error': self.error, 'historyKeysLoaded': len(self.history_loaded),
        }

    async def check(self, observer_status=None, deriv_status=None):
        """Is the Quotex observer stream delivering usable signal input?"""
        now = time.time()
        per_source = {}
        for source in SOURCES:
            instruments = await self.db.market_instruments.find({'source': source}, {'_id': 0, 'symbol': 1, 'label': 1, 'latestEpoch': 1, 'latestPrice': 1}).to_list(500)
            fresh = [i for i in instruments if i.get('latestEpoch') and now - i['latestEpoch'] <= FRESHNESS]
            candles = {}
            for timeframe in dict.fromkeys(self.settings['timeframes'] + ['1m', '5m', '15m', '1h']):
                seconds = TIMEFRAMES[timeframe]
                fresh_symbols = [instrument['symbol'] for instrument in fresh]
                ready_symbols = []
                if fresh_symbols:
                    match = {
                        'source': source, 'symbol': {'$in': fresh_symbols},
                        'timeframe': timeframe, 'epoch': {'$lte': now - seconds},
                    }
                    if source == 'deriv':
                        match['completeness'] = 'PROVIDER_OHLC'
                    counts = await self.db.market_candles.aggregate([
                        {'$match': match},
                        {'$group': {'_id': '$symbol', 'closedCandles': {'$sum': 1}}},
                        {'$match': {'closedCandles': {'$gte': MIN_CANDLES}}},
                    ]).to_list(None)
                    ready_symbols = sorted(row['_id'] for row in counts)
                candles[timeframe] = {
                    'pairsReady': len(ready_symbols),
                    'required': MIN_CANDLES,
                    'minimumCandles': MIN_CANDLES,
                    'candidatePairs': len(fresh_symbols),
                    'readySymbols': ready_symbols,
                    'ready': bool(ready_symbols),
                }
            signals_1h = await self.db.live_signals.count_documents({'source': source, 'generatedAt': {'$gte': now - 3600}})
            signals_24h = await self.db.live_signals.count_documents({'source': source, 'generatedAt': {'$gte': now - 86400}})
            last = await self.db.live_signals.find_one({'source': source}, {'_id': 0, 'label': 1, 'timeframe': 1, 'direction': 1, 'confidence': 1, 'entryEpoch': 1, 'status': 1, 'generatedAt': 1}, sort=[('generatedAt', -1)])
            per_source[source] = {
                'pairsKnown': len(instruments), 'pairsFresh': len(fresh),
                'freshPairs': [{'symbol': i['symbol'], 'label': i.get('label') or i['symbol'], 'ageSeconds': round(now - i['latestEpoch'], 1), 'price': i.get('latestPrice')} for i in sorted(fresh, key=lambda x: -x['latestEpoch'])[:40]],
                'candlesReady': candles, 'signalsLastHour': signals_1h, 'signalsLast24h': signals_24h, 'lastSignal': last,
            }
        observer = per_source['market-qx-observer-v2']
        deriv = per_source['deriv']
        observer_receiving = bool(
            observer_status and observer_status.get('state') == 'DATA_RECEIVING'
        )
        deriv_receiving = bool(
            deriv_status
            and deriv_status.get('state') == 'DATA_RECEIVING'
            and deriv['pairsFresh'] > 0
        )
        receiving = observer_receiving or deriv_receiving
        stale = bool(
            observer_status and observer_status.get('state') == 'STALE'
            or deriv_status and deriv_status.get('state') == 'STALE'
        )
        verdict = 'RECEIVING' if receiving else 'STALE' if stale else 'NOT_CONNECTED'
        if receiving:
            has_ready_candles = any(
                row['pairsReady']
                for source in (observer, deriv)
                for row in source['candlesReady'].values()
            )
            if not has_ready_candles:
                verdict = 'RECEIVING_WARMING_UP'
            elif observer['signalsLastHour'] or deriv['signalsLastHour']:
                verdict = 'RECEIVING_SIGNALS_ACTIVE'
        return {
                'now': now,
                'verdict': verdict,
                'connectionStatus': 'CONNECTED' if receiving else 'NOT_CONNECTED',
                'observer': observer_status,
                'deriv': deriv_status,
                'sources': per_source,
                'engine': self.status(),
                'freshnessSeconds': FRESHNESS,
                'noFakeData': 'Signals require live closed candles; stale or missing input yields NO_SIGNAL.',
        }
