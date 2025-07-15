# trade_closer.py

import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger("trade_closer")

def parse_oanda_time(time_str: str) -> datetime:
    """Clean and parse extended-precision OANDA timestamps safely."""
    time_str = time_str.replace("Z", "+00:00")
    pattern = r'(\.\d{6})\d*'
    fixed_str = re.sub(pattern, r'\1', time_str)
    return datetime.fromisoformat(fixed_str)

class TradeCloser:
    def __init__(self, oanda_client, position_sizer):
        self.oanda = oanda_client
        self.position_sizer = position_sizer
        self.trailing_stop_pips = 15
        self.min_profit_threshold = 3.0  # in pips
        self.max_trade_duration = timedelta(hours=2)
        self.min_risk_reward = 1.2

    async def monitor_trades(self):
        open_trades = await self.oanda.get_open_trades()
        for trade in open_trades:
            await self._evaluate_trade(trade)

    async def _evaluate_trade(self, trade):
        trade_id = trade["id"]
        instrument = trade["instrument"]
        open_time = parse_oanda_time(trade["openTime"])
        current_price = await self.oanda.get_price(instrument)

        unrealized_pl = float(trade.get("unrealizedPL", 0))
        initial_margin = float(trade.get("initialMarginRequired", 1))  # Avoid div by zero
        duration = datetime.now(open_time.tzinfo) - open_time

        if duration > self.max_trade_duration:
            logger.info(f"Trade {trade_id} held too long ({duration}), closing")
            await self._close_trade(trade_id, instrument)
            return

        rr_ratio = unrealized_pl / initial_margin if initial_margin > 0 else 0

        if unrealized_pl >= self.min_profit_threshold and rr_ratio >= self.min_risk_reward:
            logger.info(f"Trade {trade_id} meets PL threshold (PL: {unrealized_pl}, RR: {rr_ratio:.2f}), closing")
            await self._close_trade(trade_id, instrument)
            return

        entry_price = float(trade["price"])
        is_short = trade["currentUnits"].startswith("-")

        pip_size = 0.01 if instrument.endswith("JPY") else 0.0001
        stop_distance = self.trailing_stop_pips * pip_size

        if is_short:
            stop_price = entry_price + stop_distance
            if current_price >= stop_price:
                logger.info(f"Trade {trade_id} hit trailing stop (short), closing")
                await self._close_trade(trade_id, instrument)
        else:
            stop_price = entry_price - stop_distance
            if current_price <= stop_price:
                logger.info(f"Trade {trade_id} hit trailing stop (long), closing")
                await self._close_trade(trade_id, instrument)

    async def _close_trade(self, trade_id, instrument):
        success, _ = await self.oanda.close_trade(trade_id)
        if success:
            self.position_sizer.close_trade(instrument)
            logger.info(f"Trade {trade_id} closed successfully")
        else:
            logger.error(f"Failed to close trade {trade_id}")