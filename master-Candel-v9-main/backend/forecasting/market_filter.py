# forecasting/market_filter.py

import numpy as np

class MarketFilter:
    """
    ফেক ব্রেকআউট এবং চপ্লি মার্কেট ফিল্টার করার জন্য অ্যাডভান্সড লেয়ার।
    """
    def __init__(self, atr_threshold=0.0002):
        self.atr_threshold = atr_threshold

    def is_market_tradable(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> tuple[bool, str]:
        if len(closes) < 14:
            return False, "Not enough candles for filter check"

        # ATR ক্যালকুলেশন (Volatility)
        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                np.abs(highs[1:] - closes[:-1]),
                np.abs(lows[1:] - closes[:-1])
            )
        )
        current_atr = np.mean(tr[-14:])

        # যদি মার্কেট অতিরিক্ত শান্ত বা ভোলাটিলিটি শূন্য হয়
        if current_atr < self.atr_threshold:
            return False, f"Low volatility / Choppy market (ATR: {current_atr:.5f})"

        return True, "Market conditions are suitable for trading"