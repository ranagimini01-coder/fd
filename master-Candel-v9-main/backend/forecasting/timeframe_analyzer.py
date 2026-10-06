# forecasting/timeframe_analyzer.py

import numpy as np

class TimeframeAnalyzer:
    """
    একাধিক টাইমফ্রেমের কনফ্লুয়েন্স চেক করে ট্রেন্ডের সঠিক দিক নির্ধারণ করার জন্য।
    """
    def __init__(self):
        pass

    def analyze_multi_timeframe(self, short_term_closes: list, long_term_closes: list) -> str:
        """
        short_term_closes: যেমন ১ মিনিটের ক্যান্ডেল ডেটা
        long_term_closes: যেমন ৫ মিনিট বা ১৫ মিনিটের ক্যান্ডেল ডেটা
        """
        if not short_term_closes or not long_term_closes:
            return "NEUTRAL"

        # শর্ট টার্ম ট্রেন্ড
        short_sma = np.mean(short_term_closes[-5:])
        short_current = short_term_closes[-1]
        short_trend = "UP" if short_current > short_sma else "DOWN"

        # লং টার্ম ট্রেন্ড
        long_sma = np.mean(long_term_closes[-5:])
        long_current = long_term_closes[-1]
        long_trend = "UP" if long_current > long_sma else "DOWN"

        # দুটো টাইমফ্রেমের ট্রেন্ড এক হলে তবেই স্ট্রং সিগন্যাল দেবে
        if short_trend == "UP" and long_trend == "UP":
            return "STRONG_CALL"
        elif short_trend == "DOWN" and long_trend == "DOWN":
            return "STRONG_PUT"
        
        return "MIXED_TREND"