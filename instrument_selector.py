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

    # London: 07–16 UTC, New York: 13–22 UTC, Tokyo: 00–09 UTC
    return (
        (7 <= hour < 16) or
        (13 <= hour < 22) or
        (0 <= hour < 9)
    )

def is_low_liquidity_period():
    hour = datetime.utcnow().hour
    return LOW_LIQUIDITY_HOURS["start"] <= hour <= LOW_LIQUIDITY_HOURS["end"]

# ERROR: 'select_instruments' is imported as a module-level function in other files, but is not defined here. Implement this function or update the import in other files to use the correct function.
