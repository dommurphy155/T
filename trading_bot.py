import os
import logging
import asyncio
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, Dict, List
from oanda_client import OandaClient
from position_sizer import PositionSizer
from trade_executor import TradeExecutor
from trade_closer import TradeCloser

logger = logging.getLogger("trading_bot")

@dataclass
class TradeResult:
    success: bool
    instrument: str = ""
    units: int = 0
    cost_gbp: Optional[float] = None
    expected_roi: Optional[float] = None
    entry_price: Optional[float] = None
    trade_id: Optional[str] = None
    error: Optional[str] = None

@dataclass
class DailyReport:
    total_pnl: float = 0.0
    total_trades: int = 0
    win_rate: float = 0.0
    biggest_winner: float = 0.0
    biggest_loser: float = 0.0
    open_positions: int = 0
    performance_log: str = ""
    expected_roi: Optional[float] = None

class TradingBot:
    def __init__(self):
        api_key = os.getenv("OANDA_API_KEY")
        account_id = os.getenv("OANDA_ACCOUNT_ID")

        if not api_key or not account_id:
            raise ValueError("OANDA_API_KEY and OANDA_ACCOUNT_ID must be set in environment variables.")

        self.oanda = OandaClient(api_key, account_id)
        self.position_sizer = PositionSizer(self.oanda, max_risk=0.015, max_open_trades=50)
        self.trade_executor = TradeExecutor(self.oanda, self.position_sizer)
        self.trade_closer = TradeCloser(self.oanda, self.position_sizer)
        self.instruments = ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CHF"]
        
        # Auto-trading state
        self.auto_trading = False
        self.daily_trade_count = 0
        self.max_daily_trades = 10
        self.last_reset_date = datetime.now().date()
        self.monitoring_task = None
        
        # Performance tracking
        self.daily_stats = {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "total_pnl": 0.0,
            "biggest_winner": 0.0,
            "biggest_loser": 0.0
        }

    def is_market_open(self) -> bool:
        """Check if forex market is open (24/5 market)"""
        now = datetime.utcnow()
        # Forex market is closed from Friday 22:00 UTC to Sunday 22:00 UTC
        weekday = now.weekday()  # 0=Monday, 6=Sunday
        
        if weekday == 5:  # Saturday
            return False
        elif weekday == 6:  # Sunday
            return now.hour >= 22  # Opens at 22:00 UTC Sunday
        elif weekday == 4:  # Friday
            return now.hour < 22  # Closes at 22:00 UTC Friday
        else:
            return True  # Monday-Thursday always open

    def reset_daily_counter(self):
        """Reset daily trade counter if new day"""
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.daily_trade_count = 0
            self.last_reset_date = today
            self.daily_stats = {
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "total_pnl": 0.0,
                "biggest_winner": 0.0,
                "biggest_loser": 0.0
            }

    async def start_auto_trading(self):
        """Start auto-trading every 5 minutes"""
        self.auto_trading = True
        logger.info("Auto-trading started - will trade every 5 minutes during market hours")
        
        while self.auto_trading:
            try:
                self.reset_daily_counter()
                
                if self.is_market_open() and self.daily_trade_count < self.max_daily_trades:
                    await self.run()
                    await asyncio.sleep(300)  # 5 minutes
                else:
                    if not self.is_market_open():
                        logger.info("Market closed - waiting for next session")
                        await asyncio.sleep(3600)  # Check every hour when closed
                    else:
                        logger.info(f"Daily trade limit reached ({self.daily_trade_count}/{self.max_daily_trades})")
                        await asyncio.sleep(300)
                        
            except Exception as e:
                logger.error(f"Auto-trading error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error

    async def stop_auto_trading(self):
        """Stop auto-trading"""
        self.auto_trading = False
        logger.info("Auto-trading stopped")

    async def start_monitoring(self):
        """Start continuous trade monitoring every minute"""
        if self.monitoring_task is None:
            self.monitoring_task = asyncio.create_task(self._monitor_loop())

    async def stop_monitoring(self):
        """Stop continuous monitoring"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            self.monitoring_task = None

    async def _monitor_loop(self):
        """Monitor trades every minute"""
        while True:
            try:
                await self.trade_closer.monitor_trades()
                await asyncio.sleep(60)  # Every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(60)

    async def run(self) -> Optional[TradeResult]:
        """Execute one trade attempt"""
        self.reset_daily_counter()
        
        if not self.is_market_open():
            return TradeResult(success=False, error="Market is closed")
            
        if self.daily_trade_count >= self.max_daily_trades:
            return TradeResult(success=False, error="Daily trade limit reached")

        # Close existing trades first if this is initial run
        await self.trade_closer.monitor_trades()
        
        # Try to place one trade
        for instrument in self.instruments:
            result = await self._try_trade(instrument)
            if result.success:
                self.daily_trade_count += 1
                self.daily_stats["trades"] += 1
                return result
                
        return TradeResult(success=False, error="No trades placed - all instruments on cooldown")

    async def _try_trade(self, instrument: str) -> TradeResult:
        """Try to place a trade on specific instrument"""
        try:
            stop_loss_pips = 15.0
            units = await self.position_sizer.calculate_units(instrument, stop_loss_pips)
            
            if units <= 0:
                return TradeResult(success=False, instrument=instrument, error="Units calculated as 0 or blocked")

            # Get current price for cost calculation
            price = await self.oanda.get_price(instrument)
            if price is None:
                return TradeResult(success=False, instrument=instrument, error="Could not get price")

            # Execute trade
            success, response = await self.trade_executor.execute_trade(instrument, units)
            
            if not success:
                return TradeResult(success=False, instrument=instrument, error=str(response))

            # Calculate cost in GBP (approximate)
            cost_gbp = units * price * 0.8  # Rough GBP conversion
            expected_roi = 0.015  # 1.5% expected return
            
            # Extract trade ID from response
            trade_id = None
            if isinstance(response, dict) and "orderFillTransaction" in response:
                trade_id = response["orderFillTransaction"].get("id")

            return TradeResult(
                success=True,
                instrument=instrument,
                units=units,
                cost_gbp=cost_gbp,
                expected_roi=expected_roi,
                entry_price=price,
                trade_id=trade_id
            )
            
        except Exception as e:
            logger.error(f"Trade attempt failed for {instrument}: {e}")
            return TradeResult(success=False, instrument=instrument, error=str(e))

    async def get_open_trades(self) -> List[Dict]:
        """Get formatted open trades"""
        trades = await self.oanda.get_open_trades()
        formatted_trades = []
        
        for trade in trades:
            formatted_trades.append({
                "instrument": trade.get("instrument", "unknown"),
                "units": trade.get("currentUnits", 0),
                "expected_roi": 0.015,  # 1.5% target
                "unrealized_pl": float(trade.get("unrealizedPL", 0)),
                "open_time": trade.get("openTime", ""),
                "id": trade.get("id", "")
            })
            
        return formatted_trades

    async def get_daily_report(self) -> DailyReport:
        """Generate daily performance report"""
        open_trades = await self.get_open_trades()
        
        # Calculate total unrealized P&L
        total_unrealized_pnl = sum(trade["unrealized_pl"] for trade in open_trades)
        
        # Calculate win rate
        total_completed = self.daily_stats["wins"] + self.daily_stats["losses"]
        win_rate = (self.daily_stats["wins"] / total_completed * 100) if total_completed > 0 else 0
        
        performance_log = f"""
Today's Performance:
• Trades: {self.daily_stats['trades']}
• Completed: {total_completed}
• Win Rate: {win_rate:.1f}%
• Realized P&L: £{self.daily_stats['total_pnl']:.2f}
• Unrealized P&L: £{total_unrealized_pnl:.2f}
• Daily Limit: {self.daily_trade_count}/{self.max_daily_trades}
        """.strip()
        
        return DailyReport(
            total_pnl=self.daily_stats['total_pnl'] + total_unrealized_pnl,
            total_trades=self.daily_stats['trades'],
            win_rate=win_rate,
            biggest_winner=self.daily_stats['biggest_winner'],
            biggest_loser=self.daily_stats['biggest_loser'],
            open_positions=len(open_trades),
            performance_log=performance_log,
            expected_roi=0.015
        )

    async def get_weekly_report(self) -> DailyReport:
        """Generate weekly performance report (same format as daily for now)"""
        daily_report = await self.get_daily_report()
        daily_report.performance_log = daily_report.performance_log.replace("Today's", "This Week's")
        return daily_report

    async def run_diagnostics(self) -> str:
        """Run system diagnostics"""
        import psutil
        import tracemalloc
        
        # Get system info
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        # Get memory usage
        try:
            current, peak = tracemalloc.get_traced_memory()
            memory_usage = f"{current / 1024 / 1024:.1f} MB"
        except:
            memory_usage = "N/A"
        
        # Get open trades count
        open_trades = await self.get_open_trades()
        
        # Get last trade time
        last_trade_time = "Never"
        if hasattr(self.position_sizer, 'trade_state'):
            last_times = self.position_sizer.trade_state.get('last_trade_time', {})
            if last_times:
                latest = max(last_times.values())
                last_trade_time = latest.strftime("%Y-%m-%d %H:%M:%S") if hasattr(latest, 'strftime') else str(latest)
        
        diagnostics = f"""
System Diagnostics:
• CPU Usage: {cpu_percent}%
• Memory: {memory.percent}% ({memory_usage})
• Open Trades: {len(open_trades)}
• Auto-trading: {"ON" if self.auto_trading else "OFF"}
• Market Status: {"OPEN" if self.is_market_open() else "CLOSED"}
• Daily Trades: {self.daily_trade_count}/{self.max_daily_trades}
• Last Trade: {last_trade_time}
• Error Count: 0 (tracking not implemented)
        """.strip()
        
        return diagnostics

    async def close_all_trades(self):
        """Close all existing trades"""
        trades = await self.oanda.get_open_trades()
        closed_count = 0
        
        for trade in trades:
            trade_id = trade.get("id")
            instrument = trade.get("instrument")
            
            if trade_id:
                success, _ = await self.oanda.close_trade(trade_id)
                if success:
                    closed_count += 1
                    self.position_sizer.close_trade(instrument)
                    logger.info(f"Closed trade {trade_id} on {instrument}")
        
        logger.info(f"Closed {closed_count} trades")
        return closed_count

    def update_trade_result(self, pnl: float, won: bool):
        """Update daily statistics when trade closes"""
        self.daily_stats["total_pnl"] += pnl
        
        if won:
            self.daily_stats["wins"] += 1
            if pnl > self.daily_stats["biggest_winner"]:
                self.daily_stats["biggest_winner"] = pnl
        else:
            self.daily_stats["losses"] += 1
            if pnl < self.daily_stats["biggest_loser"]:
                self.daily_stats["biggest_loser"] = pnl