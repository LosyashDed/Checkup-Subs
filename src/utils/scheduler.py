from datetime import datetime, timedelta, timezone
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from src.config import CHANNEL_ID, ADMIN_ID
from src.database import database as db
from src.utils.user_utils import get_user_mention

async def check_subscriptions_with_stats(bot: Bot, admin_chat_id: int = ADMIN_ID):

    logger.info("Запущена проверка подписок...")
    
    try:
        active_users = await db.get_users_by_status('active')
        total_active_before = len(active_users)
        today = datetime.now().date()
        expired_count = 0

        for user in active_users:
            user_id = user['user_id']
            end_date_str = user.get('subscription_end_date')
            
            if not end_date_str:
                logger.warning(f"У активного пользователя {user_id} отсутствует дата окончания подписки.")
                continue

            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                if end_date < today:
                    logger.info(f"Подписка для пользователя {user_id} истекла. Удаление...")
                    await bot.ban_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
                    # Сразу разблокируем, чтобы просто удалить, а не заблокировать
                    await bot.unban_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
                    await db.update_user_status(user_id, 'expired')
                    expired_count += 1
                    logger.info(f"Пользователь {user_id} удален из канала, статус обновлен на 'expired'.")
                    await bot.send_message(admin_chat_id, f"Пользователь ID: {user_id} {get_user_mention(user)} удален из канала, статус обновлен на 'expired'.")
            except ValueError:
                logger.error(f"Неверный формат даты '{end_date_str}' для пользователя {user_id}.")
            except Exception as e:
                logger.error(f"Не удалось удалить пользователя {user_id} из канала: {e}")

        # Статистика
        updated_active_users = await db.get_users_by_status('active')
        total_active_after = len(updated_active_users)
        
        stats = {
            'message': '',
            'total_before': total_active_before,
            'total_after': total_active_after,
            'expired_count': expired_count,
            'success': True
        }
        
        if expired_count > 0:
            stats_message = (
                f"✅ Проверка подписок завершена!\n\n"
                f"📊 Статистика:\n"
                f"• Было активных: {total_active_before}\n"
                f"• Стало активных: {total_active_after}\n"
                f"• Истекших подписок: {expired_count}\n\n"
                f"Пользователи с истекшими подписками были удалены из канала."
            )
        else:
            stats_message = (
                f"✅ Проверка подписок завершена!\n\n"
                f"📊 Статистика:\n"
                f"• Активных пользователей: {total_active_before}\n"
                f"• Истекших подписок: 0\n\n"
                f"Все подписки актуальны! 🎉"
            )
        
        stats['message'] = stats_message
            
        try:
            await bot.send_message(admin_chat_id, stats_message, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Не удалось отправить статистику администратору: {e}")
        
        logger.info(f"Проверка подписок завершена. Обработано: {expired_count} истекших подписок")
        return stats
        
    except Exception as e:
        logger.error(f"Ошибка во время выполнения задачи проверки подписок: {e}")
        error_stats = {
            'success': False,
            'error': str(e),
            'message': f"❌ Произошла ошибка при проверке подписок:\n{str(e)}\n\nПодробности смотрите в логах."
        }
        
        try:
            await bot.send_message(admin_chat_id, error_stats['message'], parse_mode='HTML')
        except Exception as send_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}")
        
        return error_stats

async def scheduled_check_subscriptions(bot: Bot):
    logger.info("Запущена автоматическая ежедневная проверка подписок...")
    await check_subscriptions_with_stats(bot)

def setup_scheduler(bot: Bot):
    scheduler = AsyncIOScheduler(timezone=timezone(timedelta(hours=3)))
    scheduler.add_job(scheduled_check_subscriptions, 'cron', hour=4, minute=0, args=(bot,))
    scheduler.start()
    logger.info("Планировщик задач запущен. Проверка будет выполняться ежедневно в 4:00 по МСК с отправкой статистики администратору.") 