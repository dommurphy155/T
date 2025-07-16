import asyncio
# ERROR: 'calculate_position_size' is imported from position_sizer, but only a class is defined there. Implement a module-level function or update the import to use the class method.
# ERROR: 'log_trade_action' is imported from logger, but logger.py does not exist. Implement logger.py or update the import to use a valid logger.
# ERROR: 'record_open_trade' is imported from state_manager, but is not defined there. Implement this function or update the import.
# ERROR: 'get_current_spread', 'get_atr_value', and 'get_signal_hash' are imported from utils, but utils.py does not exist. Implement these functions or update the import.

MAX_SPREAD_PIPS = 2.0
MAX_TRADES_PER_DAY = 10
MAX_GLOBAL_TRADES = 50
MIN_TIME_BETWEEN_TRADES_SEC = 6

trade_locks = {}

async def can_trade(instrument, state):
    from time import time

    # Prevent over-trading globally or per instrument
    if len(state.get("open_trades", [])) >= MAX_GLOBAL_TRADES:
        return False, "Max global trades reached."

    if state["daily_trade_count"].get(instrument, 0) >= MAX_TRADES_PER_DAY:
        return False, f"Max trades for {instrument} today."

    last_time = state["last_trade_time"].get(instrument, 0)
    if time() - last_time < MIN_TIME_BETWEEN_TRADES_SEC:
        return False, f"Cooldown not passed for {instrument}."

    return True, ""

async def execute_trade(signal, account_summary, state):
    instrument = signal["instrument"]
    direction = signal["direction"]
    spread = await get_current_spread(instrument)
    atr = await get_atr_value(instrument)

    if spread > MAX_SPREAD_PIPS:
        return f"Spread too high on {instrument} ({spread:.2f} pips)"

    can, reason = await can_trade(instrument, state)
    if not can:
        return reason

    if instrument in trade_locks:
        return f"Trade already in progress for {instrument}."

    trade_locks[instrument] = True
    client = OandaClient()

    try:
        signal_hash = get_signal_hash(signal)
        if signal_hash in state.get("recent_signals", []):
            return f"Duplicate signal skipped for {instrument}."

        size = await calculate_position_size(instrument, account_summary, atr)
        order_result = client.place_order(instrument, size if direction == "buy" else -size)

        if order_result.get("errorMessage"):
            return f"Order failed: {order_result['errorMessage']}"

        trade_id = order_result["tradeOpened"]["tradeID"]
        await record_open_trade(trade_id, instrument, direction, size, atr)
        await log_trade_action(f"Executed {direction.upper()} on {instrument} for {size} units (ATR: {atr:.2f})")

        return f"Trade executed: {instrument} {direction} x{size}"
    except Exception as e:
        return f"Trade error: {e}"
    finally:
        trade_locks.pop(instrument, None)
