from aiogram import Router, F, Bot
from aiogram.filters import Command, BaseFilter
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
from datetime import datetime
import os
import glob

from src.config import ADMIN_ID, CHANNEL_ID
from src.database import database as db
from src.utils.user_utils import get_user_mention
from src.keyboards.inline import get_subscription_keyboard
from src.utils.filter import setup_admin_router
from src.utils.scheduler import check_subscriptions_with_stats

admin_router = Router()
admin_router = setup_admin_router(admin_router)

@admin_router.message(Command("start"))
async def start_command(message: Message):
    """
    Приветственное сообщение при запуске бота.
    """
    welcome_text = (
        "👋 <b>Добро пожаловать в Checkup-Subs Bot!</b>\n\n"
        "🤖 Я помогу вам управлять подписками пользователей в вашем канале.\n\n"
        "📋 <b>Что я умею:</b>\n"
        "- Автоматически обрабатывать заявки на вступление\n"
        "- Управлять подписками пользователей\n"
        "- Проверять и очищать истекшие подписки\n"
        "- Предоставлять статистику\n\n"
        "🔧 <b>Быстрый старт:</b>\n"
        "- <code>/stats</code> - посмотреть статистику подписок\n"
        "- <code>/help</code> - полный список команд\n\n"
        "🚀 <b>Бот готов к работе!</b>"
    )
    
    await message.answer(welcome_text, parse_mode='HTML')


@admin_router.message(Command("help"))
async def help_command(message: Message):
    """
    Показывает список всех доступных команд администратора.
    """
    help_text = (
        "🤖 <b>Команды администратора</b>\n\n"
        "🚀 <b>Основные команды:</b>\n"
        "- <code>/start</code> - приветственное сообщение\n"
        "- <code>/help</code> - эта справка\n\n"
        "👥 <b>Управление пользователями:</b>\n"
        "- <code>/ban @username</code> - заблокировать пользователя\n"
        "- <code>/unban @username</code> - разблокировать пользователя\n"
        "- <code>/extend @username</code> - продлить подписку\n\n"
        "📊 <b>Просмотр списков:</b>\n"
        "- <code>/active</code> - активные пользователи\n"
        "- <code>/expiring</code> - истекающие подписки (10 дней)\n"
        "- <code>/all</code> - все пользователи\n\n"
        "🔍 <b>Проверка подписок:</b>\n"
        "- <code>/check_subs</code> - проверить и очистить истекшие\n\n"
        "📋 <b>Системные команды:</b>\n"
        "- <code>/log</code> - получить файлы логов\n\n"
        "💡 <b>Примеры:</b>\n"
        "<code>/ban @john_doe</code>\n"
        "<code>/extend 123456789</code>\n"
        "<code>/unban @jane_smith</code>"
    )
    
    await message.answer(help_text, parse_mode='HTML')

# Функция бана
async def process_ban(user_id: int, bot: Bot):
    logger.info(f"Начало процесса блокировки пользователя {user_id}.")
    await db.update_user_status(user_id, 'banned')
    try:
        await bot.ban_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        await bot.unban_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        logger.info(f"Пользователь {user_id} был удален из канала.")
    except Exception as e:
        logger.warning(f"Не удалось удалить пользователя {user_id} из чата (возможно, его там нет): {e}")
    try:
        # await bot.decline_chat_join_request(chat_id=CHANNEL_ID, user_id=user_id, hide_request=True)
        logger.info(f"Заявка на вступление от {user_id} отклонена.")
    except Exception as e:
        logger.warning(f"Не удалось отклонить заявку от {user_id} (возможно, ее нет): {e}")

@admin_router.message(Command("ban"))
async def ban_user_command(message: Message, bot: Bot):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите ID или @username пользователя.\nПример: `/ban 123456` или `/ban @nickname`")
        return
    
    identifier = args[1]
    user_data = await db.find_user_by_id_or_username(identifier)

    if not user_data:
        await message.answer("❌ Пользователь с таким ID или никнеймом не найден в базе данных.")
        return
    
    user_id = user_data['user_id']
    await process_ban(user_id, bot)
    user_mention = get_user_mention(user_data)
    await message.answer(f"🚫 Пользователь <b>{user_mention}</b> заблокирован.", parse_mode='HTML')

@admin_router.message(Command("unban"))
async def unban_user_command(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите ID или @username пользователя.\nПример: `/unban 123456` или `/unban @nickname`")
        return

    identifier = args[1]
    user_data = await db.find_user_by_id_or_username(identifier)

    if not user_data:
        await message.answer("❌ Пользователь с таким ID или никнеймом не найден в базе данных.")
        return
    
    if user_data['status'] != 'banned':
        await message.answer("ℹ️ Этот пользователь не заблокирован.")
        return

    user_id = user_data['user_id']
    await db.update_user_status(user_id, 'rejected')
    user_mention = get_user_mention(user_data)
    await message.answer(f"✅ Пользователь <b>{user_mention}</b> разблокирован. Теперь он может снова подать заявку.", parse_mode='HTML')
    logger.info(f"Пользователь {user_id} разблокирован.")


@admin_router.message(Command("extend"))
async def extend_subscription_command(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите ID или @username пользователя.\nПример: `/extend 123456` или `/extend @nickname`")
        return

    identifier = args[1]
    user_data = await db.find_user_by_id_or_username(identifier)

    if not user_data:
        await message.answer("❌ Пользователь с таким ID или никнеймом не найден в базе данных.")
        return

    user_id = user_data['user_id']
    user_mention = get_user_mention(user_data)
    keyboard = get_subscription_keyboard(user_id)
    
    text = f"Выберите новый срок подписки для пользователя <b>{user_mention}</b>.\n<i>Текущая подписка будет полностью сброшена.</i>"
    
    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')


@admin_router.message(Command("check_subs"))
async def check_subscriptions_command(message: Message, bot: Bot):
    await message.answer("🔄 Запускаю проверку подписок...")
    
    try:
        stats = await check_subscriptions_with_stats(bot)
    except Exception as e:
        logger.error(f"Ошибка при ручной проверке подписок: {e}")
        await message.answer(
            f"❌ Произошла ошибка при проверке подписок:\n{str(e)}\n\n"
            f"Подробности смотрите в логах.",
            parse_mode='HTML'
        )


# Просмотр списка пользователей
USERS_PER_PAGE = 20

async def format_users_page(users: list[dict], page: int, list_type: str) -> tuple[str, object]:    
    if not users:
        return "Список пользователей пуст.", None

    total_pages = (len(users) + USERS_PER_PAGE - 1) // USERS_PER_PAGE
    page = max(1, min(page, total_pages))
    
    start_index = (page - 1) * USERS_PER_PAGE
    end_index = start_index + USERS_PER_PAGE
    page_users = users[start_index:end_index]

    if list_type == 'active':
        type_text = 'активные'
    elif list_type == 'expiring':
        type_text = 'истекающие в ближайшие 10 дней'
    else:
        type_text = 'все'

    text = f"<b>Список пользователей ({type_text}) - Страница {page}/{total_pages}</b>\n\n"
    
    for user in page_users:
        user_mention = get_user_mention(user)
        user_id = user['user_id']
        status = user['status']
        
        if list_type == 'active':
            end_date_str = user.get('subscription_end_date')
            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').strftime('%d.%m.%Y')
                    text += f"ID: <code>{user_id}</code> - {user_mention} - до {end_date}\n"
                except ValueError:
                    text += f"ID: <code>{user_id}</code> - {user_mention} - (неверная дата)\n"
            else:
                 text += f"ID: <code>{user_id}</code> - {user_mention} - (нет даты)\n"
        else:
            end_date_str = user.get('subscription_end_date')
            end_date = "N/A"
            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').strftime('%d.%m.%Y')
                except ValueError:
                    end_date = "неверная дата"
            text += f"ID: <code>{user_id}</code> - {user_mention} - <b>{status}</b> - до {end_date}\n"

    builder = InlineKeyboardBuilder()
    if page > 1:
        builder.button(text="◀️ Назад", callback_data=f"list_{list_type}_{page - 1}")
    
    builder.button(text=f"Стр. {page}/{total_pages}", callback_data="noop")

    if page < total_pages:
        builder.button(text="Вперёд ▶️", callback_data=f"list_{list_type}_{page + 1}")
    
    return text, builder.as_markup()

@admin_router.message(Command("active"))
async def list_active_users(message: Message):
    users = await db.get_users_by_status('active')
    text, keyboard = await format_users_page(users, 1, 'active')
    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

@admin_router.message(Command("expiring"))
async def subscription_stats_command(message: Message):
    users = await db.get_users_expiring_soon('active', days=10)
    text, keyboard = await format_users_page(users, 1, 'expiring')
    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

@admin_router.message(Command("all"))
async def list_all_users(message: Message):
    users = await db.get_all_users()
    text, keyboard = await format_users_page(users, 1, 'all')
    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

@admin_router.callback_query(F.data.startswith("list_"))
async def paginate_list(call: CallbackQuery):
    _, list_type, page_str = call.data.split("_")
    page = int(page_str)

    if list_type == 'active':
        users = await db.get_users_by_status('active')
    elif list_type == 'expiring':
        users = await db.get_users_expiring_soon(10)
    else:
        users = await db.get_all_users()

    text, keyboard = await format_users_page(users, page, list_type)
    
    try:
        await call.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    except Exception as e:
        logger.warning(f"Ошибка при обновлении списка (возможно, текст не изменился): {e}")
    finally:
        await call.answer()

@admin_router.callback_query(F.data == "noop")
async def noop_callback(call: CallbackQuery):
    await call.answer() 

@admin_router.message(Command("log"))
async def send_log_files(message: Message):
    try:
        logs_dir = "logs"
        
        if not os.path.exists(logs_dir):
            await message.answer("📂 Директория с логами не найдена.")
            return
            
        log_files = []
        for pattern in ["*.log", "*.zip"]:
            log_files.extend(glob.glob(os.path.join(logs_dir, pattern)))
        
        if not log_files:
            await message.answer("📄 Файлы логов не найдены.")
            return
        
        log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
        files_to_send = log_files[:2]
        
        await message.answer(f"📋 Отправляю {len(files_to_send)} файл(ов) логов...")
        
        for file_path in files_to_send:
            try:
                file_size = os.path.getsize(file_path)
                file_size_mb = file_size / (1024 * 1024)
                
                if file_size_mb > 200:
                    await message.answer(f"⚠️ Файл {os.path.basename(file_path)} слишком большой ({file_size_mb:.1f}MB) для отправки.")
                    continue
                
                document = FSInputFile(file_path)
                await message.answer_document(
                    document
                )
                logger.info(f"Отправлен файл лога: {file_path}")
                
            except Exception as e:
                await message.answer(f"❌ Ошибка при отправке файла {os.path.basename(file_path)}: {str(e)}")
                logger.error(f"Ошибка при отправке файла лога {file_path}: {e}")
        
        logger.info(f"Команда /log выполнена администратором {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка при выполнении команды /log: {e}")
        await message.answer(f"❌ Произошла ошибка при получении файлов логов: {str(e)}") 