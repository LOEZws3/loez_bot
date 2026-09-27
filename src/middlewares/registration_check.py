"""
Middleware стартового режима.
Незарегистрированные юзеры (нет в users.json) могут использовать
только разрешённые команды.
"""

import logging
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable

from config import GENERAL_CHAT_ID, STARTER_MODE_ALLOWED_COMMANDS
from utils.user_utils import get_user_by_id

logger = logging.getLogger(__name__)


class RegistrationCheckMiddleware(BaseMiddleware):
    """
    Пропускает только разрешённые команды для незарегистрированных.
    Зарегистрированные (есть в users.json) — проходят свободно.
    Во флуд-чате (GENERAL_CHAT_ID) — не работает.
    """

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event,
        data: Dict[str, Any],
    ) -> Any:
        # Работаем только с сообщениями
        if not isinstance(event, Message):
            return await handler(event, data)

        # Во флуде не трогаем
        if event.chat.id == GENERAL_CHAT_ID:
            return await handler(event, data)

        # Только текст
        text = event.text or ""
        if not text.startswith('/'):
            return await handler(event, data)

        user_id = event.from_user.id if event.from_user else None
        if not user_id:
            return await handler(event, data)

        # Админов и владельцев не трогаем
        try:
            from utils.admin_utils import is_admin
            if is_admin(user_id):
                return await handler(event, data)
        except Exception:
            pass

        # Зарегистрирован? (есть в users.json)
        try:
            user = get_user_by_id(user_id)
            if user:
                return await handler(event, data)
        except Exception as e:
            logger.error(f"Middleware: ошибка проверки юзера {user_id}: {e}")

        # Не зарегистрирован — проверяем команду
        # /start /help /about /aboutme /apply /setbirthday /update
        command = text.split()[0].split('@')[0].lower()

        if command in STARTER_MODE_ALLOWED_COMMANDS:
            return await handler(event, data)

        # Запрещено
        await event.answer(
            f"⛔ Для использования этой команды нужно подать заявку.\n"
            f"📌 Команда: <code>{command}</code>",
            parse_mode="HTML"
        )
        logger.info(f"⛔ Middleware: {user_id} попытался использовать {command} без регистрации")
        return