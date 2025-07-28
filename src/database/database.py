import aiosqlite
from loguru import logger
from datetime import datetime
from src.config import DB_NAME


async def initialize_db():
    logger.info("Инициализация базы данных...")
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    subscription_end_date DATE,
                    last_application_date DATETIME
                )
            """)
            await db.commit()
            logger.info("Таблица users успешно создана или уже существует.")
    except aiosqlite.Error as e:
        logger.error(f"Ошибка при создании таблицы users: {e}")
        raise
    finally:
        logger.info("Инициализация базы данных завершена.")


async def add_user(user_id: int, full_name: str, username: str | None):
    last_application_date = datetime.now()

    if username:
        username = username.lower()
    
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT status FROM users WHERE user_id = ?", (user_id,))
            user = await cursor.fetchone()
            if user:
                await db.execute(
                    "UPDATE users SET full_name = ?, username = ?, last_application_date = ? WHERE user_id = ?",
                    (full_name, username, last_application_date, user_id)
                )
            else:
                await db.execute(
                    "INSERT INTO users (user_id, full_name, username, status, last_application_date) VALUES (?, ?, ?, ?, ?)",
                    (user_id, full_name, username, 'pending', last_application_date)
                )
            await db.commit()
            logger.info(f"Пользователь {user_id} добавлен/обновлен в БД.")
    except aiosqlite.Error as e:
        logger.error(f"Ошибка при добавлении/обновлении пользователя {user_id}: {e}")
        raise


async def get_user(user_id: int) -> dict | None:
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = await cursor.fetchone()
            return dict(user) if user else None
    except aiosqlite.Error as e:
        logger.error(f"Ошибка при получении пользователя {user_id}: {e}")
        raise


async def update_user_status(user_id: int, status: str):
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET status = ? WHERE user_id = ?", (status, user_id))
            await db.commit()
            logger.info(f"Статус пользователя {user_id} обновлен на {status}.")
    except aiosqlite.Error as e:
        logger.error(f"Ошибка при обновлении статуса пользователя {user_id}: {e}")
        raise


async def update_subscription(user_id: int, end_date: str):
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "UPDATE users SET status = 'active', subscription_end_date = ? WHERE user_id = ?",
                (end_date, user_id)
            )
            await db.commit()
            logger.info(f"Подписка для пользователя {user_id} обновлена до {end_date}.")
    except aiosqlite.Error as e:
        logger.error(f"Ошибка при обновлении подписки для пользователя {user_id}: {e}")
        raise


async def _execute_user_query(query: str, params: tuple) -> list[dict]:
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            users = await cursor.fetchall()
            return [dict(row) for row in users]
    except aiosqlite.Error as e:
        logger.error(f"Ошибка при выполнении запроса пользователей: {e}")
        raise

async def get_users_by_status(status: str) -> list[dict]:
    return await _execute_user_query("""
        SELECT * FROM users 
        WHERE status = ? 
        ORDER BY subscription_end_date IS NULL, subscription_end_date ASC
    """, (status,))

async def get_users_expiring_soon(status: str = 'active', days: int = 10) -> list[dict]:
    return await _execute_user_query("""
        SELECT * FROM users 
        WHERE status = ? 
        AND subscription_end_date IS NOT NULL
        AND subscription_end_date <= date('now', '+' || ? || ' days')
        AND subscription_end_date >= date('now')
        ORDER BY subscription_end_date ASC
    """, (status, days))

async def get_all_users() -> list[dict]:
    return await _execute_user_query("SELECT * FROM users", ())


async def find_user_by_id_or_username(identifier: str) -> dict | None:    
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            db.row_factory = aiosqlite.Row
            if identifier.startswith('@'):
                username = identifier[1:].lower() 
                cursor = await db.execute("SELECT * FROM users WHERE username = ?", (username,))
            else:
                try:
                    user_id = int(identifier)
                    cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                except ValueError:
                    return None
            user = await cursor.fetchone()
            return dict(user) if user else None
    except aiosqlite.Error as e:
        logger.error(f"Ошибка при поиске пользователя по '{identifier}': {e}")
        raise 