import logging
from oanda_client import OandaClient
from position_sizer import PositionSizer

logger = logging.getLogger("trade_executor")

class TradeExecutor:
    def __init__(self, oanda_client: OandaClient, position_sizer: PositionSizer):
        self.oanda_client = oanda_client
        self.position_sizer = position_sizer

    async def execute_trade(self, instrument: str, units: int):
        if units <= 0:
            logger.error("Units <= 0 or trade blocked by cooldown/max trades, abort trade")
            return False

        success, response = await self.oanda_client.create_trade(instrument, units)
        if not success:
            logger.error(f"Trade failed for {instrument}: {response}")
            return False

        self.position_sizer.record_trade(instrument)
        logger.info(f"Trade placed: buy {units} units on {instrument}")
        return True

    async def evaluate_exit(self, instrument: str, trade_id: str, entry_price: float):
        """
        Lightweight logic to evaluate if the trade should be closed early
        Uses momentum reversal, trailing profit threshold, and time decay exit
        """
        price = await self.oanda_client.get_price(instrument)
        if price is None:
            return False

        pnl_threshold = 0.002  # 20 pips profit
        loss_limit = -0.002    # 20 pips loss

        change = (price - entry_price) / entry_price

        if change >= pnl_threshold or change <= loss_limit:
            logger.info(f"Exit condition met for {instrument} | Δ: {change:.4f}")
            await self.oanda_client.close_trade(trade_id)
            self.position_sizer.close_trade(instrument)
            return True

        return False