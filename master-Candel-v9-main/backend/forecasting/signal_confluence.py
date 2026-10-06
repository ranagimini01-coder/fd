"""Strict mathematical confluence gate for binary signal generation.

A signal is emitted only when independent indicator families agree, opposition is
limited, and the final calibrated confidence clears the dynamic market gate.
"""
from __future__ import annotations

import asyncio
import math
from typing import Any, Dict, List


class SignalConfluenceEngine:
    def __init__(self, min_agree: int = 3, max_oppose: int = 1, confidence_threshold: float = 0.72):
        self.min_agree = int(min_agree)
        self.max_oppose = int(max_oppose)
        self.confidence_threshold = float(confidence_threshold)

    @staticmethod
    def _ema(values: List[float], period: int) -> float:
        if not values:
            return 0.0
        alpha = 2.0 / (period + 1.0)
        result = values[0]
        for value in values[1:]:
            result = alpha * value + (1.0 - alpha) * result
        return result

    @staticmethod
    def _rsi(values: List[float], period: int = 14) -> float:
        if len(values) < period + 1:
            return 50.0
        deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
        gains = [max(delta, 0.0) for delta in deltas]
        losses = [max(-delta, 0.0) for delta in deltas]
        avg_gain = sum(gains[:period]) / max(1, period)
        avg_loss = sum(losses[:period]) / max(1, period)
        for idx in range(period, len(deltas)):
            avg_gain = ((avg_gain * (period - 1)) + gains[idx]) / period
            avg_loss = ((avg_loss * (period - 1)) + losses[idx]) / period
        if avg_loss <= 1e-12:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def _volatility_regime(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        closes = [float(c['close']) for c in candles if 'close' in c]
        highs = [float(c['high']) for c in candles if 'high' in c]
        lows = [float(c['low']) for c in candles if 'low' in c]
        if len(closes) < 5:
            return {'regime': 'NORMAL', 'threshold': 0.95, 'score': 1.0}

        recent = closes[-20:]
        recent_range = max(highs[-20:]) - min(lows[-20:]) if highs and lows else 0.0
        rel_range = recent_range / max(abs(recent[-1]), 1e-9)
        last_move = abs(recent[-1] - recent[-2]) if len(recent) >= 2 else 0.0
        mean_move = sum(abs(b - a) for a, b in zip(recent[:-1], recent[1:])) / max(1, len(recent) - 1)
        volatility_score = (last_move / max(mean_move, 1e-9)) if mean_move else 1.0

        if rel_range > 0.01 or volatility_score > 1.8:
            return {'regime': 'HIGH_VOLATILITY', 'threshold': 0.78, 'score': max(rel_range, volatility_score)}
        if rel_range > 0.005 or volatility_score > 1.3:
            return {'regime': 'ELEVATED', 'threshold': 0.75, 'score': max(rel_range, volatility_score)}
        return {'regime': 'NORMAL', 'threshold': 0.72, 'score': max(rel_range, volatility_score)}

    def dynamic_threshold(self, candles: List[Dict[str, Any]]) -> float:
        return float(self._volatility_regime(candles)['threshold'])

    def _build_votes(self, candles: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        closes = [float(c['close']) for c in candles if 'close' in c]
        highs = [float(c['high']) for c in candles if 'high' in c]
        lows = [float(c['low']) for c in candles if 'low' in c]
        opens = [float(c['open']) for c in candles if 'open' in c]

        if not closes or len(closes) < 30:
            return {'insufficient': {'direction': 'NEUTRAL', 'weight': 0.0, 'detail': 'insufficient candles'}}

        ema_short = self._ema(closes, 9)
        ema_long = self._ema(closes, 21)
        rsi = self._rsi(closes)
        last_close = closes[-1]
        last_open = opens[-1]
        recent_range = max(max(highs[-10:]) - min(lows[-10:]), 1e-9)
        body = abs(last_close - last_open)

        votes: Dict[str, Dict[str, Any]] = {}
        if ema_short > ema_long and last_close > ema_long:
            votes['ema_trend'] = {'direction': 'CALL', 'weight': 1.5, 'detail': 'ema_short > ema_long'}
        elif ema_short < ema_long and last_close < ema_long:
            votes['ema_trend'] = {'direction': 'PUT', 'weight': 1.5, 'detail': 'ema_short < ema_long'}
        else:
            votes['ema_trend'] = {'direction': 'NEUTRAL', 'weight': 0.0, 'detail': 'ema mixed'}

        bullish_trend = ema_short > ema_long and last_close > ema_long
        bearish_trend = ema_short < ema_long and last_close < ema_long

        if bullish_trend and rsi > 55:
            votes['rsi'] = {'direction': 'CALL', 'weight': 1.0, 'detail': f'rsi {rsi:.1f} confirms bullish continuation'}
        elif bearish_trend and rsi < 45:
            votes['rsi'] = {'direction': 'PUT', 'weight': 1.0, 'detail': f'rsi {rsi:.1f} confirms bearish continuation'}
        elif rsi > 70 and not bullish_trend:
            votes['rsi'] = {'direction': 'PUT', 'weight': 1.0, 'detail': f'rsi {rsi:.1f} overbought'}
        elif rsi < 30 and not bearish_trend:
            votes['rsi'] = {'direction': 'CALL', 'weight': 1.0, 'detail': f'rsi {rsi:.1f} oversold'}
        else:
            votes['rsi'] = {'direction': 'NEUTRAL', 'weight': 0.0, 'detail': f'rsi {rsi:.1f} neutral'}

        if body > 0.25 * recent_range and last_close > last_open:
            votes['momentum'] = {'direction': 'CALL', 'weight': 1.0, 'detail': 'strong bullish body'}
        elif body > 0.25 * recent_range and last_close < last_open:
            votes['momentum'] = {'direction': 'PUT', 'weight': 1.0, 'detail': 'strong bearish body'}
        else:
            votes['momentum'] = {'direction': 'NEUTRAL', 'weight': 0.0, 'detail': 'weak body'}

        if last_close > max(closes[-5:]) * 0.999:
            votes['breakout'] = {'direction': 'CALL', 'weight': 1.25, 'detail': 'near recent high'}
        elif last_close < min(closes[-5:]) * 1.001:
            votes['breakout'] = {'direction': 'PUT', 'weight': 1.25, 'detail': 'near recent low'}
        else:
            votes['breakout'] = {'direction': 'NEUTRAL', 'weight': 0.0, 'detail': 'mid-range'}

        return votes

    def analyze_market_signal(self, candles: List[Dict[str, Any]], postgres_service=None) -> Dict[str, Any]:
        if not candles or len(candles) < 30:
            return {'direction': 'NO_SIGNAL', 'confidence': 0.0, 'reason': 'INSUFFICIENT_CANDLES', 'votes': {}, 'agreeCount': 0, 'opposeCount': 0}

        volatility = self._volatility_regime(candles)
        threshold = float(volatility['threshold'])
        votes = self._build_votes(candles)
        call_weight = sum(v['weight'] for v in votes.values() if v['direction'] == 'CALL')
        put_weight = sum(v['weight'] for v in votes.values() if v['direction'] == 'PUT')
        agree_call = [name for name, value in votes.items() if value['direction'] == 'CALL']
        agree_put = [name for name, value in votes.items() if value['direction'] == 'PUT']

        direction = 'CALL' if call_weight > put_weight else 'PUT' if put_weight > call_weight else 'NO_SIGNAL'
        agree_count = len(agree_call) if direction == 'CALL' else len(agree_put) if direction == 'PUT' else 0
        oppose_count = len(agree_put) if direction == 'CALL' else len(agree_call) if direction == 'PUT' else 0

        if direction == 'NO_SIGNAL':
            result = {'direction': 'NO_SIGNAL', 'confidence': 0.0, 'reason': 'NO_DIRECTIONAL_CONSENSUS', 'votes': votes, 'agreeCount': 0, 'opposeCount': 0, 'threshold': threshold, 'volatility_regime': volatility['regime']}
            if postgres_service is not None and hasattr(postgres_service, 'log_signal_analysis'):
                try:
                    asyncio.get_running_loop().create_task(postgres_service.log_signal_analysis(source='confluence', symbol='market', timeframe='candles', entry_epoch=float(candles[-1].get('close', 0.0) if candles else 0.0), direction='NO_SIGNAL', confidence=0.0, feature_vector={'candles': len(candles)}, micro_momentum={'volatility_regime': volatility['regime']}, confluence=result, threshold=threshold))
                except RuntimeError:
                    pass
            return result

        net_score = abs(call_weight - put_weight) / max(1.0, call_weight + put_weight)
        confidence = min(0.99, max(0.5, 0.5 + (net_score * 0.5)))
        confidence = min(confidence, 0.99)

        gate = (
            direction != 'NO_SIGNAL'
            and confidence >= threshold
            and agree_count >= self.min_agree
            and oppose_count <= self.max_oppose
        )

        if not gate:
            result = {
                'direction': 'NO_SIGNAL',
                'confidence': float(confidence),
                'reason': 'CONFLUENCE_GATE_FAILED',
                'votes': votes,
                'agreeCount': agree_count,
                'opposeCount': oppose_count,
                'threshold': threshold,
                'volatility_regime': volatility['regime'],
            }
        else:
            result = {
                'direction': direction,
                'confidence': float(confidence),
                'reason': 'CONFLUENCE_GATE_PASSED',
                'votes': votes,
                'agreeCount': agree_count,
                'opposeCount': oppose_count,
                'threshold': threshold,
                'volatility_regime': volatility['regime'],
            }

        if postgres_service is not None and hasattr(postgres_service, 'log_signal_analysis'):
            try:
                asyncio.get_running_loop().create_task(
                    postgres_service.log_signal_analysis(
                        source='confluence',
                        symbol='market',
                        timeframe='candles',
                        entry_epoch=float(candles[-1].get('close', 0.0) if candles else 0.0),
                        direction=result['direction'],
                        confidence=float(result['confidence']),
                        feature_vector={'votes': votes, 'agreeCount': agree_count, 'opposeCount': oppose_count, 'candles': len(candles)},
                        micro_momentum={'volatility_regime': volatility['regime'], 'volatility_score': float(volatility['score'])},
                        confluence=result,
                        threshold=threshold,
                    )
                )
            except RuntimeError:
                pass

        return result

    def qualifies(self, assessment: Dict[str, Any]) -> bool:
        threshold = float(assessment.get('threshold', self.confidence_threshold))
        if not assessment or assessment.get('direction') == 'NO_SIGNAL':
            return False
        confidence = float(assessment.get('confidence', 0.0))
        agree = int(assessment.get('agreeCount', 0))
        oppose = int(assessment.get('opposeCount', 0))
        return confidence >= threshold and agree >= self.min_agree and oppose <= self.max_oppose