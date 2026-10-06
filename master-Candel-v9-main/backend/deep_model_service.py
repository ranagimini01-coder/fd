"""Chronological per-market LSTM training, calibration, and tiered promotion."""
from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import Any, Dict, Sequence

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.preprocessing import StandardScaler
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from feature_engineering import compute_indicator_bundle
from market_config import TIMEFRAMES

logger = logging.getLogger(__name__)


class _CandlestickSequenceModel(nn.Module):
    def __init__(self, input_size, hidden_size=64):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=2,
            batch_first=True,
            dropout=0.2,
        )
        self.head = nn.Sequential(nn.LayerNorm(hidden_size), nn.Linear(hidden_size, 1))

    def forward(self, values):
        sequence, _state = self.lstm(values)
        return self.head(sequence[:, -1, :]).squeeze(-1)


class DeepModelService:
    """Train and serve validated per-source/symbol/timeframe sequence models.

    Only verified Deriv provider OHLC candles are eligible for live promotion.
    Model artifacts are stored as JSON-compatible parameters, never pickled.
    """

    SEQUENCE_WINDOW = 200
    FEATURE_CONTEXT = 60
    FEATURE_HORIZON = 1
    MAX_SESSION_GAP_SECONDS = 3 * 24 * 60 * 60
    MIN_TRAIN_SAMPLES = 200
    MIN_VALIDATION_SAMPLES = 100
    MIN_CALIBRATION_SAMPLES = 100
    MIN_CALIBRATION_CHECK_SAMPLES = 100
    MIN_TEST_SAMPLES = 200
    MIN_RAW_CANDLES = 5_000
    BACKFILL_CANDLES = MIN_RAW_CANDLES
    ASSUMED_NET_PAYOUT = 0.80
    OBSERVATION_MIN_WIN_RATE = 0.58
    LIVE_MIN_WIN_RATE = 0.80
    MIN_LIVE_PROBABILITY = 0.85
    MAX_TEST_ECE = 0.10
    MODEL_VERSION = 'market-torch-lstm-tiered-isotonic-v6'
    FEATURE_NAMES = (
        'open_return', 'high_return', 'low_return', 'close_return',
        'tick_volume_log1p', 'tick_volume_available',
        'rsi_14', 'macd_normalized', 'macd_hist_normalized', 'atr_normalized',
        'bullish_order_block', 'bearish_order_block', 'order_block_distance_atr',
        'fvg_direction', 'fvg_size_atr', 'missing_intervals_log1p',
        'trend_regime', 'trend_direction', 'trend_efficiency_ratio',
        'volatility_regime_trending', 'volatility_regime_ranging',
        'volatility_to_atr_ratio', 'tick_velocity', 'tick_velocity_available',
        'tick_range_atr',
    )

    def __init__(self, db, deriv_service=None):
        self.db = db
        self.deriv_service = deriv_service
        self.models: Dict[tuple[str, str, str], Dict[str, Any]] = {}
        self.paper_models: Dict[tuple[str, str, str], Dict[str, Any]] = {}
        self.runtime_models: Dict[tuple[str, str, str], _CandlestickSequenceModel] = {}
        self.training_locks: Dict[tuple[str, str, str], asyncio.Lock] = {}

    async def initialize(self):
        await self.db.deep_model_registry.create_index(
            [('source', 1), ('symbol', 1), ('timeframe', 1)], unique=True,
        )
        await self.db.deep_model_training_runs.create_index(
            [('source', 1), ('symbol', 1), ('timeframe', 1), ('generatedAt', -1)],
        )
        rows = await self.db.deep_model_registry.find(
            {'$or': [{'readyForLive': True}, {'paperReady': True}]},
            {'_id': 0, 'source': 1, 'symbol': 1, 'timeframe': 1, 'artifact': 1, 'readyForLive': 1, 'paperReady': 1},
        ).to_list(1000)
        for row in rows:
            artifact = row.get('artifact')
            if artifact and self._valid_artifact(artifact):
                key = (row['source'], row['symbol'], row['timeframe'])
                if row.get('readyForLive'):
                    self.models[key] = artifact
                elif row.get('paperReady'):
                    self.paper_models[key] = artifact
                self.runtime_models[key] = self._load_model(artifact)
            elif artifact:
                logger.warning(
                    'Ignoring incompatible or invalid promoted model artifact for %s/%s/%s',
                    row.get('source'), row.get('symbol'), row.get('timeframe'),
                )

    @staticmethod
    def _valid_candle(row):
        try:
            values = [float(row[key]) for key in ('open', 'high', 'low', 'close')]
            epoch = int(row['epoch'])
        except (KeyError, TypeError, ValueError):
            return False
        return (
            epoch >= 0
            and all(math.isfinite(value) and value > 0 for value in values)
            and values[2] <= min(values[0], values[3])
            and values[1] >= max(values[0], values[3])
        )

    def _training_samples(self, candles: Sequence[Dict[str, Any]], source: str, symbol: str, timeframe: str):
        seconds = TIMEFRAMES[timeframe]
        ordered = sorted(
            (row for row in candles if row.get('completeness') == 'PROVIDER_OHLC' and self._valid_candle(row)),
            key=lambda row: int(row['epoch']),
        )
        first_target_index = (
            self.SEQUENCE_WINDOW + self.FEATURE_CONTEXT + self.FEATURE_HORIZON - 2
        )
        segments = []
        current = []
        for candle in ordered:
            if (
                current
                and int(candle['epoch']) - int(current[-1]['epoch']) > self.MAX_SESSION_GAP_SECONDS
            ):
                if len(current) > first_target_index:
                    segments.append(current)
                current = []
            current.append(candle)
        if len(current) > first_target_index:
            segments.append(current)

        sequences, targets = [], []
        for segment in segments:
            feature_rows = self._feature_rows(segment, timeframe)
            for target_index in range(first_target_index, len(segment)):
                target = segment[target_index]
                if float(target['close']) == float(target['open']):
                    continue
                sequences.append(feature_rows[target_index - self.SEQUENCE_WINDOW:target_index])
                targets.append(int(float(target['close']) > float(target['open'])))

        if not sequences:
            return (
                np.empty((0, self.SEQUENCE_WINDOW, len(self.FEATURE_NAMES)), dtype=np.float32),
                np.empty((0,), dtype=int),
                list(self.FEATURE_NAMES),
            )
        return np.asarray(sequences, dtype=np.float32), np.asarray(targets, dtype=int), list(self.FEATURE_NAMES)

    @classmethod
    def _feature_rows(cls, candles, timeframe=None):
        rows = []
        timeframe = timeframe or (candles[0].get('timeframe') if candles else None)
        seconds = TIMEFRAMES.get(timeframe)
        if seconds is None and len(candles) > 1:
            positive_gaps = [
                int(current['epoch']) - int(previous['epoch'])
                for previous, current in zip(candles, candles[1:])
                if int(current['epoch']) > int(previous['epoch'])
            ]
            seconds = min(positive_gaps) if positive_gaps else 60
        seconds = seconds or 60
        for index, candle in enumerate(candles):
            history = candles[max(0, index - cls.FEATURE_CONTEXT + 1):index + 1]
            indicator_history = history
            if len(indicator_history) < 20:
                indicator_history = [history[0]] * (20 - len(history)) + history
            indicators = compute_indicator_bundle(indicator_history)
            close = float(candle['close'])
            open_price = float(candle['open'])
            previous_close = float(history[-2]['close']) if len(history) > 1 else open_price
            scale = max(abs(previous_close), 1e-12)
            atr = max(float(indicators.get('atr', 0.0)), 1e-12)

            tick_volume = candle.get('tickVolume')
            if not isinstance(tick_volume, (int, float)) or not math.isfinite(tick_volume) or tick_volume < 0:
                tick_volume = candle.get('volume')
            volume_available = isinstance(tick_volume, (int, float)) and math.isfinite(tick_volume) and tick_volume >= 0
            volume_value = math.log1p(float(tick_volume)) if volume_available else 0.0

            body = close - open_price
            previous = history[-2] if len(history) > 1 else candle
            previous_body = float(previous['close']) - float(previous['open'])
            bullish_order_block = float(previous_body < 0 and body > 1.5 * atr)
            bearish_order_block = float(previous_body > 0 and body < -1.5 * atr)
            order_block_distance = 0.0
            if bullish_order_block or bearish_order_block:
                midpoint = (float(previous['high']) + float(previous['low'])) / 2.0
                order_block_distance = abs(close - midpoint) / atr

            fvg_direction, fvg_size = 0.0, 0.0
            if len(history) >= 3:
                two_back = history[-3]
                if float(candle['low']) > float(two_back['high']):
                    fvg_direction = 1.0
                    fvg_size = (float(candle['low']) - float(two_back['high'])) / atr
                elif float(candle['high']) < float(two_back['low']):
                    fvg_direction = -1.0
                    fvg_size = (float(two_back['low']) - float(candle['high'])) / atr
            elapsed_seconds = (
                max(0, int(candle['epoch']) - int(history[-2]['epoch']))
                if len(history) > 1 else seconds
            )
            missing_intervals = max(0.0, elapsed_seconds / seconds - 1.0)
            trend_efficiency = 0.0
            if len(history) > 1:
                recent_closes = [float(row['close']) for row in history[-20:]]
                path_length = sum(
                    abs(current - previous)
                    for previous, current in zip(recent_closes, recent_closes[1:])
                )
                if path_length > 0:
                    trend_efficiency = abs(recent_closes[-1] - recent_closes[0]) / path_length
            trend_regime = float(trend_efficiency >= 0.35)
            short_ema = float(indicators.get('ema_5', close))
            long_ema = float(indicators.get('ema_21', close))
            trend_direction = 1.0 if short_ema > long_ema else -1.0 if short_ema < long_ema else 0.0
            tick_velocity = candle.get('tickVolume')
            if not isinstance(tick_velocity, (int, float)) or not math.isfinite(tick_velocity) or tick_velocity < 0:
                tick_velocity = candle.get('volume')
            tick_volume_available = (
                isinstance(tick_velocity, (int, float))
                and math.isfinite(tick_velocity)
                and tick_velocity >= 0
            )
            recent_ranges = [
                float(row['high']) - float(row['low']) for row in history[-20:]
            ]
            volatility_to_atr = (
                float(np.mean(recent_ranges)) / atr if recent_ranges else 0.0
            )

            rows.append([
                (open_price - previous_close) / scale,
                (float(candle['high']) - previous_close) / scale,
                (float(candle['low']) - previous_close) / scale,
                (close - previous_close) / scale,
                volume_value,
                float(volume_available),
                float(indicators.get('rsi_14', 50.0)) / 100.0,
                float(indicators.get('macd', 0.0)) / scale,
                float(indicators.get('macd_hist', 0.0)) / scale,
                atr / scale,
                bullish_order_block,
                bearish_order_block,
                order_block_distance,
                fvg_direction,
                fvg_size,
                math.log1p(missing_intervals),
                trend_regime,
                trend_direction,
                trend_efficiency,
                trend_regime,
                1.0 - trend_regime,
                volatility_to_atr,
                math.log1p(float(tick_velocity) / seconds) if tick_volume_available else 0.0,
                float(tick_volume_available),
                (float(candle['high']) - float(candle['low'])) / atr,
            ])
        return np.asarray(rows, dtype=np.float32)

    @staticmethod
    def _split_indices(sample_count: int, purge: int):
        train_end = int(sample_count * 0.55)
        validation_end = int(sample_count * 0.65)
        calibration_end = int(sample_count * 0.75)
        calibration_check_end = int(sample_count * 0.85)
        validation_start = min(sample_count, train_end + purge)
        calibration_start = min(sample_count, validation_end + purge)
        calibration_check_start = min(sample_count, calibration_end + purge)
        test_start = min(sample_count, calibration_check_end + purge)
        return (
            (0, train_end),
            (validation_start, validation_end),
            (calibration_start, calibration_end),
            (calibration_check_start, calibration_check_end),
            (test_start, sample_count),
        )

    @staticmethod
    def _brier(probabilities, labels):
        return float(np.mean((np.asarray(probabilities) - np.asarray(labels, dtype=float)) ** 2))

    @staticmethod
    def _ece(probabilities, labels, bins=10):
        probabilities = np.asarray(probabilities, dtype=float)
        labels = np.asarray(labels, dtype=int)
        if not len(labels):
            return None
        error = 0.0
        for index in range(bins):
            lower, upper = index / bins, (index + 1) / bins
            mask = (probabilities >= lower) & (probabilities <= upper if index == bins - 1 else probabilities < upper)
            if mask.any():
                error += float(mask.mean()) * abs(float(probabilities[mask].mean()) - float(labels[mask].mean()))
        return error

    @classmethod
    def _promotion_tier(cls, win_rate):
        expected_value = (
            float(win_rate) * cls.ASSUMED_NET_PAYOUT - (1.0 - float(win_rate))
        )
        if expected_value <= 0:
            return None, expected_value
        if win_rate >= cls.LIVE_MIN_WIN_RATE:
            return 'LIVE', expected_value
        if win_rate >= cls.OBSERVATION_MIN_WIN_RATE:
            return 'PAPER', expected_value
        return None, expected_value

    @staticmethod
    def _accuracy_lower_95(correct, count):
        if count <= 0:
            return 0.0
        z = 1.96
        rate = correct / count
        z2 = z * z
        denominator = 1 + z2 / count
        center = rate + z2 / (2 * count)
        margin = z * math.sqrt(rate * (1 - rate) / count + z2 / (4 * count * count))
        return max(0.0, (center - margin) / denominator)

    @staticmethod
    def _export_artifact(model, calibrator, mean, scale, feature_names, hidden_size=64):
        return {
            'version': DeepModelService.MODEL_VERSION,
            'model': 'pytorch_lstm',
            'hiddenSize': hidden_size,
            'featureNames': list(feature_names),
            'scalerMean': np.asarray(mean, dtype=float).tolist(),
            'scalerScale': np.asarray(scale, dtype=float).tolist(),
            'stateDict': {
                name: value.detach().cpu().numpy().astype(float).tolist()
                for name, value in model.state_dict().items()
            },
            'calibration': {
                'method': 'isotonic',
                'x': calibrator.X_thresholds_.astype(float).tolist(),
                'y': calibrator.y_thresholds_.astype(float).tolist(),
            },
        }

    def _fit_and_evaluate(self, features, labels, feature_names):
        features = np.asarray(features, dtype=np.float32)
        labels = np.asarray(labels, dtype=int)
        if features.ndim == 2:
            features = features[:, None, :]
        if features.ndim != 3 or features.shape[2] != len(feature_names):
            return {'status': 'NOT_READY', 'reason': 'INVALID_SEQUENCE_FEATURE_SHAPE'}
        if not np.isfinite(features).all() or not np.isin(labels, (0, 1)).all():
            return {'status': 'NOT_READY', 'reason': 'NONFINITE_FEATURES_OR_INVALID_LABELS'}
        purge = self.SEQUENCE_WINDOW + self.FEATURE_CONTEXT + self.FEATURE_HORIZON - 2
        train_bounds, validation_bounds, calibration_bounds, calibration_check_bounds, test_bounds = self._split_indices(len(labels), purge)
        train_start, train_end = train_bounds
        validation_start, validation_end = validation_bounds
        calibration_start, calibration_end = calibration_bounds
        calibration_check_start, calibration_check_end = calibration_check_bounds
        test_start, test_end = test_bounds
        train_x, train_y = features[train_start:train_end], labels[train_start:train_end]
        validation_x, validation_y = features[validation_start:validation_end], labels[validation_start:validation_end]
        calibration_x, calibration_y = features[calibration_start:calibration_end], labels[calibration_start:calibration_end]
        calibration_check_x = features[calibration_check_start:calibration_check_end]
        calibration_check_y = labels[calibration_check_start:calibration_check_end]
        test_x, test_y = features[test_start:test_end], labels[test_start:test_end]
        counts = {
            'train': len(train_y), 'validation': len(validation_y),
            'calibrationFit': len(calibration_y), 'calibrationCheck': len(calibration_check_y),
            'test': len(test_y), 'purgeSamples': purge,
        }

        if (
            len(train_y) < self.MIN_TRAIN_SAMPLES
            or len(validation_y) < self.MIN_VALIDATION_SAMPLES
            or len(calibration_y) < self.MIN_CALIBRATION_SAMPLES
            or len(calibration_check_y) < self.MIN_CALIBRATION_CHECK_SAMPLES
            or len(test_y) < self.MIN_TEST_SAMPLES
        ):
            return {'status': 'NOT_READY', 'reason': 'INSUFFICIENT_PURGED_CHRONOLOGICAL_SAMPLES', 'sampleCounts': counts}
        if any(len(np.unique(targets)) < 2 for targets in (train_y, validation_y, calibration_y, calibration_check_y, test_y)):
            return {'status': 'NOT_READY', 'reason': 'CHRONOLOGICAL_SPLIT_HAS_ONE_CLASS', 'sampleCounts': counts}

        scaler = StandardScaler()
        scaler.fit(train_x.reshape(-1, train_x.shape[-1]))
        scale = np.where(scaler.scale_ > 0, scaler.scale_, 1.0)

        def scale_sequences(values):
            normalized = (values - scaler.mean_[None, None, :]) / scale[None, None, :]
            return np.clip(normalized, -12.0, 12.0).astype(np.float32)

        train_values = scale_sequences(train_x)
        validation_values = scale_sequences(validation_x)
        calibration_values = scale_sequences(calibration_x)
        calibration_check_values = scale_sequences(calibration_check_x)
        test_values = scale_sequences(test_x)
        torch.manual_seed(17)
        model = _CandlestickSequenceModel(train_x.shape[-1])
        optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.001)
        loss_function = nn.BCEWithLogitsLoss()
        loader = DataLoader(
            TensorDataset(torch.from_numpy(train_values), torch.from_numpy(train_y.astype(np.float32))),
            batch_size=128,
            shuffle=True,
        )
        validation_tensor = torch.from_numpy(validation_values)
        best_state = None
        best_validation_brier = float('inf')
        patience = 0
        for _epoch in range(60):
            model.train()
            for batch_x, batch_y in loader:
                optimizer.zero_grad(set_to_none=True)
                loss = loss_function(model(batch_x), batch_y)
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
            model.eval()
            with torch.no_grad():
                validation_probabilities = torch.sigmoid(model(validation_tensor)).numpy()
            validation_brier = self._brier(validation_probabilities, validation_y)
            if validation_brier + 1e-6 < best_validation_brier:
                best_validation_brier = validation_brier
                best_state = {name: value.detach().clone() for name, value in model.state_dict().items()}
                patience = 0
            else:
                patience += 1
                if patience >= 8:
                    break
        if best_state is None:
            return {'status': 'NOT_READY', 'reason': 'SEQUENCE_TRAINING_FAILED', 'sampleCounts': counts}
        model.load_state_dict(best_state)
        model.eval()

        def predict(values):
            with torch.no_grad():
                return torch.sigmoid(model(torch.from_numpy(values))).numpy().astype(float)

        validation_probabilities = predict(validation_values)
        calibration_probabilities = predict(calibration_values)
        calibrator = IsotonicRegression(out_of_bounds='clip').fit(calibration_probabilities, calibration_y)
        calibration_check_raw = predict(calibration_check_values)
        calibration_check_calibrated = calibrator.predict(calibration_check_raw)
        calibration_check_raw_brier = self._brier(calibration_check_raw, calibration_check_y)
        calibration_check_brier = self._brier(calibration_check_calibrated, calibration_check_y)
        calibration_check_ece = self._ece(calibration_check_calibrated, calibration_check_y)
        calibration_pass = (
            len(calibrator.X_thresholds_) >= 2
            and calibration_check_brier < calibration_check_raw_brier
            and calibration_check_ece is not None
            and calibration_check_ece <= self.MAX_TEST_ECE
        )
        raw_test_probabilities = predict(test_values)
        calibrated_test_probabilities = calibrator.predict(raw_test_probabilities)
        predictions = calibrated_test_probabilities >= 0.5
        correct = int(np.sum(predictions == test_y))
        test_win_rate = correct / len(test_y)
        candidate_tier, test_expected_value = self._promotion_tier(test_win_rate)
        promotion_tier = candidate_tier if calibration_pass else None
        test_brier = self._brier(calibrated_test_probabilities, test_y)
        raw_test_brier = self._brier(raw_test_probabilities, test_y)
        baseline_probability = float(np.mean(train_y))
        baseline_brier = self._brier(np.full(len(test_y), baseline_probability), test_y)
        lower_bound = self._accuracy_lower_95(correct, len(test_y))
        ece = self._ece(calibrated_test_probabilities, test_y)
        live_ready = promotion_tier == 'LIVE'
        paper_ready = promotion_tier == 'PAPER'
        report = {
            'status': 'LIVE_READY' if live_ready else 'PAPER_READY' if paper_ready else 'BELOW_TIER_GATES',
            'reason': (
                'LIVE_TIER_GATES_PASSED' if live_ready else
                'OBSERVATION_TIER_GATES_PASSED' if paper_ready else
                'CALIBRATION_GATE_FAILED' if candidate_tier is not None and not calibration_pass else
                'OUT_OF_SAMPLE_WIN_RATE_OR_EXPECTED_VALUE_GATE_FAILED'
            ),
            'promotionTier': promotion_tier,
            'payoutAssumption': {
                'netPayoutOnWin': self.ASSUMED_NET_PAYOUT,
                'source': 'USER_SELECTED_ASSUMPTION_NOT_CONTRACT_OBSERVED',
                'expectedValueFormula': 'winRate * netPayoutOnWin - (1 - winRate)',
            },
            'tierGates': {
                'observationMinWinRate': self.OBSERVATION_MIN_WIN_RATE,
                'liveMinWinRate': self.LIVE_MIN_WIN_RATE,
                'requiresPositiveExpectedValue': True,
                'requiresChronologicalOutOfSampleTest': True,
                'requiresIndependentCalibrationCheck': True,
                'minimumTestSamples': self.MIN_TEST_SAMPLES,
            },
            'sampleCounts': counts,
            'candidateModels': {'pytorch_lstm': {'validationBrier': best_validation_brier}},
            'selectedModel': 'pytorch_lstm',
            'validation': {'validationBrier': best_validation_brier},
            'calibration': {
                'method': 'isotonic',
                'calibrationFitSamples': len(calibration_y),
                'checkRawBrier': calibration_check_raw_brier,
                'checkCalibratedBrier': calibration_check_brier,
                'checkECE': calibration_check_ece,
                'passed': calibration_pass,
            },
            'test': {
                'accuracy': test_win_rate,
                'winRate': test_win_rate,
                'expectedValuePerUnitStake': test_expected_value,
                'accuracyLower95': lower_bound,
                'brier': test_brier,
                'rawBrier': raw_test_brier,
                'naiveBaselineBrier': baseline_brier,
                'ece': ece,
            },
            'promotionGates': {
                'tieredWinRateAndExpectedValue': candidate_tier is not None,
                'independentCalibrationCheck': calibration_pass,
            },
        }
        if promotion_tier is not None:
            report['artifact'] = self._export_artifact(model, calibrator, scaler.mean_, scale, feature_names)
        return report

    async def train_market(self, source, symbol, timeframe):
        if source != 'deriv' or timeframe not in TIMEFRAMES:
            return {'status': 'NOT_READY', 'reason': 'VERIFIED_DERIV_SOURCE_REQUIRED'}
        key = (source, symbol, timeframe)
        lock = self.training_locks.setdefault(key, asyncio.Lock())
        async with lock:
            seconds = TIMEFRAMES[timeframe]
            async def load_rows():
                rows = await self.db.market_candles.find({
                    'source': 'deriv', 'symbol': symbol, 'timeframe': timeframe,
                    'completeness': 'PROVIDER_OHLC', 'epoch': {'$lte': time.time() - seconds},
                }, {'_id': 0}).sort('epoch', -1).limit(self.BACKFILL_CANDLES).to_list(self.BACKFILL_CANDLES)
                rows.reverse()
                return rows

            rows = await load_rows()
            backfill = {'status': 'NOT_NEEDED', 'requestedCandles': 0}
            if len(rows) < self.BACKFILL_CANDLES:
                if self.deriv_service is None:
                    backfill = {
                        'status': 'UNAVAILABLE',
                        'reason': 'DERIV_HISTORY_SERVICE_NOT_CONFIGURED',
                        'requestedCandles': self.BACKFILL_CANDLES,
                        'providerCandlesAvailable': len(rows),
                    }
                else:
                    try:
                        await self.deriv_service.history(
                            symbol, timeframe, count=self.BACKFILL_CANDLES, force=True,
                        )
                        rows = await load_rows()
                        backfill = {
                            'status': 'COMPLETE' if len(rows) >= self.BACKFILL_CANDLES else 'INSUFFICIENT_PROVIDER_HISTORY',
                            'requestedCandles': self.BACKFILL_CANDLES,
                            'providerCandlesAvailable': len(rows),
                        }
                    except Exception as exc:  # noqa: BLE001 - no model is trained from unverified fallback data.
                        backfill = {
                            'status': 'FAILED',
                            'reason': getattr(exc, 'code', type(exc).__name__),
                            'error': str(exc),
                            'requestedCandles': self.BACKFILL_CANDLES,
                            'providerCandlesAvailable': len(rows),
                        }
            features, labels, feature_names = self._training_samples(rows, source, symbol, timeframe)
            generated_at = time.time()
            report = await asyncio.to_thread(self._fit_and_evaluate, features, labels, feature_names)
            report.update({
                'source': source, 'symbol': symbol, 'timeframe': timeframe,
                'generatedAt': generated_at, 'closedProviderCandles': len(rows),
                'featureCount': len(feature_names), 'modelVersion': self.MODEL_VERSION,
                'backfill': backfill,
            })
            artifact = report.pop('artifact', None)
            await self.db.deep_model_training_runs.insert_one(dict(report))
            promotion_tier = report.get('promotionTier')
            has_test_result = int(report.get('sampleCounts', {}).get('test', 0)) >= self.MIN_TEST_SAMPLES
            if artifact is not None and promotion_tier in {'PAPER', 'LIVE'}:
                live_ready = promotion_tier == 'LIVE'
                paper_ready = promotion_tier == 'PAPER'
                await self.db.deep_model_registry.update_one(
                    {'source': source, 'symbol': symbol, 'timeframe': timeframe},
                    {'$set': {
                        'source': source, 'symbol': symbol, 'timeframe': timeframe,
                        'modelVersion': self.MODEL_VERSION,
                        'promotionTier': promotion_tier,
                        'readyForLive': live_ready,
                        'paperReady': paper_ready,
                        'trainedAt': generated_at, 'artifact': artifact, 'metrics': report,
                    }},
                    upsert=True,
                )
                if live_ready:
                    self.models[key] = artifact
                    self.paper_models.pop(key, None)
                else:
                    self.models.pop(key, None)
                    self.paper_models[key] = artifact
                self.runtime_models[key] = self._load_model(artifact)
            elif has_test_result:
                await self.db.deep_model_registry.update_one(
                    {'source': source, 'symbol': symbol, 'timeframe': timeframe},
                    {
                        '$set': {
                            'source': source, 'symbol': symbol, 'timeframe': timeframe,
                            'modelVersion': self.MODEL_VERSION,
                            'promotionTier': None, 'readyForLive': False, 'paperReady': False,
                            'trainedAt': generated_at, 'metrics': report,
                        },
                        '$unset': {'artifact': ''},
                    },
                    upsert=True,
                )
                self.models.pop(key, None)
                self.paper_models.pop(key, None)
                self.runtime_models.pop(key, None)
            return report

    def predict_candles(self, source, symbol, timeframe, candles):
        key = (source, symbol, timeframe)
        artifact = self.models.get(key)
        promotion_tier = 'LIVE' if artifact is not None else 'PAPER'
        if artifact is None:
            artifact = self.paper_models.get(key)
        seconds = TIMEFRAMES.get(timeframe)
        required_candles = self.SEQUENCE_WINDOW + self.FEATURE_CONTEXT - 1
        if (
            source != 'deriv' or artifact is None or seconds is None
            or len(candles) < required_candles
        ):
            return {'readyForLive': False, 'promotionTier': None, 'direction': 'NO_SIGNAL', 'reason': 'VALIDATED_MODEL_UNAVAILABLE'}
        window = candles[-required_candles:]
        if any(row.get('completeness') != 'PROVIDER_OHLC' for row in window):
            return {'readyForLive': False, 'promotionTier': promotion_tier, 'direction': 'NO_SIGNAL', 'reason': 'UNVERIFIED_PROVIDER_WINDOW'}
        try:
            epochs = [int(row['epoch']) for row in window]
        except (KeyError, TypeError, ValueError):
            return {'readyForLive': False, 'promotionTier': promotion_tier, 'direction': 'NO_SIGNAL', 'reason': 'INVALID_PROVIDER_TIMESTAMPS'}
        if any(
            current - previous <= 0 or current - previous > self.MAX_SESSION_GAP_SECONDS
            for previous, current in zip(epochs, epochs[1:])
        ):
            return {'readyForLive': False, 'promotionTier': promotion_tier, 'direction': 'NO_SIGNAL', 'reason': 'GAPPED_PROVIDER_WINDOW'}

        vector = self._feature_rows(window, timeframe)[-self.SEQUENCE_WINDOW:]
        if not np.isfinite(vector).all():
            return {'readyForLive': False, 'promotionTier': promotion_tier, 'direction': 'NO_SIGNAL', 'reason': 'INVALID_LIVE_FEATURES'}
        if vector.shape != (self.SEQUENCE_WINDOW, len(artifact['featureNames'])):
            return {'readyForLive': False, 'promotionTier': promotion_tier, 'direction': 'NO_SIGNAL', 'reason': 'INVALID_LIVE_FEATURE_SHAPE'}
        scale = np.asarray(artifact['scalerScale'], dtype=np.float32)
        scale = np.where(scale > 0, scale, 1.0)
        scaled = np.clip(
            (vector - np.asarray(artifact['scalerMean'], dtype=np.float32)) / scale,
            -12.0,
            12.0,
        ).astype(np.float32)
        model = self.runtime_models.get((source, symbol, timeframe))
        if model is None:
            model = self._load_model(artifact)
            self.runtime_models[(source, symbol, timeframe)] = model
        with torch.no_grad():
            logit = float(model(torch.from_numpy(scaled[None, :, :])).item())
            probability_up = 1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, logit))))
        calibration = artifact['calibration']
        calibrated_up = float(np.interp(probability_up, calibration['x'], calibration['y']))
        direction = 'CALL' if calibrated_up >= 0.5 else 'PUT'
        directional_probability = calibrated_up if direction == 'CALL' else 1.0 - calibrated_up
        return {
            'readyForLive': promotion_tier == 'LIVE',
            'promotionTier': promotion_tier,
            'direction': direction,
            'probabilityUp': calibrated_up,
            'confidence': round(directional_probability * 100.0, 2),
            'passesSignalThreshold': (
                promotion_tier == 'LIVE'
                and directional_probability >= self.MIN_LIVE_PROBABILITY
            ),
            'model': artifact['model'],
            'modelVersion': artifact['version'],
            'source': source, 'symbol': symbol, 'timeframe': timeframe,
        }

    async def infer_market(self, source, symbol, timeframe):
        seconds = TIMEFRAMES.get(timeframe)
        if seconds is None:
            return {'readyForLive': False, 'direction': 'NO_SIGNAL', 'reason': 'UNSUPPORTED_TIMEFRAME'}
        rows = await self.db.market_candles.find({
            'source': source, 'symbol': symbol, 'timeframe': timeframe,
            'completeness': 'PROVIDER_OHLC', 'epoch': {'$lte': time.time() - seconds},
        }, {'_id': 0}).sort('epoch', -1).limit(self.SEQUENCE_WINDOW + self.FEATURE_CONTEXT - 1).to_list(self.SEQUENCE_WINDOW + self.FEATURE_CONTEXT - 1)
        return self.predict_candles(source, symbol, timeframe, list(reversed(rows)))

    def status(self):
        return {
            'readyMarkets': [
                {'source': source, 'symbol': symbol, 'timeframe': timeframe, 'model': artifact['model'], 'version': artifact['version']}
                for (source, symbol, timeframe), artifact in sorted(self.models.items())
            ],
            'readyMarketCount': len(self.models),
            'paperReadyMarkets': [
                {'source': source, 'symbol': symbol, 'timeframe': timeframe, 'model': artifact['model'], 'version': artifact['version']}
                for (source, symbol, timeframe), artifact in sorted(self.paper_models.items())
            ],
            'paperReadyMarketCount': len(self.paper_models),
            'minimumSamples': {
                'train': self.MIN_TRAIN_SAMPLES,
                'validation': self.MIN_VALIDATION_SAMPLES,
                'test': self.MIN_TEST_SAMPLES,
            },
            'minimumSignalProbability': self.MIN_LIVE_PROBABILITY,
            'tierPolicy': {
                'observationMinWinRate': self.OBSERVATION_MIN_WIN_RATE,
                'liveMinWinRate': self.LIVE_MIN_WIN_RATE,
                'assumedNetPayout': self.ASSUMED_NET_PAYOUT,
                'payoutSource': 'USER_SELECTED_ASSUMPTION_NOT_CONTRACT_OBSERVED',
                'backfillTargetCandles': self.BACKFILL_CANDLES,
                'historicalEvaluation': 'PURGED_CHRONOLOGICAL_OUT_OF_SAMPLE',
            },
            'livePolicy': 'LIVE_TIER_MODELS_ONLY; observation-tier model predictions are shadow logged and never block signals',
        }

    async def evaluation_status(self):
        target = await self.db.deep_model_training_runs.aggregate([
            {
                '$match': {
                    'source': 'deriv',
                    'modelVersion': self.MODEL_VERSION,
                },
            },
            {'$group': {'_id': {'symbol': '$symbol', 'timeframe': '$timeframe'}}},
            {'$count': 'total'},
        ]).to_list(1)
        expected = int(target[0]['total']) if target else 0
        latest_reports = await self.db.deep_model_training_runs.aggregate([
            {
                '$match': {
                    'source': 'deriv',
                    'modelVersion': self.MODEL_VERSION,
                },
            },
            {'$sort': {'generatedAt': -1}},
            {
                '$group': {
                    '_id': {'symbol': '$symbol', 'timeframe': '$timeframe'},
                    'report': {'$first': '$$ROOT'},
                },
            },
            {'$replaceRoot': {'newRoot': '$report'}},
            {
                '$group': {
                    '_id': None,
                    'evaluated': {'$sum': 1},
                    'tier1': {
                        '$sum': {'$cond': [{'$in': ['$promotionTier', ['PAPER', 'LIVE']]}, 1, 0]},
                    },
                    'tier2': {
                        '$sum': {'$cond': [{'$eq': ['$promotionTier', 'LIVE']}, 1, 0]},
                    },
                    'rejected': {
                        '$sum': {'$cond': [{'$eq': ['$status', 'BELOW_TIER_GATES']}, 1, 0]},
                    },
                    'fullBackfills': {
                        '$sum': {'$cond': [{'$eq': ['$backfill.status', 'COMPLETE']}, 1, 0]},
                    },
                    'insufficientBackfills': {
                        '$sum': {'$cond': [{'$eq': ['$backfill.status', 'INSUFFICIENT_PROVIDER_HISTORY']}, 1, 0]},
                    },
                    'failedBackfills': {
                        '$sum': {'$cond': [{'$eq': ['$backfill.status', 'FAILED']}, 1, 0]},
                    },
                    'candlesLoaded': {'$sum': '$closedProviderCandles'},
                    'candlesMaximum': {'$max': '$closedProviderCandles'},
                },
            },
        ]).to_list(1)
        report = latest_reports[0] if latest_reports else {}
        evaluated = int(report.get('evaluated', 0))
        return {
            'expectedModels': expected,
            'evaluated': evaluated,
            'pending': max(0, expected - evaluated),
            'tier1Count': int(report.get('tier1', 0)),
            'tier2Count': int(report.get('tier2', 0)),
            'rejectedCount': int(report.get('rejected', 0)),
            'backfill': {
                'targetCandlesPerModel': self.BACKFILL_CANDLES,
                'fullTargetCount': int(report.get('fullBackfills', 0)),
                'insufficientProviderHistoryCount': int(report.get('insufficientBackfills', 0)),
                'failedCount': int(report.get('failedBackfills', 0)),
                'candlesLoaded': int(report.get('candlesLoaded', 0)),
                'maximumCandlesForOneModel': int(report.get('candlesMaximum', 0)),
                'providerLimit': 'Historical data availability varies by symbol and timeframe',
            },
        }

    @staticmethod
    def _valid_artifact(artifact):
        if not isinstance(artifact, dict):
            return False
        feature_names = artifact.get('featureNames')
        scaler_mean = artifact.get('scalerMean')
        scaler_scale = artifact.get('scalerScale')
        state_dict = artifact.get('stateDict')
        calibration = artifact.get('calibration')
        if (
            artifact.get('version') != DeepModelService.MODEL_VERSION
            or artifact.get('model') != 'pytorch_lstm'
            or not isinstance(artifact.get('hiddenSize'), int)
            or artifact.get('hiddenSize') < 1
            or not isinstance(feature_names, list)
            or feature_names != list(DeepModelService.FEATURE_NAMES)
            or not isinstance(scaler_mean, list)
            or len(scaler_mean) != len(DeepModelService.FEATURE_NAMES)
            or not isinstance(scaler_scale, list)
            or len(scaler_scale) != len(DeepModelService.FEATURE_NAMES)
            or not isinstance(state_dict, dict)
            or not state_dict
            or not isinstance(calibration, dict)
        ):
            return False
        calibration_x = calibration.get('x')
        calibration_y = calibration.get('y')
        if (
            not isinstance(calibration_x, list)
            or not isinstance(calibration_y, list)
            or len(calibration_x) < 2
            or len(calibration_x) != len(calibration_y)
        ):
            return False
        try:
            DeepModelService._load_model(artifact)
            mean = np.asarray(scaler_mean, dtype=float)
            scale = np.asarray(scaler_scale, dtype=float)
            x = np.asarray(calibration_x, dtype=float)
            y = np.asarray(calibration_y, dtype=float)
        except (KeyError, TypeError, ValueError, RuntimeError):
            return False
        return (
            np.isfinite(mean).all()
            and np.isfinite(scale).all() and (scale > 0).all()
            and np.isfinite(x).all() and np.isfinite(y).all()
            and ((y >= 0) & (y <= 1)).all()
            and (np.diff(x) >= 0).all()
        )

    @staticmethod
    def _load_model(artifact):
        model = _CandlestickSequenceModel(len(artifact['featureNames']), int(artifact['hiddenSize']))
        model.load_state_dict({
            name: torch.as_tensor(values, dtype=torch.float32)
            for name, values in artifact['stateDict'].items()
        })
        model.eval()
        return model
