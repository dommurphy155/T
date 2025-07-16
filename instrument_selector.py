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

def choose_best_instrument(state: dict) -> str:
    """
    Picks a tradeable instrument from preferred list based on:
    - Active session
    - Volume window (avoid low-liquidity)
    - Cooldown memory (avoid recent trades on same pair)
    """
    if not is_active_session_now():
        logging.info("Skipping instrument selection: Inactive forex session.")
        return None

    if is_low_liquidity_period():
        logging.info("Skipping instrument selection: Detected low liquidity period.")
        return None

    cooldown_memory = state.get("cooldowns", {})
    eligible_pairs = []

    for pair in CURRENCY_PAIRS:
        last_trade_time = cooldown_memory.get(pair)
        if not last_trade_time:
            eligible_pairs.append(pair)
            continue

        # Enforce cooldown window (6 seconds)
        time_diff = (datetime.utcnow() - datetime.fromisoformat(last_trade_time)).total_seconds()
        if time_diff >= 6:
            eligible_pairs.append(pair)

    if not eligible_pairs:
        logging.info("No eligible pairs passed cooldown filter.")
        return None

    selected = random.choice(eligible_pairs)
    logging.info(f"Selected instrument: {selected}")
    return selected
