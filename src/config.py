import os
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID")
DB_NAME = os.getenv("DB_NAME", "database.db")

if not all([BOT_TOKEN, ADMIN_ID, CHANNEL_ID]):
    logger.error("Не удалось загрузить переменные окружения. Убедитесь, что создан файл .env")
    raise ValueError("Отсутствуют необходимые переменные окружения: BOT_TOKEN, ADMIN_ID, CHANNEL_ID")

try:
    ADMIN_ID = int(ADMIN_ID)
    CHANNEL_ID = int(CHANNEL_ID)
except ValueError:
    logger.error("ADMIN_ID и CHANNEL_ID должны быть числами")
    raise ValueError("ADMIN_ID и CHANNEL_ID должны быть целочисленными значениями") 