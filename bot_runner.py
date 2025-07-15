import asyncio
import logging
import nest_asyncio
from telegram_bot import TelegramBot

logging.basicConfig(level=logging.INFO)

async def main():
    bot = TelegramBot()
    await bot.app.initialize()
    await bot.app.start()
    await bot.app.updater.start_polling()
    # Hold the program open forever until externally stopped (ctrl+c)
    await asyncio.Event().wait()

if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(main())