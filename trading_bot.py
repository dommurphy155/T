import asyncio
from instrument_selector import select_instruments
from strategy import generate_signals
from trade_executor import execute_trade
from state_manager import StateManager
from oanda_client import get_account_summary
from telegram_bot import send_update
from logger import log_info
from datetime import datetime
import time
from typing import Any

SCAN_INTERVAL = 60  # seconds

def get_next_trade_time(*args: Any, **kwargs: Any) -> str:
    # Stub: Replace with real next trade time logic
    return "N/A"

def get_last_signal_breakdown(*args: Any, **kwargs: Any) -> str:
    # Stub: Replace with real signal breakdown logic
    return "No breakdown available."

async def trading_loop():
    state_manager = StateManager()
    state_manager.load_state()
    last_reset_day = datetime.utcnow().day

    while True:
        try:
            current_day = datetime.utcnow().day
            if current_day != last_reset_day:
                # Reset daily counters using state_manager's state dict
                state = state_manager.get_all()
                if 'daily_trades' in state:
                    state['daily_trades'] = 0
                if 'daily_profit' in state:
                    state['daily_profit'] = 0.0
                if 'daily_loss' in state:
                    state['daily_loss'] = 0.0
                last_reset_day = current_day
                await log_info("Daily counters reset.")

            instruments = await select_instruments()
            account_summary = await get_account_summary()
            signals = await generate_signals(instruments)

            tasks = []
            for signal in signals:
                task = execute_and_notify(signal, account_summary, state_manager)
                tasks.append(task)

            await asyncio.gather(*tasks)
            state_manager.save()

        except Exception as e:
            await log_info(f"Trading loop error: {e}")

        await asyncio.sleep(SCAN_INTERVAL)

async def execute_and_notify(signal, account_summary, state_manager):
    result = await execute_trade(signal, account_summary, state_manager.get_all())
    await send_update(result)
    await log_info(result)

if __name__ == "__main__":
    asyncio.run(trading_loop())
