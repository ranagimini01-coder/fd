"""Step 3: Market behaviour finder for trend, breakout, range, and regime detection.

This layer identifies the dominant behaviour of a market before model selection.
It is deliberately deterministic so the downstream LSTM/Transformer/XGBoost/RF/MARL
systems can consume a stable behavioural context alongside raw feature vectors.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence
import math

import numpy as np


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


class MarketBehaviourFinder:
    """Detects regime and behavioural quality for a candle window."""

    def __init__(self, lookback: int = 50):
        self.lookback = max(5, int(lookback))

    def _range_state(self, candles: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        closes = np.asarray([_safe_float(c.get('close')) for c in candles], dtype=float)
        highs = np.asarray([_safe_float(c.get('high')) for c in candles], dtype=float)
        lows = np.asarray([_safe_float(c.get('low')) for c in candles], dtype=float)
        if closes.size < 2:
            return {"regime": "UNKNOWN", "score": 0.0, "range_width": 0.0}
        recent_high = float(np.max(highs[-self.lookback:]))
        recent_low = float(np.min(lows[-self.lookback:]))
        range_width = recent_high - recent_low
        last_close = float(closes[-1])
        if range_width <= 0:
            return {"regime": "FLAT", "score": 0.0, "range_width": 0.0}
        position = (last_close - recent_low) / range_width
        if position < 0.35:
            regime = "LOW_RANGE"
            score = 1.0 - position
        elif position > 0.65:
            regime = "HIGH_RANGE"
            score = position
        else:
            regime = "MID_RANGE"
            score = 0.5
        return {"regime": regime, "score": float(score), "range_width": float(range_width)}

    def _trend_state(self, candles: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        closes = np.asarray([_safe_float(c.get('close')) for c in candles], dtype=float)
        if closes.size < 10:
            return {"direction": "NEUTRAL", "strength": 0.0, "bias": 0.0}
        recent = closes[-self.lookback:]
        short = np.mean(recent[-5:]) if recent.size >= 5 else np.mean(recent)
        medium = np.mean(recent[-10:]) if recent.size >= 10 else np.mean(recent)
        long = np.mean(recent[-20:]) if recent.size >= 20 else np.mean(recent)
        bias = (short - long) / max(abs(long), 1e-9)
        if short > medium > long:
            direction = "UPTREND"
            strength = min(1.0, max(0.0, bias))
        elif short < medium < long:
            direction = "DOWNTREND"
            strength = min(1.0, max(0.0, -bias))
        else:
            direction = "NEUTRAL"
            strength = 0.0
        return {"direction": direction, "strength": float(strength), "bias": float(bias)}

    def _breakout_state(self, candles: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        highs = np.asarray([_safe_float(c.get('high')) for c in candles], dtype=float)
        lows = np.asarray([_safe_float(c.get('low')) for c in candles], dtype=float)
        closes = np.asarray([_safe_float(c.get('close')) for c in candles], dtype=float)
        if closes.size < 5:
            return {"breakout": "UNKNOWN", "probability": 0.0, "direction": "NONE"}
        recent_high = float(np.max(highs[-self.lookback:]))
        recent_low = float(np.min(lows[-self.lookback:]))
        latest_close = float(closes[-1])
        last_high = float(highs[-1])
        last_low = float(lows[-1])

        if latest_close > recent_high and last_high > recent_high:
            return {"breakout": "UP_BREAKOUT", "probability": 0.9, "direction": "UP"}
        if latest_close < recent_low and last_low < recent_low:
            return {"breakout": "DOWN_BREAKOUT", "probability": 0.9, "direction": "DOWN"}
        if latest_close > recent_high * 0.995:
            return {"breakout": "TESTING_UPPER_BAND", "probability": 0.6, "direction": "UP"}
        if latest_close < recent_low * 1.005:
            return {"breakout": "TESTING_LOWER_BAND", "probability": 0.6, "direction": "DOWN"}
        return {"breakout": "CONSOLIDATION", "probability": 0.2, "direction": "NONE"}

    def _volatility_regime(self, candles: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        closes = np.asarray([_safe_float(c.get('close')) for c in candles], dtype=float)
        if closes.size < 2:
            return {"regime": "UNKNOWN", "score": 0.0}
        returns = np.diff(closes)
        std = float(np.std(returns[-self.lookback:])) if returns.size >= self.lookback else float(np.std(returns))
        mean_abs = float(np.mean(np.abs(returns[-self.lookback:]))) if returns.size >= self.lookback else float(np.mean(np.abs(returns)))
        score = std / max(mean_abs, 1e-9)
        if score > 1.2:
            regime = "HIGH_VOLATILITY"
        elif score > 0.6:
            regime = "MODERATE_VOLATILITY"
        else:
            regime = "LOW_VOLATILITY"
        return {"regime": regime, "score": float(score)}

    def scan(self, candles: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        if not candles:
            return {"status": "NO_DATA", "regime": "UNKNOWN", "quality": 0.0}

        trend = self._trend_state(candles)
        range_state = self._range_state(candles)
        breakout = self._breakout_state(candles)
        volatility = self._volatility_regime(candles)

        quality_score = 0.0
        quality_score += 30.0 * trend["strength"]
        quality_score += 20.0 * range_state["score"]
        quality_score += 25.0 * breakout["probability"]
        quality_score += 25.0 * min(1.0, volatility["score"] / 2.0)
        quality_score = max(0.0, min(100.0, quality_score))

        if trend["direction"] == "UPTREND" and breakout["direction"] == "UP":
            behaviour = "TRENDING_BULLISH_BREAKOUT"
        elif trend["direction"] == "DOWNTREND" and breakout["direction"] == "DOWN":
            behaviour = "TRENDING_BEARISH_BREAKOUT"
        elif range_state["regime"] in {"MID_RANGE", "LOW_RANGE", "HIGH_RANGE"}:
            behaviour = "RANGE_BOUND"
        else:
            behaviour = "UNCERTAIN"

        return {
            "status": "READY",
            "behaviour": behaviour,
            "trend": trend,
            "range_state": range_state,
            "breakout": breakout,
            "volatility": volatility,
            "quality_score": round(quality_score, 2),
            "market_phase": behaviour,
            "decision_ready": quality_score >= 60.0,
        }


def detect_market_behaviour(candles: Sequence[Dict[str, Any]], lookback: int = 50) -> Dict[str, Any]:
    return MarketBehaviourFinder(lookback=lookback).scan(candles)
