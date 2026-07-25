import logging
from config import USERS_FILE, GENERAL_CHAT_ID
from utils.user_utils import load_users, save_users
from aiogram import Bot

# Исправлено: __name__ вместо name
logger = logging.getLogger(__name__)


async def sync_users_with_group(bot: Bot):
    """Синхронизирует users.txt с реальными участниками группы"""
    try:
        # Получаем список реальных участников группы
        real_members = set()

        # Проверяем наличие метода
        get_members_method = getattr(bot, 'get_chat_members', None)
        if not get_members_method:
            logger.error("❌ Метод get_chat_members недоступен у объекта бота")
            return -1

        async for member in get_members_method(chat_id=GENERAL_CHAT_ID):
            user = member.user
            if not user.is_bot:  # Исключаем ботов
                real_members.add(user.id)

        # Загружаем текущий список из users.txt
        users = load_users()
        current_user_ids = {u['id'] for u in users}

        # Находим пользователей, которых нет в группе
        removed_users = current_user_ids - real_members

        if removed_users:
            # Фильтруем только тех, кто есть в группе
            updated_users = [u for u in users if u['id'] in real_members]
            save_users(updated_users)
            logger.info(f"🔄 Синхронизация: удалено {len(removed_users)} пользователей, отсутствующих в группе")
            return len(removed_users)
        else:
            logger.info("🔄 Синхронизация: список участников актуален")
            return 0
    except Exception as e:
        logger.error(f"❌ Ошибка синхронизации: {e}")
        return -1