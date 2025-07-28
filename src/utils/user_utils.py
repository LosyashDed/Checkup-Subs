from aiogram.types import User

def get_user_mention(user: User | dict) -> str:
    if isinstance(user, dict):
        # Если это словарь из нашей БД
        username = user.get('username')
        full_name = user.get('full_name', '')
    else:
        # Если это объект aiogram.types.User
        username = user.username
        full_name = user.full_name

    if username:
        return f"@{username}"
    return full_name 