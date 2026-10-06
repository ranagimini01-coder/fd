"""Format a qualified binary signal using its exact candle entry epoch."""
from datetime import datetime, timezone

from pairs_config import REAL_MARKET_PAIRS


_SYMBOL_NAMES = {
    key: config["name"]
    for key, config in REAL_MARKET_PAIRS.items()
}
_SYMBOL_NAMES.update({
    config["deriv"]: config["name"]
    for config in REAL_MARKET_PAIRS.values()
})


def _display_symbol(symbol):
    symbol = str(symbol)
    if symbol in _SYMBOL_NAMES:
        return _SYMBOL_NAMES[symbol]
    normalized = symbol.removeprefix("frx").removeprefix("cry")
    if len(normalized) == 6 and normalized.isalpha():
        return f"{normalized[:3]}/{normalized[3:]}"
    return normalized


def format_binary_signal(symbol, direction, confidence, timeframe_min, entry_epoch):
    """Return text and structured signal data aligned to the provided entry epoch."""
    direction = str(direction).upper()
    if direction not in {"CALL", "PUT"}:
        raise ValueError("direction must be CALL or PUT")
    confidence = int(round(float(confidence)))
    if not 0 <= confidence <= 100:
        raise ValueError("confidence must be between 0 and 100")
    timeframe_min = int(timeframe_min)
    if timeframe_min < 1:
        raise ValueError("timeframe_min must be positive")
    entry_epoch = int(entry_epoch)
    timeframe_seconds = timeframe_min * 60
    if entry_epoch <= 0 or entry_epoch % timeframe_seconds:
        raise ValueError("entry_epoch must align to the timeframe candle boundary")

    generated_at = datetime.now(timezone.utc)
    entry_at = datetime.fromtimestamp(entry_epoch, timezone.utc)
    entry_time = entry_at.strftime("%I:%M %p UTC")
    formatted_symbol = _display_symbol(symbol)
    text_payload = (
        f"PAIR: {formatted_symbol}\n"
        f"TIMEFRAME: {timeframe_min} MINUTE\n"
        f"ENTRY TIME: {entry_time}\n"
        f"CONFIDENCE: {confidence}%\n"
        f"DIRECTION: {direction}"
    )

    return {
        "text_payload": text_payload,
        "raw_data": {
            "symbol": formatted_symbol,
            "timeframe": f"{timeframe_min}m",
            "entry_time": entry_time,
            "entry_epoch": entry_epoch,
            "confidence": confidence,
            "direction": direction,
            "timestamp": generated_at.timestamp(),
        },
    }