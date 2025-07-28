from aiogram import Router, F
from aiogram.filters import BaseFilter
from aiogram.types import Message

from src.config import ADMIN_ID

class AdminFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user.id == ADMIN_ID

def setup_admin_router(router: Router) -> Router:
    router.message.filter(AdminFilter())
    router.callback_query.filter(F.from_user.id == ADMIN_ID)
    return router