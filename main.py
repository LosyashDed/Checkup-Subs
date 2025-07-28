import asyncio
import os
from loguru import logger
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from src.config import BOT_TOKEN
from src.database.database import initialize_db
from src.handlers.join_requests import join_router
from src.handlers.admin_commands import admin_router
from src.utils.scheduler import setup_scheduler

os.makedirs("logs", exist_ok=True)
logger.add("logs/bot.log", rotation="10 MB", compression="zip", level="INFO")


async def main():
    logger.info("Запуск бота...")

    try:
        await initialize_db()

        bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = Dispatcher()

        dp.include_router(admin_router)
        dp.include_router(join_router)
        
        # Планировщик
        setup_scheduler(bot)

        # await bot.delete_webhook(drop_pending_updates=True)
        logger.info("sБот успешно запущен и готов к работе!")
        
        try:
            await dp.start_polling(bot)
        finally:
            await bot.session.close()
            logger.info("Сессия бота закрыта.")
            
    except Exception as e:
        logger.critical(f"Критическая ошибка при инициализации: {e}")
        raise


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен вручную.")
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске: {e}") 