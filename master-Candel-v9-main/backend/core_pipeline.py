"""Composable candle-analysis stages for the Master Agent.

Scores are diagnostics and ranking features, not calibrated win probabilities.
OTC forecasts are explicitly observation-only and cannot self-train the model.
"""
import math
import statistics
import time

from forecasting.time_series_predictor import TimeSeriesPredictor
from master_agent import BASE_WEIGHTS
from signal_engine import evaluate as evaluate_confluence


class CorePipeline:
    def __init__(self, indicator_engine=None, min_quality_score=65, otc_predictor=None):
        self.indicator_engine = indicator_engine
        self.min_quality_score = max(0, min(100, int(min_quality_score)))
        self.otc_predictor = otc_predictor or TimeSeriesPredictor()

    @staticmethod
    def _valid_candle(candle):
        try:
            opening, high, low, close = (float(candle[key]) for key in ('open', 'high', 'low', 'close'))
        except (KeyError, TypeError, ValueError):
            return False
        return (
            all(math.isfinite(value) and value > 0 for value in (opening, high, low, close))
            and high >= max(opening, close)
            and low <= min(opening, close)
            and high >= low
        )

    @staticmethod
    def _pattern(candles):
        if not candles:
            return {'type': 'UNKNOWN', 'direction': 'NEUTRAL', 'patterns': []}
        candle = candles[-1]
        opening, high, low, close = (float(candle[key]) for key in ('open', 'high', 'low', 'close'))
        span = max(high - low, 1e-12)
        body = abs(close - opening)
        upper_wick = high - max(opening, close)
        lower_wick = min(opening, close) - low
        kind = 'BULLISH' if close > opening else 'BEARISH' if close < opening else 'DOJI'
        patterns = []
        if body / span <= 0.1:
            patterns.append('DOJI')
        if lower_wick >= max(body * 2, span * 0.55) and upper_wick <= span * 0.2:
            patterns.append('LONG_LOWER_WICK')
        if upper_wick >= max(body * 2, span * 0.55) and lower_wick <= span * 0.2:
            patterns.append('LONG_UPPER_WICK')
        if len(candles) > 1:
            previous = candles[-2]
            previous_open, previous_close = float(previous['open']), float(previous['close'])
            if close > opening and previous_close < previous_open and close >= previous_open and opening <= previous_close:
                patterns.append('BULLISH_ENGULFING')
            elif close < opening and previous_close > previous_open and close <= previous_open and opening >= previous_close:
                patterns.append('BEARISH_ENGULFING')
        direction = 'CALL' if kind == 'BULLISH' else 'PUT' if kind == 'BEARISH' else 'NEUTRAL'
        return {'type': kind, 'direction': direction, 'patterns': patterns}

    @staticmethod
    def _behavior(candles):
        if len(candles) < 3:
            return {
                'volatilityRatio': None, 'gapRatio': None, 'breakout': 'INSUFFICIENT_HISTORY',
                'falseBreakoutRisk': False, 'repetitionRate': 0.0,
            }
        current, previous = candles[-1], candles[-2]
        baseline = candles[-21:-1]
        ranges = [max(float(item['high']) - float(item['low']), 1e-12) for item in baseline]
        median_range = statistics.median(ranges) if ranges else 0.0
        current_range = float(current['high']) - float(current['low'])
        volatility_ratio = current_range / median_range if median_range > 0 else None
        gap = float(current['open']) - float(previous['close'])
        gap_ratio = abs(gap) / median_range if median_range > 0 else None
        prior_high = max(float(item['high']) for item in baseline) if baseline else float(previous['high'])
        prior_low = min(float(item['low']) for item in baseline) if baseline else float(previous['low'])
        close, high, low = float(current['close']), float(current['high']), float(current['low'])
        if high > prior_high and close <= prior_high:
            breakout, false_risk = 'FAILED_UPWARD_BREAK', True
        elif low < prior_low and close >= prior_low:
            breakout, false_risk = 'FAILED_DOWNWARD_BREAK', True
        elif close > prior_high:
            breakout, false_risk = 'CLOSE_CONFIRMED_UPWARD', False
        elif close < prior_low:
            breakout, false_risk = 'CLOSE_CONFIRMED_DOWNWARD', False
        else:
            breakout, false_risk = 'NO_BREAKOUT', False
        signatures = []
        for item in candles[-20:]:
            span = max(float(item['high']) - float(item['low']), 1e-12)
            body_ratio = round((float(item['close']) - float(item['open'])) / span, 1)
            signatures.append((body_ratio, round(span / max(float(item['close']), 1e-12) * 10000, 1)))
        repetition_rate = max((signatures.count(value) / len(signatures) for value in set(signatures)), default=0.0)
        return {
            'volatilityRatio': round(volatility_ratio, 4) if volatility_ratio is not None else None,
            'gapRatio': round(gap_ratio, 4) if gap_ratio is not None else None,
            'gapDirection': 'GAP_UP' if gap > 0 else 'GAP_DOWN' if gap < 0 else 'NONE',
            'breakout': breakout, 'falseBreakoutRisk': false_risk,
            'repetitionRate': round(repetition_rate, 4),
            'repetitionStatus': 'REPEATING_PRICE_ACTION_CANDIDATE' if repetition_rate >= 0.6 else 'NO_STRONG_REPETITION',
            'algorithmDetection': 'PRICE_ACTION_REPETITION_ONLY_NOT_BROKER_ALGORITHM_IDENTIFICATION',
        }

    def _indicators(self, candles):
        if self.indicator_engine is not None:
            result = self.indicator_engine(candles)
        else:
            try:
                from market_analysis import indicators
                result = indicators(candles)
            except Exception as exc:  # noqa: BLE001 - indicator failure must fail closed.
                return {'state': 'UNAVAILABLE', 'count': 0, 'values': {}, 'error': type(exc).__name__}
        result = result or {}
        values = result.get('values') if isinstance(result, dict) else None
        values = values if isinstance(values, dict) else {}
        return {**result, 'values': values, 'count': len(values), 'indicatorCoverage': '50_PLUS' if len(values) >= 50 else 'PARTIAL'}

    def evaluate(self, source, symbol, timeframe, candles, timeframe_seconds, learned_weights=None, now=None, is_otc=False):
        now = time.time() if now is None else float(now)
        ordered = list(candles or [])
        errors = [f'INVALID_CANDLE_{index}' for index, candle in enumerate(ordered) if not self._valid_candle(candle)]
        epochs = [float(item['epoch']) for item in ordered if item.get('epoch') is not None]
        if epochs and (epochs != sorted(epochs) or len(set(epochs)) != len(epochs)):
            errors.append('CANDLE_ORDER_OR_DUPLICATE_ERROR')
        valid = [item for item in ordered if self._valid_candle(item)]
        if not valid or len(valid) != len(ordered):
            return {
                'source': source, 'symbol': symbol, 'timeframe': timeframe,
                'state': 'REJECTED', 'is_otc': bool(is_otc),
                'dataQuality': {'score': 0, 'flags': errors or ['NO_CANDLES']},
                'signal': {'direction': 'NO_SIGNAL', 'reason': 'INVALID_OR_MISSING_CANDLES'},
            }

        is_otc = bool(is_otc or '(OTC)' in symbol.upper() or '[OTC]' in symbol.upper())
        completeness = {item.get('completeness') for item in valid}
        training_eligible = source == 'deriv' and not is_otc and completeness == {'PROVIDER_OHLC'}
        flags = []
        candle_epochs = [float(item['epoch']) for item in valid if item.get('epoch') is not None]
        gap_count = sum(1 for left, right in zip(candle_epochs, candle_epochs[1:]) if right - left > timeframe_seconds * 1.5) if timeframe_seconds > 0 else 0
        if gap_count:
            flags.append('CANDLE_GAPS_PRESENT')
        if not training_eligible:
            flags.append('NOT_VERIFIED_TRAINING_DATA')
        last_epoch = valid[-1].get('epoch')
        age_seconds = max(0.0, now - (float(last_epoch) + timeframe_seconds)) if last_epoch is not None else None
        stale = age_seconds is not None and age_seconds > max(30, timeframe_seconds * 2)
        if stale:
            flags.append('STALE_CLOSED_CANDLES')
        quality_score = max(0, 100 - min(gap_count * 8, 32) - (25 if not training_eligible else 0) - (30 if stale else 0))
        quality = {
            'score': quality_score,
            'state': 'VALID' if quality_score >= self.min_quality_score and not stale else 'WARNING',
            'flags': flags, 'gapCount': gap_count,
            'ageSeconds': round(age_seconds, 3) if age_seconds is not None else None,
            'trainingEligible': training_eligible and not stale and gap_count == 0,
            'observationOnly': is_otc,
            'provenance': 'DERIV_PROVIDER_OHLC' if training_eligible else 'OBSERVED_OR_UNVERIFIED',
        }
        indicators = self._indicators(valid)
        behavior = self._behavior(valid)

        if is_otc:
            forecast = self.otc_predictor.analyze_sequence(valid)
            direction = forecast.get('direction', 'NO_TRADE')
            direction = direction if direction in {'CALL', 'PUT'} else 'NO_SIGNAL'
            directional_votes = {}
            if direction in {'CALL', 'PUT'}:
                directional_votes['micro_momentum'] = {'direction': direction, 'detail': forecast.get('reason', 'OTC_SEQUENCE_MODEL')}
                if 'Streak:' in forecast.get('reason', ''):
                    directional_votes['repetitive_action'] = {'direction': direction, 'detail': forecast['reason']}
            assessment = {
                'direction': direction,
                'confidence': int(round(float(forecast.get('confidence', 0.0)) * 100)),
                'agreeCount': len(directional_votes), 'opposeCount': 0,
                'agreeing': list(directional_votes), 'opposing': [],
                'votes': directional_votes, 'indicators': indicators.get('values', {}),
                'reason': forecast.get('reason', 'OTC_FORECAST_NO_TRADE'),
                'forecast': forecast, 'model': 'OTC_TIME_SERIES_OBSERVATION_ONLY',
            }
            behavior = {
                **behavior,
                'algorithmDetection': 'REPEATED_VISIBLE_PRICE_ACTION_CANDIDATE_NOT_BROKER_ALGORITHM_IDENTIFICATION',
                'otcForecast': forecast,
            }
        else:
            weights = {key: (learned_weights or {}).get(key, value) for key, value in BASE_WEIGHTS.items()}
            assessment = evaluate_confluence(valid, weights=weights)

        vetoes = []
        if quality['state'] != 'VALID':
            vetoes.append('DATA_QUALITY_GATE')
        if behavior.get('falseBreakoutRisk'):
            vetoes.append('FAILED_BREAKOUT_GATE')
        if (behavior.get('gapRatio') or 0) >= 1.5:
            vetoes.append('EXTREME_GAP_GATE')
        if (behavior.get('volatilityRatio') or 0) >= 3.0:
            vetoes.append('EXTREME_VOLATILITY_GATE')
        if vetoes:
            assessment = {**assessment, 'direction': 'NO_SIGNAL', 'reason': vetoes[0], 'vetoes': vetoes}

        span = max(float(valid[-1]['high']) - float(valid[-1]['low']), 1e-12)
        candle_type = self._pattern(valid)
        quality_pair_score = round(quality_score * 0.7 + assessment.get('confidence', 0) * 0.3, 2)
        signal_ready = assessment['direction'] in {'CALL', 'PUT'} and not vetoes
        return {
            'source': source, 'symbol': symbol, 'timeframe': timeframe,
            'state': 'READY' if signal_ready else 'VETOED' if vetoes else 'NO_SIGNAL',
            'is_otc': is_otc, 'verified': not is_otc and source == 'deriv',
            'dataQuality': quality, 'patternDetection': candle_type,
            'chartAnalysis': {'candleCount': len(valid), 'lastRange': span},
            'indicatorEngine': indicators, 'behaviourFinder': behavior,
            'pairAndCandleType': {
                'pairType': 'OTC' if is_otc else 'REGULAR_OR_UNKNOWN',
                'candleType': candle_type['type'], 'cot': 'UNAVAILABLE_NO_COT_SOURCE',
            },
            'qualityPair': {'rankingScore': quality_pair_score, 'scoreType': 'QUALITY_AND_MODEL_SCORE_NOT_WIN_PROBABILITY'},
            'signal': assessment, 'vetoes': vetoes,
        }

    @staticmethod
    def top_pairs(reports, limit=15):
        ranked = [item for item in reports if item.get('state') == 'READY' and item.get('qualityPair')]
        return sorted(ranked, key=lambda item: item['qualityPair']['rankingScore'], reverse=True)[:max(0, min(15, int(limit)))]
