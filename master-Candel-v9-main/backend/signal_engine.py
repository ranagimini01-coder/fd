"""Confluence signal engine.

Pure functions over CLOSED candles only. Every vote is derived from observed
prices; nothing is fabricated. A direction is emitted only when several
independent indicator families agree and the weighted agreement clears the
caller's confidence threshold. Confidence is a *confluence score* (50-99) --
the realised accuracy is measured separately by verifying each signal against
the entry candle's close.
"""
import math
import numpy as np

MIN_CANDLES = 60
DEEP_MIN_CANDLES = 40

# Indicator families and their maximum vote weights.
WEIGHTS = {
    'ema_trend': 1.5, 'macd': 1.25, 'rsi': 1.0, 'bollinger': 1.0, 'stochastic': 1.0,
    'momentum': 0.75, 'candle_pattern': 1.25, 'support_resistance': 0.75, 'structure': 0.75,
}
TOTAL_WEIGHT = sum(WEIGHTS.values())


def _ema(values, period):
    alpha = 2 / (period + 1)
    out = np.empty(len(values))
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


def _rsi(closes, period=14):
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    values = [50.0] * (period + 1)
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        values.append(100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss))
    return np.array(values)


def _atr(highs, lows, closes, period=14):
    prev_close = np.concatenate(([closes[0]], closes[:-1]))
    tr = np.maximum(highs - lows, np.maximum(np.abs(highs - prev_close), np.abs(lows - prev_close)))
    return _ema(tr, period)


def _stochastic(highs, lows, closes, period=14, smooth=3):
    k = np.full(len(closes), 50.0)
    for i in range(period - 1, len(closes)):
        low = lows[i - period + 1:i + 1].min()
        high = highs[i - period + 1:i + 1].max()
        k[i] = 50.0 if high == low else (closes[i] - low) / (high - low) * 100
    d = np.convolve(k, np.ones(smooth) / smooth, mode='same')
    return k, d


def _vote(direction, weight, detail):
    return {'direction': direction, 'weight': weight, 'detail': detail}


def trend_direction(candles, minimum=30):
    if len(candles) < minimum:
        return None
    closes = np.asarray([float(candle['close']) for candle in candles], dtype=float)
    if not np.all(np.isfinite(closes)) or closes[-1] <= 0:
        return None
    fast, slow = _ema(closes, 9), _ema(closes, 21)
    slope = slow[-1] - slow[-4]
    if fast[-1] > slow[-1] and slope > 0:
        return 'CALL'
    if fast[-1] < slow[-1] and slope < 0:
        return 'PUT'
    return 'NEUTRAL'


def _micro_momentum_snapshot(closes, window=10):
    if len(closes) < 2:
        return {'velocity': 0.0, 'trend': 'NEUTRAL', 'fake_breakout': False, 'late_rejection': False, 'last_step': 0.0, 'window': min(window, max(1, len(closes)))}

    recent = list(closes[-window:])
    deltas = [recent[i] - recent[i - 1] for i in range(1, len(recent))]
    velocity = sum(deltas) / max(1, len(deltas)) if deltas else 0.0
    last_step = deltas[-1] if deltas else 0.0
    trend = 'CALL' if velocity > 0 else 'PUT' if velocity < 0 else 'NEUTRAL'
    fake_breakout = (velocity > 0 and last_step < 0 and recent[-1] > recent[0]) or (velocity < 0 and last_step > 0 and recent[-1] < recent[0])
    late_rejection = (velocity > 0 and last_step < 0) or (velocity < 0 and last_step > 0)
    return {'velocity': float(velocity), 'trend': trend, 'fake_breakout': bool(fake_breakout), 'late_rejection': bool(late_rejection), 'last_step': float(last_step), 'window': len(recent)}


def evaluate(candles, higher_timeframe_candles=None, deep=False, weights=None):
    """Return a scored assessment for the NEXT candle.

    candles: list of closed candle dicts (chronological) with open/high/low/close.
    higher_timeframe_candles: optional closed candles of a higher timeframe for trend confirmation.
    deep: relax the minimum history and add higher-timeframe confirmation weighting.
    """
    minimum = DEEP_MIN_CANDLES if deep else MIN_CANDLES
    if len(candles) < minimum:
        return {'direction': 'NO_SIGNAL', 'confidence': 0, 'reason': 'INSUFFICIENT_CLOSED_CANDLES', 'required': minimum, 'available': len(candles), 'votes': {}}
    opens = np.array([float(c['open']) for c in candles])
    highs = np.array([float(c['high']) for c in candles])
    lows = np.array([float(c['low']) for c in candles])
    closes = np.array([float(c['close']) for c in candles])
    if not np.all(np.isfinite(closes)) or closes[-1] <= 0:
        return {'direction': 'NO_SIGNAL', 'confidence': 0, 'reason': 'INVALID_PRICE_DATA', 'votes': {}}

    votes = {}
    penalties = []
    active_weights = {}
    micro_momentum = _micro_momentum_snapshot(closes)
    feature_vector = {
        'close': float(closes[-1]),
        'slope_5': float((closes[-1] - closes[-5]) / closes[-5]) if len(closes) >= 5 and closes[-5] else 0.0,
        'slope_10': float((closes[-1] - closes[-10]) / closes[-10]) if len(closes) >= 10 and closes[-10] else 0.0,
        'micro_velocity': float(micro_momentum['velocity']),
        'last_step': float(micro_momentum['last_step']),
        'volatility': float(np.std(closes[-10:])) if len(closes) >= 10 else 0.0,
    }
    if micro_momentum['late_rejection'] or micro_momentum['fake_breakout']:
        penalties.append({'name': 'MICRO_MOMENTUM_REJECTION', 'points': 8, 'detail': f"tick velocity {micro_momentum['velocity']:.4f}, fake_breakout={micro_momentum['fake_breakout']}, late_rejection={micro_momentum['late_rejection']}"})
    votes['micro_momentum'] = _vote(micro_momentum['trend'], 1.0, f"tick velocity {micro_momentum['velocity']:.4f} across last {micro_momentum['window']} closes") if micro_momentum['trend'] != 'NEUTRAL' else _vote('NEUTRAL', 0.0, 'tick velocity neutral')
    for family, default in WEIGHTS.items():
        try:
            value = float((weights or {}).get(family, default))
        except (TypeError, ValueError):
            value = default
        active_weights[family] = value if math.isfinite(value) and value > 0 else default
    total_weight = sum(active_weights.values())

    # 1. EMA trend alignment
    ema9, ema21, ema50 = _ema(closes, 9), _ema(closes, 21), _ema(closes, 50)
    slope21 = ema21[-1] - ema21[-4]
    if ema9[-1] > ema21[-1] > ema50[-1] and closes[-1] > ema21[-1] and slope21 > 0:
        votes['ema_trend'] = _vote('CALL', active_weights['ema_trend'], 'EMA9>EMA21>EMA50, price above EMA21')
    elif ema9[-1] < ema21[-1] < ema50[-1] and closes[-1] < ema21[-1] and slope21 < 0:
        votes['ema_trend'] = _vote('PUT', active_weights['ema_trend'], 'EMA9<EMA21<EMA50, price below EMA21')
    elif ema9[-1] > ema21[-1] and slope21 > 0:
        votes['ema_trend'] = _vote('CALL', active_weights['ema_trend'] * 0.5, 'EMA9 above EMA21, rising')
    elif ema9[-1] < ema21[-1] and slope21 < 0:
        votes['ema_trend'] = _vote('PUT', active_weights['ema_trend'] * 0.5, 'EMA9 below EMA21, falling')
    else:
        votes['ema_trend'] = _vote('NEUTRAL', 0, 'EMAs mixed')

    # 2. MACD histogram direction and slope
    macd_line = _ema(closes, 12) - _ema(closes, 26)
    signal_line = _ema(macd_line, 9)
    hist = macd_line - signal_line
    if hist[-1] > 0 and hist[-1] > hist[-2] > hist[-3]:
        votes['macd'] = _vote('CALL', active_weights['macd'], 'MACD histogram positive and expanding')
    elif hist[-1] < 0 and hist[-1] < hist[-2] < hist[-3]:
        votes['macd'] = _vote('PUT', active_weights['macd'], 'MACD histogram negative and expanding')
    elif hist[-1] > 0 and hist[-2] <= 0:
        votes['macd'] = _vote('CALL', active_weights['macd'] * 0.8, 'MACD bullish cross')
    elif hist[-1] < 0 and hist[-2] >= 0:
        votes['macd'] = _vote('PUT', active_weights['macd'] * 0.8, 'MACD bearish cross')
    else:
        votes['macd'] = _vote('NEUTRAL', 0, 'MACD flat')

    # 3. RSI: exhaustion reversal or momentum continuation
    rsi = _rsi(closes)
    r, r_prev = rsi[-1], rsi[-2]
    if r < 30 and r > r_prev:
        votes['rsi'] = _vote('CALL', active_weights['rsi'], f'RSI {r:.0f} oversold and turning up')
    elif r > 70 and r < r_prev:
        votes['rsi'] = _vote('PUT', active_weights['rsi'], f'RSI {r:.0f} overbought and turning down')
    elif 52 < r < 68 and r > r_prev:
        votes['rsi'] = _vote('CALL', active_weights['rsi'] * 0.6, f'RSI {r:.0f} rising in bullish zone')
    elif 32 < r < 48 and r < r_prev:
        votes['rsi'] = _vote('PUT', active_weights['rsi'] * 0.6, f'RSI {r:.0f} falling in bearish zone')
    else:
        votes['rsi'] = _vote('NEUTRAL', 0, f'RSI {r:.0f} neutral')

    # 4. Bollinger bands (20, 2)
    window = closes[-20:]
    mid, std = window.mean(), window.std(ddof=0)
    upper, lower = mid + 2 * std, mid - 2 * std
    pct_b = 0.5 if upper == lower else (closes[-1] - lower) / (upper - lower)
    if closes[-1] < lower and closes[-1] > opens[-1]:
        votes['bollinger'] = _vote('CALL', active_weights['bollinger'], 'Close below lower band with bullish body')
    elif closes[-1] > upper and closes[-1] < opens[-1]:
        votes['bollinger'] = _vote('PUT', active_weights['bollinger'], 'Close above upper band with bearish body')
    elif 0.55 < pct_b < 0.9 and closes[-1] > mid and mid > np.mean(closes[-40:-20]):
        votes['bollinger'] = _vote('CALL', active_weights['bollinger'] * 0.6, 'Riding upper half of rising bands')
    elif 0.1 < pct_b < 0.45 and closes[-1] < mid and mid < np.mean(closes[-40:-20]):
        votes['bollinger'] = _vote('PUT', active_weights['bollinger'] * 0.6, 'Riding lower half of falling bands')
    else:
        votes['bollinger'] = _vote('NEUTRAL', 0, f'%B {pct_b:.2f}')

    # 5. Stochastic (14, 3)
    k, d = _stochastic(highs, lows, closes)
    if k[-1] < 25 and k[-1] > d[-1] and k[-2] <= d[-2]:
        votes['stochastic'] = _vote('CALL', active_weights['stochastic'], 'Stochastic bullish cross from oversold')
    elif k[-1] > 75 and k[-1] < d[-1] and k[-2] >= d[-2]:
        votes['stochastic'] = _vote('PUT', active_weights['stochastic'], 'Stochastic bearish cross from overbought')
    elif 40 < k[-1] < 80 and k[-1] > d[-1] and k[-1] > k[-2]:
        votes['stochastic'] = _vote('CALL', active_weights['stochastic'] * 0.5, 'Stochastic rising above signal')
    elif 20 < k[-1] < 60 and k[-1] < d[-1] and k[-1] < k[-2]:
        votes['stochastic'] = _vote('PUT', active_weights['stochastic'] * 0.5, 'Stochastic falling below signal')
    else:
        votes['stochastic'] = _vote('NEUTRAL', 0, 'Stochastic mixed')

    # 6. Momentum / rate of change (5)
    roc = (closes[-1] - closes[-6]) / closes[-6] * 100
    atr = _atr(highs, lows, closes)
    atr_now = atr[-1] if atr[-1] > 0 else max(1e-9, np.mean(highs - lows))
    normalized = (closes[-1] - closes[-6]) / (atr_now * 5)
    if normalized > 0.35:
        votes['momentum'] = _vote('CALL', active_weights['momentum'], f'5-bar momentum +{roc:.3f}%')
    elif normalized < -0.35:
        votes['momentum'] = _vote('PUT', active_weights['momentum'], f'5-bar momentum {roc:.3f}%')
    else:
        votes['momentum'] = _vote('NEUTRAL', 0, 'Momentum flat')

    # 7. Candle patterns on the last two closed candles
    body = closes - opens
    rng = np.maximum(highs - lows, 1e-12)
    last, prev = -1, -2
    upper_wick = highs[last] - max(opens[last], closes[last])
    lower_wick = min(opens[last], closes[last]) - lows[last]
    pattern = None
    if body[last] > 0 and body[prev] < 0 and closes[last] > opens[prev] and opens[last] <= closes[prev]:
        pattern = ('CALL', 'Bullish engulfing')
    elif body[last] < 0 and body[prev] > 0 and closes[last] < opens[prev] and opens[last] >= closes[prev]:
        pattern = ('PUT', 'Bearish engulfing')
    elif lower_wick > 2 * abs(body[last]) and upper_wick < abs(body[last]) and closes[last] >= opens[last] and closes[last] < ema21[-1]:
        pattern = ('CALL', 'Hammer / pin bar rejection')
    elif upper_wick > 2 * abs(body[last]) and lower_wick < abs(body[last]) and closes[last] <= opens[last] and closes[last] > ema21[-1]:
        pattern = ('PUT', 'Shooting star rejection')
    elif all(body[-3:] > 0) and all(closes[-3:] > opens[-3:]) and closes[-1] > closes[-2] > closes[-3] and np.mean(np.abs(body[-3:]) / rng[-3:]) > 0.55:
        pattern = ('CALL', 'Three consecutive strong bullish closes')
    elif all(body[-3:] < 0) and closes[-1] < closes[-2] < closes[-3] and np.mean(np.abs(body[-3:]) / rng[-3:]) > 0.55:
        pattern = ('PUT', 'Three consecutive strong bearish closes')
    votes['candle_pattern'] = _vote(pattern[0], active_weights['candle_pattern'], pattern[1]) if pattern else _vote('NEUTRAL', 0, 'No decisive pattern')

    # 8. Support / resistance proximity from the last 50 candles
    look_h, look_l = highs[-50:-1], lows[-50:-1]
    resistance, support = look_h.max(), look_l.min()
    near = 0.35 * atr_now
    if abs(closes[-1] - support) <= near and closes[-1] > lows[-1] + rng[-1] * 0.4:
        votes['support_resistance'] = _vote('CALL', active_weights['support_resistance'], 'Holding above 50-bar support')
    elif abs(closes[-1] - resistance) <= near and closes[-1] < highs[-1] - rng[-1] * 0.4:
        votes['support_resistance'] = _vote('PUT', active_weights['support_resistance'], 'Rejected at 50-bar resistance')
    elif closes[-1] > resistance:
        votes['support_resistance'] = _vote('CALL', active_weights['support_resistance'] * 0.8, 'Breakout above 50-bar high')
    elif closes[-1] < support:
        votes['support_resistance'] = _vote('PUT', active_weights['support_resistance'] * 0.8, 'Breakdown below 50-bar low')
    else:
        votes['support_resistance'] = _vote('NEUTRAL', 0, 'Mid-range')

    # 9. Market structure: higher highs / higher lows over the last 3 swings (5-bar blocks)
    blocks_h = [highs[i:i + 5 or None].max() for i in range(-15, 0, 5)]
    blocks_l = [lows[i:i + 5 or None].min() for i in range(-15, 0, 5)]
    if blocks_h[0] < blocks_h[1] < blocks_h[2] and blocks_l[0] < blocks_l[1] < blocks_l[2]:
        votes['structure'] = _vote('CALL', active_weights['structure'], 'Higher highs and higher lows')
    elif blocks_h[0] > blocks_h[1] > blocks_h[2] and blocks_l[0] > blocks_l[1] > blocks_l[2]:
        votes['structure'] = _vote('PUT', active_weights['structure'], 'Lower highs and lower lows')
    else:
        votes['structure'] = _vote('NEUTRAL', 0, 'No clear structure')

    # Volatility regime penalties
    atr_baseline = float(np.mean(atr[-50:])) if len(atr) >= 50 else float(np.mean(atr))
    regime = atr_now / atr_baseline if atr_baseline > 0 else 1.0
    if regime > 2.2:
        penalties.append({'name': 'VOLATILITY_SPIKE', 'points': 12, 'detail': f'ATR {regime:.1f}x baseline'})
    elif regime > 1.6:
        penalties.append({'name': 'ELEVATED_VOLATILITY', 'points': 6, 'detail': f'ATR {regime:.1f}x baseline'})
    if rng[-1] > 3 * atr_now:
        penalties.append({'name': 'CLIMAX_BAR', 'points': 8, 'detail': 'Last candle range >3x ATR'})
    if np.count_nonzero(closes[-20:] == opens[-20:]) >= 6:
        penalties.append({'name': 'FLAT_MARKET', 'points': 10, 'detail': 'Many doji/flat closes'})

    call = sum(v['weight'] for v in votes.values() if v['direction'] == 'CALL')
    put = sum(v['weight'] for v in votes.values() if v['direction'] == 'PUT')
    agree_call = [n for n, v in votes.items() if v['direction'] == 'CALL']
    agree_put = [n for n, v in votes.items() if v['direction'] == 'PUT']
    direction = 'CALL' if call > put else 'PUT' if put > call else 'NO_SIGNAL'
    net = abs(call - put) / total_weight
    neutral = sum(1 for v in votes.values() if v['direction'] == 'NEUTRAL')
    # Concave mapping rewards broad agreement; each silent family costs 1.5 points.
    confidence = 50 + 49 * (net ** 0.7) - 1.5 * neutral

    # Higher-timeframe confirmation (deep scan): reward alignment, punish conflict.
    higher = None
    if higher_timeframe_candles and len(higher_timeframe_candles) >= 30 and direction != 'NO_SIGNAL':
        h_close = np.array([float(c['close']) for c in higher_timeframe_candles])
        h_ema9, h_ema21 = _ema(h_close, 9), _ema(h_close, 21)
        higher_dir = 'CALL' if h_ema9[-1] > h_ema21[-1] and h_close[-1] > h_ema21[-1] else 'PUT' if h_ema9[-1] < h_ema21[-1] and h_close[-1] < h_ema21[-1] else 'NEUTRAL'
        higher = {'direction': higher_dir, 'candles': len(higher_timeframe_candles)}
        if higher_dir == direction:
            confidence += 6
        elif higher_dir != 'NEUTRAL':
            penalties.append({'name': 'HIGHER_TIMEFRAME_CONFLICT', 'points': 12, 'detail': f'Higher timeframe trend is {higher_dir}'})

    confidence -= sum(p['points'] for p in penalties)
    confidence = int(round(max(0, min(99, confidence))))
    agreeing = agree_call if direction == 'CALL' else agree_put
    opposing = agree_put if direction == 'CALL' else agree_call
    return {
        'direction': direction, 'confidence': confidence,
        'callWeight': round(call, 3), 'putWeight': round(put, 3), 'totalWeight': total_weight,
        'agreeing': agreeing, 'opposing': opposing, 'agreeCount': len(agreeing), 'opposeCount': len(opposing),
        'votes': votes, 'penalties': penalties, 'higherTimeframe': higher,
        'micro_momentum': micro_momentum,
        'feature_vector': feature_vector,
        'indicators': {'ema9': float(ema9[-1]), 'ema21': float(ema21[-1]), 'ema50': float(ema50[-1]), 'rsi': float(r), 'macdHist': float(hist[-1]), 'pctB': float(pct_b), 'stochK': float(k[-1]), 'atr': float(atr_now), 'atrRegime': float(regime), 'close': float(closes[-1])},
        'reason': 'CONFLUENCE_SCORED',
    }


def qualifies(assessment, threshold, min_agree=4, max_oppose=1):
    """Gate: direction present, confidence >= threshold, enough agreeing families, few opposing."""
    if assessment['direction'] == 'NO_SIGNAL':
        return False, assessment.get('reason', 'NO_DIRECTION')
    if assessment['confidence'] < threshold:
        return False, f"CONFIDENCE_{assessment['confidence']}_BELOW_{threshold}"
    if assessment['agreeCount'] < min_agree:
        return False, f"ONLY_{assessment['agreeCount']}_FAMILIES_AGREE"
    if assessment['opposeCount'] > max_oppose:
        return False, f"{assessment['opposeCount']}_FAMILIES_OPPOSE"
    return True, 'QUALIFIED'


def outcome(direction, entry_candle):
    """WIN/LOSS/TIE by comparing the entry candle close against its open."""
    o, c = float(entry_candle['open']), float(entry_candle['close'])
    if math.isclose(o, c, rel_tol=0, abs_tol=1e-12):
        return 'TIE'
    if direction == 'CALL':
        return 'WIN' if c > o else 'LOSS'
    return 'WIN' if c < o else 'LOSS'


def market_safety_veto(candles):
    """Block volatility spikes and sideways markets with materially falling tick volume."""
    if len(candles) < 21:
        return None
    highs = np.asarray([float(candle['high']) for candle in candles], dtype=float)
    lows = np.asarray([float(candle['low']) for candle in candles], dtype=float)
    closes = np.asarray([float(candle['close']) for candle in candles], dtype=float)
    if not all(np.all(np.isfinite(values)) for values in (highs, lows, closes)):
        return 'INVALID_SAFETY_FEATURES'

    atr = _atr(highs, lows, closes, 14)
    baseline = float(np.mean(atr[-21:-1]))
    if baseline > 0 and float(atr[-1]) > 2.5 * baseline:
        return 'ATR_SPIKE'

    if len(closes) >= 40:
        band_widths = np.asarray([
            4.0 * float(np.std(closes[index - 19:index + 1])) / max(abs(float(np.mean(closes[index - 19:index + 1]))), 1e-12)
            for index in range(19, len(closes))
        ])
        width_baseline = float(np.mean(band_widths[-21:-1]))
        if width_baseline > 0 and float(band_widths[-1]) > 2.5 * width_baseline:
            return 'BOLLINGER_WIDTH_SPIKE'

    recent = candles[-20:]
    volumes = [candle.get('tickVolume') for candle in recent]
    if all(isinstance(value, (int, float)) and math.isfinite(value) and value >= 0 for value in volumes):
        travel = float(np.sum(np.abs(np.diff(closes[-20:]))))
        efficiency = abs(float(closes[-1] - closes[-20])) / max(travel, 1e-12)
        prior_volume = float(np.mean(volumes[:15]))
        recent_volume = float(np.mean(volumes[15:]))
        if efficiency <= 0.15 and prior_volume > 0 and recent_volume < 0.6 * prior_volume:
            return 'SIDEWAYS_LOW_TICK_VOLUME'
    return None
