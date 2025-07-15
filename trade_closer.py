import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List

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
        self.min_profit_threshold = 5.0  # in pips
        self.max_trade_duration = timedelta(hours=2)  # Hard 2-hour limit
        self.min_risk_reward = 1.2
        self.price_history = {}  # Track price history for momentum detection

    async def monitor_trades(self):
        """Monitor all open trades and apply exit strategies"""
        try:
            open_trades = await self.oanda.get_open_trades()
            logger.info(f"Monitoring {len(open_trades)} open trades")
            
            for trade in open_trades:
                await self._evaluate_trade(trade)
                
            # Sync position sizer with actual trade count
            await self.position_sizer.sync_open_trades()
            
        except Exception as e:
            logger.error(f"Error monitoring trades: {e}")

    async def _evaluate_trade(self, trade: Dict):
        """Evaluate a single trade for exit conditions"""
        try:
            trade_id = trade["id"]
            instrument = trade["instrument"]
            open_time = parse_oanda_time(trade["openTime"])
            current_price = await self.oanda.get_price(instrument)
            
            if current_price is None:
                logger.warning(f"Could not get price for {instrument}")
                return

            unrealized_pl = float(trade.get("unrealizedPL", 0))
            entry_price = float(trade["price"])
            units = int(trade["currentUnits"])
            is_long = units > 0
            
            # Convert to UTC for comparison
            now_utc = datetime.now(timezone.utc)
            if open_time.tzinfo is None:
                open_time = open_time.replace(tzinfo=timezone.utc)
            
            duration = now_utc - open_time

            # 1. HARD 2-HOUR TIMEOUT - Force close regardless of P&L
            if duration > self.max_trade_duration:
                logger.info(f"Trade {trade_id} hit 2-hour timeout, forcing closure")
                await self._close_trade(trade_id, instrument, "timeout")
                return

            # 2. DYNAMIC PROFIT TARGET based on volatility/momentum
            if await self._check_profit_target(trade_id, instrument, entry_price, current_price, unrealized_pl, is_long):
                return

            # 3. TRAILING STOP LOSS - Lock in profits
            if await self._check_trailing_stop(trade_id, instrument, entry_price, current_price, is_long):
                return

            # 4. MOMENTUM REVERSAL DETECTION
            if await self._check_momentum_reversal(trade_id, instrument, current_price, is_long):
                return

            # 5. MINIMUM LOSS THRESHOLD - Cut losses early
            if await self._check_loss_threshold(trade_id, instrument, unrealized_pl):
                return

            # Update price history for momentum detection
            self._update_price_history(instrument, current_price)

        except Exception as e:
            logger.error(f"Error evaluating trade {trade.get('id', 'unknown')}: {e}")

    async def _check_profit_target(self, trade_id: str, instrument: str, entry_price: float, 
                                 current_price: float, unrealized_pl: float, is_long: bool) -> bool:
        """Check dynamic profit targets based on volatility"""
        pip_size = 0.01 if instrument.endswith("JPY") else 0.0001
        
        # Calculate current profit in pips
        if is_long:
            profit_pips = (current_price - entry_price) / pip_size
        else:
            profit_pips = (entry_price - current_price) / pip_size

        # Dynamic profit target based on time held and volatility
        base_target = 10.0  # Base 10 pips
        volatility_multiplier = self._get_volatility_multiplier(instrument)
        dynamic_target = base_target * volatility_multiplier

        # If profitable above dynamic target, close
        if profit_pips >= dynamic_target and unrealized_pl > 0:
            logger.info(f"Trade {trade_id} hit dynamic profit target: {profit_pips:.1f} pips (target: {dynamic_target:.1f})")
            await self._close_trade(trade_id, instrument, "profit_target")
            return True

        return False

    async def _check_trailing_stop(self, trade_id: str, instrument: str, entry_price: float, 
                                 current_price: float, is_long: bool) -> bool:
        """Check trailing stop loss"""
        pip_size = 0.01 if instrument.endswith("JPY") else 0.0001
        stop_distance = self.trailing_stop_pips * pip_size

        if is_long:
            # For long positions, stop is below current price
            stop_price = current_price - stop_distance
            # Only trigger if price has moved significantly in our favor first
            if current_price > entry_price + (stop_distance * 0.5):  # At least 7.5 pips profit
                if entry_price <= stop_price:  # Stop has moved above entry
                    logger.info(f"Trade {trade_id} hit trailing stop (long): {current_price:.5f} -> {stop_price:.5f}")
                    await self._close_trade(trade_id, instrument, "trailing_stop")
                    return True
        else:
            # For short positions, stop is above current price
            stop_price = current_price + stop_distance
            # Only trigger if price has moved significantly in our favor first
            if current_price < entry_price - (stop_distance * 0.5):  # At least 7.5 pips profit
                if entry_price >= stop_price:  # Stop has moved below entry
                    logger.info(f"Trade {trade_id} hit trailing stop (short): {current_price:.5f} -> {stop_price:.5f}")
                    await self._close_trade(trade_id, instrument, "trailing_stop")
                    return True

        return False

    async def _check_momentum_reversal(self, trade_id: str, instrument: str, current_price: float, is_long: bool) -> bool:
        """Check for momentum reversal using price history"""
        if instrument not in self.price_history or len(self.price_history[instrument]) < 3:
            return False

        prices = self.price_history[instrument][-3:]  # Last 3 prices
        
        # Simple momentum reversal detection
        if len(prices) == 3:
            if is_long:
                # For long positions, look for downward momentum
                if prices[0] > prices[1] > prices[2]:  # Consistent decline
                    logger.info(f"Trade {trade_id} showing downward momentum reversal")
                    await self._close_trade(trade_id, instrument, "momentum_reversal")
                    return True
            else:
                # For short positions, look for upward momentum
                if prices[0] 