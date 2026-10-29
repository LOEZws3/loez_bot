import logging
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable

from config import GENERAL_CHAT_ID, STARTER_MODE_ALLOWED_COMMANDS, OWNER_ID
from utils.user_utils import get_user_by_id

logger = logging.getLogger(__name__)


class RegistrationCheckMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        if event.chat.id == GENERAL_CHAT_ID:
            return await handler(event, data)

        text = event.text or ""
        if not text.startswith('/'):
            return await handler(event, data)

        user_id = event.from_user.id if event.from_user else None
        if not user_id:
            return await handler(event, data)

        # ⚠️ Логирование команд админов (исправлено: вынесено после определения user_id и text)
        try:
            from utils.admin_utils import is_admin
            if is_admin(user_id):
                admin_logger = logging.getLogger('admin_actions')
                admin_logger.info(f"🛠️ Админ {user_id} использовал команду: {text.split()[0]}")
        except Exception as e:
            logger.error(f"Ошибка логирования команды админа: {e}")

        # ⚠️ ВЛАДЕЛЕЦ ПРОХОДИТ ВСЕГДА
        if user_id == OWNER_ID:
            return await handler(event, data)

        # ⚠️ ОБХОД ДЛЯ АДМИНОВ (если их нет в users.json после /free)
        try:
            from utils.admin_utils import is_admin
            if is_admin(user_id):
                return await handler(event, data)
        except Exception:
            pass

        # Проверка политики
        user = get_user_by_id(user_id)
        if user and not user.get('agreed_to_privacy', False):
            command = text.split()[0].split('@')[0].lower()
            if command != '/start':
                await event.answer(
                    "⛔ <b>Вы должны ознакомиться и согласиться с политикой конфиденциальности и правилами пользования.</b>\n\n"
                    "📌 Нажмите /start, чтобы прочитать и согласиться.",
                    parse_mode="HTML"
                )
                return
            return await handler(event, data)

        # Если юзера нет в базе
        if not user:
            command = text.split()[0].split('@')[0].lower()
            if command in STARTER_MODE_ALLOWED_COMMANDS:
                return await handler(event, data)

            await event.answer(
                f"⛔ Для использования этой команды нужно подать заявку.\n"
                f"📌 Команда: <code>{command}</code>",
                parse_mode="HTML"
            )
            return

        return await handler(event, data)