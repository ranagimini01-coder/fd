"""Master catalog of real-market instruments available through Deriv."""

from datetime import datetime, timezone

__all__ = [
    "REAL_MARKET_PAIRS",
    "get_active_pairs",
    "get_deriv_symbols",
    "is_forex_market_open",
    "get_currently_active_deriv_symbols",
]


REAL_MARKET_PAIRS = {
    # 1. Major Forex Pairs
    "EURUSD": {"name": "EUR/USD", "deriv": "frxEURUSD", "category": "forex_major"},
    "GBPUSD": {"name": "GBP/USD", "deriv": "frxGBPUSD", "category": "forex_major"},
    "USDJPY": {"name": "USD/JPY", "deriv": "frxUSDJPY", "category": "forex_major"},
    "AUDUSD": {"name": "AUD/USD", "deriv": "frxAUDUSD", "category": "forex_major"},
    "USDCAD": {"name": "USD/CAD", "deriv": "frxUSDCAD", "category": "forex_major"},
    "USDCHF": {"name": "USD/CHF", "deriv": "frxUSDCHF", "category": "forex_major"},
    "NZDUSD": {"name": "NZD/USD", "deriv": "frxNZDUSD", "category": "forex_major"},

    # 2. Minor & Cross Forex Pairs
    "EURGBP": {"name": "EUR/GBP", "deriv": "frxEURGBP", "category": "forex_minor"},
    "EURJPY": {"name": "EUR/JPY", "deriv": "frxEURJPY", "category": "forex_minor"},
    "GBPJPY": {"name": "GBP/JPY", "deriv": "frxGBPJPY", "category": "forex_minor"},
    "EURCAD": {"name": "EUR/CAD", "deriv": "frxEURCAD", "category": "forex_minor"},
    "EURAUD": {"name": "EUR/AUD", "deriv": "frxEURAUD", "category": "forex_minor"},
    "EURNZD": {"name": "EUR/NZD", "deriv": "frxEURNZD", "category": "forex_minor"},
    "EURCHF": {"name": "EUR/CHF", "deriv": "frxEURCHF", "category": "forex_minor"},
    "GBPCAD": {"name": "GBP/CAD", "deriv": "frxGBPCAD", "category": "forex_minor"},
    "GBPAUD": {"name": "GBP/AUD", "deriv": "frxGBPAUD", "category": "forex_minor"},
    "GBPNZD": {"name": "GBP/NZD", "deriv": "frxGBPNZD", "category": "forex_minor"},
    "GBPCHF": {"name": "GBP/CHF", "deriv": "frxGBPCHF", "category": "forex_minor"},
    "AUDCAD": {"name": "AUD/CAD", "deriv": "frxAUDCAD", "category": "forex_minor"},
    "AUDJPY": {"name": "AUD/JPY", "deriv": "frxAUDJPY", "category": "forex_minor"},
    "AUDNZD": {"name": "AUD/NZD", "deriv": "frxAUDNZD", "category": "forex_minor"},
    "AUDCHF": {"name": "AUD/CHF", "deriv": "frxAUDCHF", "category": "forex_minor"},
    "CADJPY": {"name": "CAD/JPY", "deriv": "frxCADJPY", "category": "forex_minor"},
    "CADCHF": {"name": "CAD/CHF", "deriv": "frxCADCHF", "category": "forex_minor"},
    "NZDJPY": {"name": "NZD/JPY", "deriv": "frxNZDJPY", "category": "forex_minor"},
    "NZDCAD": {"name": "NZD/CAD", "deriv": "frxNZDCAD", "category": "forex_minor"},
    "NZDCHF": {"name": "NZD/CHF", "deriv": "frxNZDCHF", "category": "forex_minor"},
    "CHFJPY": {"name": "CHF/JPY", "deriv": "frxCHFJPY", "category": "forex_minor"},

    # 3. Commodities & Metals
    "XAUUSD": {"name": "XAU/USD", "deriv": "frxXAUUSD", "category": "commodities"},  # Gold
    "XAGUSD": {"name": "XAG/USD", "deriv": "frxXAGUSD", "category": "commodities"},  # Silver
    "USCRUDE": {"name": "US Crude", "deriv": "frxXTIUSD", "category": "commodities"},  # WTI
    "UKBRENT": {"name": "UK Brent", "deriv": "frxXBRUSD", "category": "commodities"},  # Brent

    # 4. Exotic Forex Pairs
    "USDTRY": {"name": "USD/TRY", "deriv": "frxUSDTRY", "category": "exotic"},
    "USDBRL": {"name": "USD/BRL", "deriv": "frxUSDBRL", "category": "exotic"},
    "USDINR": {"name": "USD/INR", "deriv": "frxUSDINR", "category": "exotic"},
    "USDMXN": {"name": "USD/MXN", "deriv": "frxUSDMXN", "category": "exotic"},
    "USDSGD": {"name": "USD/SGD", "deriv": "frxUSDSGD", "category": "exotic"},

    # 5. Cryptocurrencies
    "BTCUSD": {"name": "BTC/USD", "deriv": "cryBTCUSD", "category": "crypto"},
    "ETHUSD": {"name": "ETH/USD", "deriv": "cryETHUSD", "category": "crypto"},
}


def get_active_pairs(category=None):
    """Return display names, optionally filtered by category."""
    if category:
        return [
            data["name"]
            for data in REAL_MARKET_PAIRS.values()
            if data["category"] == category
        ]
    return [data["name"] for data in REAL_MARKET_PAIRS.values()]


def get_deriv_symbols():
    """Return the Deriv API symbol for every configured real-market pair."""
    return [data["deriv"] for data in REAL_MARKET_PAIRS.values()]


def is_forex_market_open(now=None):
    """Return whether standard Forex trading hours are open at the given UTC time."""
    now = now or datetime.now(timezone.utc)
    now = now.astimezone(timezone.utc)
    weekday = now.weekday()

    if weekday == 5:
        return False
    if weekday == 4 and now.hour >= 22:
        return False
    if weekday == 6 and now.hour < 22:
        return False
    return True


def get_currently_active_deriv_symbols(now=None):
    """Return crypto symbols 24/7 and other real-market symbols during Forex hours."""
    forex_open = is_forex_market_open(now)
    active_symbols = []
    market_categories = {"forex_major", "forex_minor", "commodities", "exotic"}

    for config in REAL_MARKET_PAIRS.values():
        category = config.get("category")
        if category == "crypto" or (forex_open and category in market_categories):
            active_symbols.append(config["deriv"])

    return active_symbols