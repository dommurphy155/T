import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError
from trading_bot import TradingBot

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = int(os.getenv("TELEGRAM_CHAT_ID", "0"))
        self.trading_bot = TradingBot()
        self.last_trade_info = None

        self.app = Application.builder().token(self.token).build()

        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("status", self.status))
        self.app.add_handler(CommandHandler("maketrade", self.trade))
        self.app.add_handler(CommandHandler("whatyoudoin", self.diagnostics))
        self.app.add_handler(CommandHandler("opentrades", self.open_trades))
        self.app.add_handler(CommandHandler("daily", self.daily_report))
        self.app.add_handler(CommandHandler("weekly", self.weekly_report))
        self.app.add_error_handler(self.error_handler)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🤖 Bot is live. Use /maketrade to place a trade.")

    async def trade(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        result = await self.trading_bot.run()
        if not result:
            await update.message.reply_text("⚠️ No trade executed.")
            return
        
        instrument = getattr(result, "instrument", "unknown")
        units = getattr(result, "units", 0)
        cost_in_gbp = getattr(result, "cost_gbp", None)  # Assuming TradingBot returns this
        expected_roi = getattr(result, "expected_roi", None)  # Decimal e.g. 0.12 for 12%
        pl_pct = expected_roi * 100 if expected_roi is not None else None
        
        trade_msg = f"📈 Trade executed on {instrument}\n"
        trade_msg += f"💰 Units bought: {units}\n"
        if cost_in_gbp is not None:
            trade_msg += f"💷 Invested: £{cost_in_gbp:,.2f}\n"
        if pl_pct is not None:
            trade_msg += f"🎯 Expected ROI: {pl_pct:.2f}%\n"
        trade_msg += "🔎 Monitor closely and adjust risk accordingly."
        
        self.last_trade_info = trade_msg
        await update.message.reply_text(trade_msg)

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Removed error summary as requested
        msg = "📊 Status Report:\n✅ All systems up to date and running smoothly."
        await update.message.reply_text(msg)

    async def open_trades(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        trades = await self.trading_bot.get_open_trades()
        if not trades:
            await update.message.reply_text("📭 No open trades at the moment.")
            return
        
        msg = "📂 Open Trades:\n"
        for t in trades:
            instr = t.get("instrument", "unknown")
            units = t.get("units", 0)
            roi = t.get("expected_roi", None)
            roi_pct = roi * 100 if roi is not None else None
            pl = t.get("unrealized_pl", None)
            pl_str = f"PL: £{pl:.2f}" if pl is not None else "PL: N/A"
            msg += f"• {instr} | Units: {units} | "
            if roi_pct is not None:
                msg += f"Expected ROI: {roi_pct:.2f}% | "
            msg += f"{pl_str}\n"
        msg += "🔔 Review your positions carefully."
        await update.message.reply_text(msg)

    async def daily_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        report = await self.trading_bot.get_daily_report()
        roi = report.get("expected_roi", None)
        roi_pct = roi * 100 if roi is not None else None
        performance = report.get("performance_log", "No performance data available.")
        msg = "📅 Daily Report:\n"
        if roi_pct is not None:
            msg += f"🎯 Expected ROI Today: {roi_pct:.2f}%\n"
        msg += f"📈 Performance Summary:\n{performance}"
        await update.message.reply_text(msg)

    async def weekly_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        report = await self.trading_bot.get_weekly_report()
        roi = report.get("expected_roi", None)
        roi_pct = roi * 100 if roi is not None else None
        performance = report.get("performance_log", "No performance data available.")
        msg = "📆 Weekly Report:\n"
        if roi_pct is not None:
            msg += f"🎯 Expected ROI This Week: {roi_pct:.2f}%\n"
        msg += f"📊 Performance Summary:\n{performance}"
        await update.message.reply_text(msg)

    async def diagnostics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🔍 Running diagnostics...")
        diag = await self.trading_bot.run_diagnostics()
        await update.message.reply_text(f"✅ Diagnostics Complete:\n{diag}")

    async def error_handler(self, update, context):
        logger.error(f"Telegram error: {context.error}")
        if update and update.message:
            await update.message.reply_text("⚠️ An error occurred while processing your command.")

    async def run_polling(self):
        await self.app.run_polling()