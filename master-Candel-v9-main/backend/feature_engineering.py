"""Step 2: Feature engineering and 50+ indicator pipeline.

The feature bundle is intentionally framework-neutral so it can drive:
- LSTM sequences
- Transformer attention windows
- XGBoost classifiers
- Random Forest classifiers
- MARL state encoders
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence, Tuple
import math

import numpy as np


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def _ema(values: Sequence[float], period: int) -> float:
    if not values:
        return 0.0
    alpha = 2.0 / (period + 1.0)
    current = float(values[0])
    for value in values[1:]:
        current = alpha * float(value) + (1.0 - alpha) * current
    return float(current)


def _ema_series(values: Sequence[float], period: int) -> np.ndarray:
    if not values:
        return np.asarray([], dtype=float)
    alpha = 2.0 / (period + 1.0)
    output = np.empty(len(values), dtype=float)
    output[0] = float(values[0])
    for index in range(1, len(values)):
        output[index] = alpha * float(values[index]) + (1.0 - alpha) * output[index - 1]
    return output


def _sma(values: Sequence[float], period: int) -> float:
    if not values:
        return 0.0
    window = list(values[-period:]) if period < len(values) else list(values)
    return float(sum(window) / len(window)) if window else 0.0


def _rsi(values: Sequence[float], period: int = 14) -> float:
    if len(values) < 2:
        return 50.0
    changes = np.diff(np.asarray(values, dtype=float))
    gains = np.clip(changes, 0.0, None)
    losses = np.clip(-changes, 0.0, None)
    avg_gain = float(np.mean(gains[:period])) if len(gains) >= period else float(np.mean(gains))
    avg_loss = float(np.mean(losses[:period])) if len(losses) >= period else float(np.mean(losses))
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def _macd(values: Sequence[float]) -> Tuple[float, float, float]:
    if len(values) < 26:
        return 0.0, 0.0, 0.0
    macd_series = _ema_series(values, 12) - _ema_series(values, 26)
    macd = float(macd_series[-1])
    signal = _ema(macd_series.tolist(), 9)
    hist = macd - signal
    return float(macd), float(signal), float(hist)


def _stochastic(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 14) -> Tuple[float, float]:
    available = min(len(highs), len(lows), len(closes))
    if available < period:
        return 50.0, 50.0
    k_values = []
    for end in range(period - 1, available):
        start = end - period + 1
        low = min(lows[start:end + 1])
        high = max(highs[start:end + 1])
        k = 50.0 if high == low else 100.0 * ((closes[end] - low) / (high - low))
        k_values.append(float(k))
    return k_values[-1], float(np.mean(k_values[-3:]))


def _bbands(values: Sequence[float], period: int = 20) -> Tuple[float, float, float, float, float]:
    if len(values) < period:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    window = np.asarray(values[-period:], dtype=float)
    mean = float(np.mean(window))
    std = float(np.std(window, ddof=0))
    upper = mean + (2.0 * std)
    lower = mean - (2.0 * std)
    width = upper - lower
    pct_b = 0.0 if width == 0 else float((values[-1] - lower) / width)
    return mean, upper, lower, width, pct_b


def _atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 14) -> float:
    if len(closes) < 2:
        return 0.0
    values = []
    for idx in range(1, len(closes)):
        prev_close = closes[idx - 1]
        true_range = max(float(highs[idx]) - float(lows[idx]), abs(float(highs[idx]) - prev_close), abs(float(lows[idx]) - prev_close))
        values.append(true_range)
    if not values:
        return 0.0
    return _ema(values, period)


def _compute_price_features(candles: Sequence[Dict[str, Any]]) -> Dict[str, float]:
    closes = np.asarray([_safe_float(c.get('close')) for c in candles], dtype=float)
    opens = np.asarray([_safe_float(c.get('open')) for c in candles], dtype=float)
    highs = np.asarray([_safe_float(c.get('high')) for c in candles], dtype=float)
    lows = np.asarray([_safe_float(c.get('low')) for c in candles], dtype=float)
    volumes = np.asarray([_safe_float(c.get('volume'), 1.0) for c in candles], dtype=float)

    if closes.size == 0:
        return {"empty": 1.0}

    latest_close = float(closes[-1])
    prev_close = float(closes[-2]) if closes.size > 1 else latest_close
    last_range = float(highs[-1] - lows[-1])
    body = float(closes[-1] - opens[-1])
    body_ratio = 0.0 if last_range == 0 else float(abs(body) / last_range)
    gap = float(opens[-1] - prev_close)
    slope_5 = float((closes[-1] - closes[-5]) / max(abs(closes[-5]), 1e-9)) if closes.size > 5 else 0.0
    slope_10 = float((closes[-1] - closes[-10]) / max(abs(closes[-10]), 1e-9)) if closes.size > 10 else 0.0
    slope_20 = float((closes[-1] - closes[-20]) / max(abs(closes[-20]), 1e-9)) if closes.size > 20 else 0.0
    return {
        "close": latest_close,
        "open": float(opens[-1]),
        "high": float(highs[-1]),
        "low": float(lows[-1]),
        "range": last_range,
        "body": body,
        "body_ratio": body_ratio,
        "gap": gap,
        "slope_5": slope_5,
        "slope_10": slope_10,
        "slope_20": slope_20,
        "volume": float(volumes[-1]),
        "volatility": float(np.std(closes[-20:])) if closes.size >= 20 else float(np.std(closes)),
        "trend_strength": float((closes[-1] - closes[0]) / max(abs(closes[0]), 1e-9)),
    }


def _market_regime_features(candles: Sequence[Dict[str, Any]]) -> Dict[str, float]:
    closes = [_safe_float(candle.get("close")) for candle in candles]
    highs = [_safe_float(candle.get("high")) for candle in candles]
    lows = [_safe_float(candle.get("low")) for candle in candles]
    if not closes:
        return {}

    recent_closes = closes[-20:]
    path_length = sum(abs(current - previous) for previous, current in zip(recent_closes, recent_closes[1:]))
    efficiency_ratio = (
        abs(recent_closes[-1] - recent_closes[0]) / path_length
        if path_length > 0 else 0.0
    )
    trend_regime = 1.0 if efficiency_ratio >= 0.35 else 0.0
    short_ema = _ema(closes, 5)
    long_ema = _ema(closes, 20)
    trend_direction = 1.0 if short_ema > long_ema else -1.0 if short_ema < long_ema else 0.0

    ranges = [high - low for high, low in zip(highs[-20:], lows[-20:])]
    atr = _atr(highs[-20:], lows[-20:], recent_closes)
    mean_range = float(np.mean(ranges)) if ranges else 0.0
    tick_volume = candles[-1].get("tickVolume", candles[-1].get("volume"))
    tick_volume = _safe_float(tick_volume, -1.0)
    elapsed = 60.0
    if len(candles) > 1:
        elapsed = max(
            1.0,
            _safe_float(candles[-1].get("epoch")) - _safe_float(candles[-2].get("epoch")),
        )
    tick_volume_available = tick_volume >= 0

    return {
        "trend_regime": trend_regime,
        "trend_direction": trend_direction,
        "trend_efficiency_ratio": float(efficiency_ratio),
        "volatility_regime_trending": trend_regime,
        "volatility_regime_ranging": 1.0 - trend_regime,
        "volatility_to_atr_ratio": mean_range / max(atr, 1e-12),
        "tick_velocity": math.log1p(tick_volume / elapsed) if tick_volume_available else 0.0,
        "tick_velocity_available": float(tick_volume_available),
        "tick_range_atr": ranges[-1] / max(atr, 1e-12) if ranges else 0.0,
    }


def compute_multi_timeframe_features(candle_sets: Dict[str, Sequence[Dict[str, Any]]]) -> Dict[str, float]:
    """Encode 1m/5m/15m trend regimes without substituting unavailable timeframes."""
    features: Dict[str, float] = {}
    directions = []
    for timeframe in ("1m", "5m", "15m"):
        candles = candle_sets.get(timeframe) or ()
        direction = 0.0
        if len(candles) >= 20:
            closes = [_safe_float(candle.get("close")) for candle in candles]
            short = _ema(closes, 5)
            long = _ema(closes, 20)
            direction = 1.0 if short > long else -1.0 if short < long else 0.0
        features[f"trend_{timeframe}"] = direction
        features[f"trend_{timeframe}_available"] = float(len(candles) >= 20)
        if len(candles) >= 20:
            directions.append(direction)

    available = len(directions) == 3
    aligned = available and len(set(directions)) == 1 and directions[0] != 0.0
    features["multi_timeframe_confluence"] = float(sum(directions) / 3.0) if available else 0.0
    features["multi_timeframe_aligned"] = float(aligned)
    features["multi_timeframe_available"] = float(available)
    return features


def compute_indicator_bundle(candles: Sequence[Dict[str, Any]]) -> Dict[str, float]:
    """Produces a 50+ indicator-style feature map for a candle window."""
    if not candles:
        return {"empty": 1.0}

    closes = np.asarray([_safe_float(c.get('close')) for c in candles], dtype=float)
    opens = np.asarray([_safe_float(c.get('open')) for c in candles], dtype=float)
    highs = np.asarray([_safe_float(c.get('high')) for c in candles], dtype=float)
    lows = np.asarray([_safe_float(c.get('low')) for c in candles], dtype=float)
    volumes = np.asarray([_safe_float(c.get('volume'), 1.0) for c in candles], dtype=float)

    if closes.size == 0:
        return {"empty": 1.0}

    price = _compute_price_features(candles)
    macd, macd_signal, macd_hist = _macd(closes.tolist())
    stoch_k, stoch_d = _stochastic(highs.tolist(), lows.tolist(), closes.tolist())
    bb_mean, bb_upper, bb_lower, bb_width, pct_b = _bbands(closes.tolist())
    atr = _atr(highs.tolist(), lows.tolist(), closes.tolist())
    rsi_7 = _rsi(closes.tolist(), 7)
    rsi_14 = _rsi(closes.tolist(), 14)
    rsi_21 = _rsi(closes.tolist(), 21)

    features: Dict[str, float] = {
        "ema_5": _ema(closes.tolist(), 5),
        "ema_8": _ema(closes.tolist(), 8),
        "ema_13": _ema(closes.tolist(), 13),
        "ema_21": _ema(closes.tolist(), 21),
        "ema_34": _ema(closes.tolist(), 34),
        "ema_55": _ema(closes.tolist(), 55),
        "sma_5": _sma(closes.tolist(), 5),
        "sma_8": _sma(closes.tolist(), 8),
        "sma_13": _sma(closes.tolist(), 13),
        "sma_21": _sma(closes.tolist(), 21),
        "sma_34": _sma(closes.tolist(), 34),
        "sma_55": _sma(closes.tolist(), 55),
        "close_vs_ema_21": float(closes[-1] - _ema(closes.tolist(), 21)),
        "close_vs_sma_20": float(closes[-1] - _sma(closes.tolist(), 20)),
        "close_vs_sma_50": float(closes[-1] - _sma(closes.tolist(), 50)),
        "rsi_7": rsi_7,
        "rsi_14": rsi_14,
        "rsi_21": rsi_21,
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_hist": macd_hist,
        "stoch_k": stoch_k,
        "stoch_d": stoch_d,
        "bb_mean": bb_mean,
        "bb_upper": bb_upper,
        "bb_lower": bb_lower,
        "bb_width": bb_width,
        "pct_b": pct_b,
        "atr": atr,
        "atr_ratio": float(atr / max(abs(closes[-1]), 1e-9)),
        "roc_3": float((closes[-1] - closes[-3]) / max(abs(closes[-3]), 1e-9)) if closes.size > 3 else 0.0,
        "roc_5": float((closes[-1] - closes[-5]) / max(abs(closes[-5]), 1e-9)) if closes.size > 5 else 0.0,
        "roc_10": float((closes[-1] - closes[-10]) / max(abs(closes[-10]), 1e-9)) if closes.size > 10 else 0.0,
        "roc_20": float((closes[-1] - closes[-20]) / max(abs(closes[-20]), 1e-9)) if closes.size > 20 else 0.0,
        "momentum_5": float(closes[-1] - closes[-5]),
        "momentum_10": float(closes[-1] - closes[-10]),
        "momentum_20": float(closes[-1] - closes[-20]),
        "price_change_1": float(closes[-1] - closes[-2]) if closes.size > 1 else 0.0,
        "price_change_3": float(closes[-1] - closes[-3]) if closes.size > 3 else 0.0,
        "volatility_std_10": float(np.std(closes[-10:])) if closes.size >= 10 else float(np.std(closes)),
        "volatility_std_20": float(np.std(closes[-20:])) if closes.size >= 20 else float(np.std(closes)),
        "range_high_low_ratio": float((highs[-1] - lows[-1]) / max(abs(closes[-1]), 1e-9)),
        "body_ratio": float(abs(closes[-1] - opens[-1]) / max(highs[-1] - lows[-1], 1e-9)),
        "upper_wick": float(highs[-1] - max(opens[-1], closes[-1])),
        "lower_wick": float(min(opens[-1], closes[-1]) - lows[-1]),
        "wicks_total": float((highs[-1] - max(opens[-1], closes[-1])) + (min(opens[-1], closes[-1]) - lows[-1])),
        "gap_to_prev_close": float(opens[-1] - closes[-2]) if closes.size > 1 else 0.0,
        "rolling_high_5": float(np.max(highs[-5:])),
        "rolling_low_5": float(np.min(lows[-5:])),
        "rolling_high_10": float(np.max(highs[-10:])),
        "rolling_low_10": float(np.min(lows[-10:])),
        "rolling_high_20": float(np.max(highs[-20:])),
        "rolling_low_20": float(np.min(lows[-20:])),
        "rolling_high_50": float(np.max(highs[-50:])),
        "rolling_low_50": float(np.min(lows[-50:])),
        "support_distance": float(abs(closes[-1] - np.min(lows[-50:]))),
        "resistance_distance": float(abs(closes[-1] - np.max(highs[-50:]))),
        "volume_sma_5": _sma(volumes.tolist(), 5),
        "volume_sma_10": _sma(volumes.tolist(), 10),
        "volume_sma_20": _sma(volumes.tolist(), 20),
        "volume_ratio_5": float(volumes[-1] / max(_sma(volumes.tolist(), 5), 1e-9)),
        "volume_ratio_10": float(volumes[-1] / max(_sma(volumes.tolist(), 10), 1e-9)),
        "close_above_open": float(1.0 if closes[-1] >= opens[-1] else 0.0),
        "close_below_open": float(1.0 if closes[-1] < opens[-1] else 0.0),
        "trend_up": float(1.0 if closes[-1] > closes[-3] else 0.0),
        "trend_down": float(1.0 if closes[-1] < closes[-3] else 0.0),
        "up_day": float(1.0 if closes[-1] > opens[-1] else 0.0),
        "down_day": float(1.0 if closes[-1] < opens[-1] else 0.0),
        "close_to_ema_gap": float(abs(closes[-1] - _ema(closes.tolist(), 21)) / max(abs(_ema(closes.tolist(), 21)), 1e-9)),
        "close_to_sma_gap": float(abs(closes[-1] - _sma(closes.tolist(), 21)) / max(abs(_sma(closes.tolist(), 21)), 1e-9)),
        "n_returns": float(np.mean(np.diff(closes[-10:])) if closes.size > 10 else 0.0),
        "return_skew": float(np.std(np.diff(closes[-20:])) if closes.size > 20 else 0.0),
        "directional_bias": float((closes[-1] - closes[0]) / max(abs(closes[0]), 1e-9)),
    }

    features.update(price)
    features.update(_market_regime_features(candles))
    return features


class FeatureEngineeringPipeline:
    """Prepare full feature bundles for sequence and tabular model consumers."""

    def __init__(self, sequence_window: int = 200, feature_horizon: int = 1):
        self.sequence_window = max(20, int(sequence_window))
        self.feature_horizon = max(1, int(feature_horizon))

    def build_bundle(self, candles: Sequence[Dict[str, Any]], symbol: str = "UNKNOWN", timeframe: str = "1m", source: str = "deriv") -> Dict[str, Any]:
        if not candles:
            raise ValueError("FeatureEngineeringPipeline requires at least one candle")

        feature_map = compute_indicator_bundle(candles)
        ordered = list(candles)
        closes = np.asarray([_safe_float(c.get('close')) for c in ordered], dtype=float)
        if len(closes) < self.sequence_window:
            raise ValueError(f"Need at least {self.sequence_window} candles for sequence features")

        sample_count = max(0, len(ordered) - self.sequence_window - self.feature_horizon + 1)
        sequence_rows = []
        labels = []
        for idx in range(sample_count):
            window = ordered[idx:idx + self.sequence_window]
            feature_row = compute_indicator_bundle(window)
            sequence_rows.append(feature_row)
            current_close = closes[idx + self.sequence_window - 1]
            future_close = closes[idx + self.sequence_window - 1 + self.feature_horizon]
            labels.append(1 if future_close > current_close else 0)

        feature_names = list(feature_row.keys()) if sequence_rows else list(feature_map.keys())
        tabular_matrix = np.asarray([[float(feature_row.get(name, 0.0)) for name in feature_names] for feature_row in sequence_rows], dtype=float)

        packet = {
            "symbol": symbol,
            "timeframe": timeframe,
            "source": source,
            "feature_names": feature_names,
            "features": feature_map,
            "tabular_matrix": tabular_matrix,
            "labels": labels,
            "sequence_rows": sequence_rows,
            "sequence_window": self.sequence_window,
            "feature_horizon": self.feature_horizon,
            "ml_ready": bool(tabular_matrix.size > 0),
            "feature_count": len(feature_names),
            "target_field": "next_close_up",
        }
        return packet

    def prepare_model_inputs(self, candles: Sequence[Dict[str, Any]], symbol: str = "UNKNOWN", timeframe: str = "1m", source: str = "deriv") -> Dict[str, Any]:
        bundle = self.build_bundle(candles, symbol=symbol, timeframe=timeframe, source=source)
        sequence_matrix = np.asarray([
            [float(row.get(name, 0.0)) for name in bundle["feature_names"]]
            for row in bundle["sequence_rows"][-self.sequence_window:]
        ], dtype=float)

        return {
            "feature_key": f"{source}:{symbol}:{timeframe}:{len(candles)}",
            "tabular": {
                "X": bundle["tabular_matrix"],
                "y": np.asarray(bundle["labels"], dtype=int),
                "feature_names": bundle["feature_names"],
            },
            "sequence": {
                "lstm": sequence_matrix,
                "transformer": sequence_matrix,
                "shape": list(sequence_matrix.shape),
            },
            "targets": {
                "lstm": np.asarray(bundle["labels"], dtype=int).tolist(),
                "transformer": np.asarray(bundle["labels"], dtype=int).tolist(),
                "xgboost": np.asarray(bundle["labels"], dtype=int).tolist(),
                "random_forest": np.asarray(bundle["labels"], dtype=int).tolist(),
                "marl": np.asarray(bundle["labels"], dtype=int).tolist(),
            },
            "metadata": {
                "symbol": symbol,
                "timeframe": timeframe,
                "source": source,
                "feature_count": bundle["feature_count"],
                "ml_ready": bundle["ml_ready"],
                "feature_horizon": self.feature_horizon,
                "sequence_window": self.sequence_window,
            },
        }


def build_feature_pipeline(sequence_window: int = 200, feature_horizon: int = 1) -> FeatureEngineeringPipeline:
    return FeatureEngineeringPipeline(sequence_window=sequence_window, feature_horizon=feature_horizon)
