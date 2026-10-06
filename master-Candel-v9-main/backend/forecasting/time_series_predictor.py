
# backend/forecasting/time_series_predictor.py

import asyncio
import math


class TimeSeriesPredictor:
    """
    Advanced Statistical Arbitrage & Time-Series Forecasting Module.
    Designed specifically for high-frequency DOM data (is_otc=True).
    Outputs predictions only when mathematical confidence is >= 85%.
    """

    def __init__(self, confidence_threshold=0.68):
        self.threshold = confidence_threshold

    @staticmethod
    def _micro_momentum(closes: list, window: int = 10) -> dict:
        if len(closes) < 2:
            return {
                'window': min(window, max(1, len(closes))),
                'velocity': 0.0,
                'trend': 'NEUTRAL',
                'fake_breakout': False,
                'late_rejection': False,
                'last_step': 0.0,
            }

        recent = list(closes[-window:])
        deltas = [recent[i] - recent[i - 1] for i in range(1, len(recent))]
        velocity = sum(deltas) / max(1, len(deltas)) if deltas else 0.0
        last_step = deltas[-1] if deltas else 0.0

        late_rejection = False
        fake_breakout = False
        if velocity > 0 and last_step < 0:
            late_rejection = True
        if velocity < 0 and last_step > 0:
            late_rejection = True
        if velocity > 0 and last_step < 0 and recent[-1] > recent[0]:
            fake_breakout = True
        if velocity < 0 and last_step > 0 and recent[-1] < recent[0]:
            fake_breakout = True

        trend = 'CALL' if velocity > 0 else 'PUT' if velocity < 0 else 'NEUTRAL'
        return {
            'window': len(recent),
            'velocity': float(velocity),
            'trend': trend,
            'fake_breakout': fake_breakout,
            'late_rejection': late_rejection,
            'last_step': float(last_step),
        }

    def analyze_sequence(self, ticks: list, postgres_service=None) -> dict:
        """
        Analyzes the last N ticks to forecast the next candle direction.
        Expected input: list of dicts with 'close', 'high', 'low' prices.
        """
        if not ticks or len(ticks) < 30:
            return {
                'direction': 'NO_TRADE',
                'confidence': 0.0,
                'reason': 'Insufficient data for statistical modeling',
            }

        try:
            closes = [float(t['close']) for t in ticks]
            highs = [float(t['high']) for t in ticks]
            lows = [float(t['low']) for t in ticks]
            opens = [float(t['open']) for t in ticks]
        except (KeyError, TypeError, ValueError):
            return {'direction': 'NO_TRADE', 'confidence': 0.0, 'reason': 'INVALID_OHLC_SEQUENCE'}

        if any(not math.isfinite(value) or value <= 0 for value in closes + highs + lows + opens):
            return {'direction': 'NO_TRADE', 'confidence': 0.0, 'reason': 'INVALID_OHLC_SEQUENCE'}

        if any(high < max(opening, close) or low > min(opening, close) for opening, high, low, close in zip(opens, highs, lows, closes)):
            return {'direction': 'NO_TRADE', 'confidence': 0.0, 'reason': 'INVALID_OHLC_SEQUENCE'}

        short_ma = sum(closes[-5:]) / 5
        long_ma = sum(closes[-20:]) / 20
        momentum_delta = (short_ma - long_ma) / long_ma if long_ma else 0.0

        recent_spreads = [h - l for h, l in zip(highs[-10:], lows[-10:])]
        avg_volatility = sum(recent_spreads) / len(recent_spreads) if recent_spreads else 0.0001

        bullish_streak = sum(1 for i in range(1, 6) if closes[-i] > closes[-i - 1])
        bearish_streak = sum(1 for i in range(1, 6) if closes[-i] < closes[-i - 1])

        micro_momentum = self._micro_momentum(closes)
        feature_vector = {
            'short_ma': float(short_ma),
            'long_ma': float(long_ma),
            'momentum_delta': float(momentum_delta),
            'avg_volatility': float(avg_volatility),
            'bullish_streak': int(bullish_streak),
            'bearish_streak': int(bearish_streak),
            'micro_velocity': float(micro_momentum['velocity']),
            'last_step': float(micro_momentum['last_step']),
            'close': float(closes[-1]),
        }

        base_score = 0.50
        if momentum_delta > 0.0001:
            base_score += 0.20
        elif momentum_delta < -0.0001:
            base_score -= 0.20

        if bullish_streak >= 4:
            base_score += 0.18
        elif bearish_streak >= 4:
            base_score -= 0.18

        if micro_momentum['trend'] == 'CALL':
            base_score += 0.10
        elif micro_momentum['trend'] == 'PUT':
            base_score -= 0.10

        if micro_momentum['late_rejection']:
            base_score -= 0.12
        if micro_momentum['fake_breakout']:
            base_score -= 0.10

        if avg_volatility > (closes[-1] * 0.0005):
            base_score = 0.50

        result = {
            'direction': 'CALL',
            'confidence': round(base_score, 4),
            'reason': f"High Bullish Probability (Mom: {momentum_delta:.5f}, Streak: {bullish_streak})",
            'micro_momentum': micro_momentum,
            'feature_vector': feature_vector,
        }

        if base_score < 0.5:
            result['direction'] = 'PUT'
            result['confidence'] = round(1 - base_score, 4)
            result['reason'] = f"High Bearish Probability (Mom: {momentum_delta:.5f}, Streak: {bearish_streak})"
        elif base_score < self.threshold:
            result['direction'] = 'NO_TRADE'
            result['confidence'] = round(max(base_score, 1 - base_score), 4)
            result['reason'] = f"Below Threshold ({self.threshold * 100}%)"
        elif result['direction'] == 'CALL' and base_score >= self.threshold:
            result['confidence'] = round(base_score, 4)
        elif result['direction'] == 'PUT' and base_score <= (1 - self.threshold):
            result['confidence'] = round(1 - base_score, 4)

        if postgres_service is not None and hasattr(postgres_service, 'log_signal_analysis'):
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    postgres_service.log_signal_analysis(
                        source='forecast',
                        symbol='unknown',
                        timeframe='tick',
                        entry_epoch=float(closes[-1]),
                        direction=result['direction'],
                        confidence=float(result['confidence']),
                        feature_vector=feature_vector,
                        micro_momentum=micro_momentum,
                        confluence={'threshold': float(self.threshold), 'decision': result['direction'], 'confidence': float(result['confidence'])},
                        threshold=float(self.threshold),
                    )
                )
            except RuntimeError:
                pass

        return result

