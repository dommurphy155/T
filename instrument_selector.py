import random
import logging
from datetime import datetime
import pytz

CURRENCY_PAIRS = [
    "EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CHF"
]

LOW_LIQUIDITY_HOURS = {
    "start": 21,  # 9 PM UTC (Asia session overlap)
    "end": 23     # 11 PM UTC (lowest liquidity)
}

def is_active_session_now():
    utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
    hour = utc_now.hour
    return (
        (7 <= hour < 16) or
        (13 <= hour < 22) or
        (0 <= hour < 9)
    )

def is_low_liquidity_period():
    hour = datetime.utcnow().hour
    return LOW_LIQUIDITY_HOURS["start"] <= hour <= LOW_LIQUIDITY_HOURS["end"]

def select_instruments():
    # Minimal stub for compatibility
    return CURRENCY_PAIRS
