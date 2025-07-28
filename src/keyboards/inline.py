from aiogram.utils.keyboard import InlineKeyboardBuilder    

def get_approval_keyboard(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Одобрить", callback_data=f"approve_{user_id}")
    builder.button(text="❌ Отклонить", callback_data=f"decline_{user_id}")
    builder.button(text="🚫 Заблокировать", callback_data=f"ban_{user_id}")
    builder.adjust(2, 1)
    return builder.as_markup()


def get_subscription_keyboard(user_id: int):
    builder = InlineKeyboardBuilder()
    periods = {
        "1 неделя": 7, "2 недели": 14, "1 месяц": 30,
        "2 месяца": 60, "3 месяца": 90
    }
    for text, days in periods.items():
        builder.button(text=text, callback_data=f"set_sub_{user_id}_{days}")
    builder.adjust(3)
    return builder.as_markup()