import logging
import datetime
from aiogram import Bot
from config import GENERAL_CHAT_ID
from utils.user_utils import load_users, save_users

logger = logging.getLogger(__name__)

async def sync_users_with_group(bot: Bot):
    """Синхронизирует users.json с реальными участниками группы"""
    try:
        real_members = set()
        get_members_method = getattr(bot, 'get_chat_members', None)
        if not get_members_method:
            logger.error("❌ Метод get_chat_members недоступен у объекта бота")
            return -1

        async for member in get_members_method(chat_id=GENERAL_CHAT_ID):
            user = member.user
            if not user.is_bot:
                real_members.add(user.id)

        users = load_users()
        users_to_keep = []
        removed_count = 0
        now = datetime.datetime.now()

        for u in users:
            if u['id'] in real_members:
                users_to_keep.append(u)
            else:
                # Проверяем льготный период (grace period)
                grace_until_str = u.get('grace_until')
                in_grace = False
                
                if grace_until_str:
                    try:
                        grace_until = datetime.datetime.fromisoformat(grace_until_str)
                        if now < grace_until:
                            in_grace = True
                    except Exception:
                        pass  # Если дата битая, удаляем как обычно
                
                if in_grace:
                    users_to_keep.append(u)
                    logger.info(f"⏳ {u['id']} ({u.get('full_name')}) в льготном периоде до {grace_until.strftime('%d.%m.%Y %H:%M')}. Не удаляем.")
                else:
                    removed_count += 1

        if removed_count > 0:
            save_users(users_to_keep)
            logger.info(f"🔄 Синхронизация: удалено {removed_count} пользователей, отсутствующих в группе")
            return removed_count
        else:
            logger.info("🔄 Синхронизация: список участников актуален")
            return 0
            
    except Exception as e:
        logger.error(f"❌ Ошибка синхронизации: {e}")
        return -1