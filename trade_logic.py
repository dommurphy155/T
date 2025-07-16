import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, EMAIndicator
from ta.volatility import AverageTrueRange
from datetime import datetime, timedelta
import pytz

SIGNAL_MEMORY = {}
SIGNAL_COOLDOWN_SECONDS = 6
SIGNAL_THRESHOLD = 0.7

def _recent_signal_memory(pair):
    now = datetime.utcnow()
    if pair in SIGNAL_MEMORY:
        last_signal_time = SIGNAL_MEMORY[pair]
        return (now - last_signal_time).total_seconds() < SIGNAL_COOLDOWN_SECONDS
    return False

def _update_signal_memory(pair):
    SIGNAL_MEMORY[pair] = datetime.utcnow()

def compute_indicators(df):
    df = df.copy()
    df['rsi'] = RSIIndicator(close=df['close'], window=14).rsi()
    df['macd'] = MACD(close=df['close']).macd_diff()
    df['ema9'] = EMAIndicator(close=df['close'], window=9).ema_indicator()
    df['ema21'] = EMAIndicator(close=df['close'], window=21).ema_indicator()
    df['atr'] = AverageTrueRange(high=df['high'], low=df['low'], close=df['close']).average_true_range()
    df['momentum'] = df['close'].diff()
    df['velocity'] = df['momentum'].diff()
    return df

def score_signal(df):
    latest = df.iloc[-1]
    score = 0
    total_weight = 0

    # RSI
    if latest['rsi'] < 30:
        score += 0.2
    elif latest['rsi'] > 70:
        score -= 0.2
    total_weight += 0.2

    # MACD
    if latest['macd'] > 0:
        score += 0.2
    elif latest['macd'] < 0:
        score -= 0.2
    total_weight += 0.2

    # EMA Trend
    if latest['ema9'] > latest['ema21']:
        score += 0.2
    elif latest['ema9'] < latest['ema21']:
        score -= 0.2
    total_weight += 0.2

    # Momentum
    if latest['momentum'] > 0 and latest['velocity'] > 0:
        score += 0.2
    elif latest['momentum'] < 0 and latest['velocity'] < 0:
        score -= 0.2
    total_weight += 0.2

    # Normalize
    normalized_score = score / total_weight if total_weight else 0
    return round(normalized_score, 2)

def get_trade_signal(pair, df, higher_tf_df=None):
    if _recent_signal_memory(pair):
        return None

    df = compute_indicators(df)
    signal_score = score_signal(df)

    if signal_score < SIGNAL_THRESHOLD:
        return None

    # Confirm with higher timeframe if available
    if higher_tf_df is not None:
        higher_tf_df = compute_indicators(higher_tf_df)
        ht_score = score_signal(higher_tf_df)
        if ht_score < SIGNAL_THRESHOLD:
            return None

    direction = "buy" if signal_score > 0 else "sell"
    _update_signal_memory(pair)
    return {
        "pair": pair,
        "direction": direction,
        "confidence": signal_score,
        "timestamp": datetime.utcnow().isoformat()
    }

def is_forex_market_open():
    now = datetime.utcnow().replace(tzinfo=pytz.utc)

    # Forex runs Sunday 9pm GMT to Friday 9pm GMT
    weekday = now.weekday()
    hour = now.hour

    if weekday == 5 or weekday == 6:
        return False  # Saturday or Sunday
    if weekday == 4 and hour >= 21:
        return False  # Friday after 9pm
    if weekday == 6 and hour < 21:
        return False  # Sunday before 9pm
    return True

def within_active_session():
    now = datetime.utcnow().replace(tzinfo=pytz.utc)
    london = now.astimezone(pytz.timezone("Europe/London")).hour
    new_york = now.astimezone(pytz.timezone("America/New_York")).hour
    tokyo = now.astimezone(pytz.timezone("Asia/Tokyo")).hour

    return (
        7 <= london <= 17 or
        8 <= new_york <= 16 or
        1 <= tokyo <= 9
    )

def can_trade_now():
    return is_forex_market_open() and within_active_session()
