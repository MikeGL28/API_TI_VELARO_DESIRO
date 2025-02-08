from aiogram import types
from functools import wraps

from config import ALLOWED_USERS


def check_access(func):
    @wraps(func)
    async def wrapper(message: types.Message, *args, **kwargs):
        if message.from_user.id not in ALLOWED_USERS:
            await message.answer("Извините, у вас нет доступа к этому боту.")
            return
        return await func(message, *args, **kwargs)
    return wrapper