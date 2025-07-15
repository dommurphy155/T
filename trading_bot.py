import os
import logging
from oanda_client import OandaClient
from position_sizer import PositionSizer
from trade_executor import TradeExecutor
from trade_closer import TradeCloser

logger = logging.getLogger("trading_bot")

class TradingBot:
    def __init__(self):
        api_key = os.getenv("OANDA_API_KEY")
        account_id = os.getenv("OANDA_ACCOUNT_ID")

        if not api_key or not account_id:
            raise ValueError("OANDA_API_KEY and OANDA_ACCOUNT_ID must be set in environment variables.")

        self.oanda = OandaClient(api_key, account_id)
        self.position_sizer = PositionSizer(self.oanda)
        self.trade_executor = TradeExecutor(self.oanda, self.position_sizer)
        self.trade_closer = TradeCloser(self.oanda, self.position_sizer)
        self.instruments = ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CHF"]

    async def run(self):
        # Try trades on all instruments
        for instrument in self.instruments:
            await self._try_trade(instrument)
        # Monitor and close trades
        await self.trade_closer.monitor_trades()

    async def _try_trade(self, instrument):
        stop_loss_pips = 10.0
        units = await self.position_sizer.calculate_units(instrument, stop_loss_pips)
        if units > 0:
            await self.trade_executor.execute_trade(instrument, units)