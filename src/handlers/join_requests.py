from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.types import ChatJoinRequest, CallbackQuery
from loguru import logger

from src.config import ADMIN_ID, CHANNEL_ID
from src.database import database as db
from src.utils.user_utils import get_user_mention
from src.utils.filter import setup_admin_router
from src.handlers.admin_commands import process_ban
from src.keyboards.inline import get_approval_keyboard, get_subscription_keyboard

join_router = Router()
join_router = setup_admin_router(join_router)

# Обработчики
@join_router.chat_join_request(F.chat.id == CHANNEL_ID)
async def handle_join_request(request: ChatJoinRequest, bot: Bot):
    user_id = request.from_user.id
    full_name = request.from_user.full_name
    username = request.from_user.username
    logger.info(f"Получена новая заявка на вступление от {get_user_mention(request.from_user)}")

    await db.add_user(user_id, full_name, username)
    user_data = await db.get_user(user_id)

    if not user_data:
        logger.error(f"Не удалось найти или создать пользователя {user_id} в БД.")
        return

    status = user_data.get('status')

    if status == 'banned':
        await request.decline()
        logger.info(f"Заявка от заблокированного пользователя {user_id} отклонена.")
        return
    elif status == 'active':
        await request.approve()
        logger.info(f"Заявка от активного пользователя {user_id} одобрена автоматически.")
        return

    user_mention = get_user_mention(user_data)
    message_text = f"Новая заявка на вступление.\nПользователь: <b>{user_mention}</b>"

    if status == 'expired':
        end_date_str = user_data.get('subscription_end_date')
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                message_text += f"\n<i>(Предыдущая подписка истекла {end_date.strftime('%d.%m.%Y')})</i>"
            except (ValueError, TypeError):
                 logger.warning(f"Некорректный формат даты '{end_date_str}' для пользователя {user_id}")


    keyboard = get_approval_keyboard(user_id)
    await bot.send_message(ADMIN_ID, message_text, reply_markup=keyboard, parse_mode='HTML')
    logger.info(f"Заявка от {user_id} отправлена администратору на рассмотрение.")

@join_router.callback_query(F.data.startswith("approve_"))
async def approve_user_prompt(call: CallbackQuery):
    user_id = int(call.data.split("_")[1])
    user_data = await db.get_user(user_id)
    if not user_data:
        await call.answer("Пользователь не найден в базе данных.", show_alert=True)
        return

    user_mention = get_user_mention(user_data)
    keyboard = get_subscription_keyboard(user_id)
    await call.message.edit_text(
        f"Выберите длительность подписки для пользователя <b>{user_mention}</b>:",
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    await call.answer()


@join_router.callback_query(F.data.startswith("set_sub_"))
async def set_subscription(call: CallbackQuery, bot: Bot):
    parts = call.data.split("_")
    user_id_str = parts[2]  
    days_str = parts[3]    
    user_id = int(user_id_str)
    days = int(days_str)

    user_data = await db.get_user(user_id)
    if not user_data:
        await call.answer("Пользователь не найден в базе данных.", show_alert=True)
        return

    try:
        try:
            chat_member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
            is_member = chat_member.status in ['member', 'administrator', 'creator']
        except Exception:
            is_member = False

        if not is_member:
            await bot.approve_chat_join_request(chat_id=CHANNEL_ID, user_id=user_id)
            logger.info(f"Заявка пользователя {user_id} одобрена.")
        else:
            logger.info(f"Пользователь {user_id} уже является участником канала.")

        end_date = datetime.now() + timedelta(days=days)
        end_date_str = end_date.strftime('%Y-%m-%d')
        await db.update_subscription(user_id, end_date_str)
        
        user_mention = get_user_mention(user_data)
        await call.message.edit_text(
            f"✅ Готово! Пользователь <b>{user_mention}</b> добавлен в канал до {end_date.strftime('%d.%m.%Y')}.",
            parse_mode='HTML'
        )
        logger.info(f"Подписка пользователя {user_id} обновлена на {days} дней.")
        
    except Exception as e:
        logger.error(f"Не удалось обработать подписку для {user_id}: {e}")
        await call.message.edit_text(f"⚠️ Произошла ошибка при обработке подписки для {user_id}. Подробности в логах.")
    finally:
        await call.answer()

@join_router.callback_query(F.data.startswith("decline_"))
async def decline_user(call: CallbackQuery, bot: Bot):
    user_id = int(call.data.split("_")[1])
    user_data = await db.get_user(user_id)
    if not user_data:
        await call.answer("Пользователь не найден.", show_alert=True)
        return

    try:
        # await bot.decline_chat_join_request(chat_id=CHANNEL_ID, user_id=user_id, hide_request=True)
        await db.update_user_status(user_id, 'rejected')
        user_mention = get_user_mention(user_data)
        await call.message.edit_text(f"❌ Заявка от пользователя <b>{user_mention}</b> отклонена.", parse_mode='HTML')
        logger.info(f"Заявка от {user_id} отклонена администратором.")
    except Exception as e:
        logger.error(f"Не удалось отклонить заявку для {user_id}: {e}")
        await call.message.edit_text(f"⚠️ Произошла ошибка при отклонении заявки для {user_id}.")
    finally:
        await call.answer() 


@join_router.callback_query(F.data.startswith("ban_"))
async def ban_user_callback(call: CallbackQuery, bot: Bot):
    user_id = int(call.data.split("_")[1])
    await process_ban(user_id, bot)
    user_data = await db.get_user(user_id)
    if user_data:
        user_mention = get_user_mention(user_data)
        await call.message.edit_text(f"🚫 Пользователь <b>{user_mention}</b> заблокирован.", parse_mode='HTML')
    await call.answer()