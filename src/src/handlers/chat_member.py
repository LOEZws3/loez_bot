from aiogram import Router
from aiogram.types import ChatMemberUpdated
import logging
import datetime
from config import GENERAL_CHAT_ID
from utils.user_history import save_user_history, load_user_history
from utils.emoji_utils import get_user_emoji
from utils.role_utils import get_user_role as get_role_from_roles
from utils.user_utils import get_user_role as get_role_from_users
from utils.sync_utils import sync_users_with_group
import html

logger = logging.getLogger(__name__)
router = Router()

ROLE_NAMES = {
    '0': 'Участник',
    '1': 'Небезопасный клиент',
    '2': 'Неприемлемый ник',
    '3': 'Временный статус (рест/нью)',
    '4': 'Администрация',
    '5': 'Администрация в ресте'
}


def get_current_datetime():
    now = datetime.datetime.now()
    return now.strftime("%d.%m.%Y %H:%M")


def get_user_role_name(user_id):
    """Получает название роли пользователя"""
    role_index = get_role_from_roles(user_id) or get_role_from_users(user_id)
    return ROLE_NAMES.get(role_index, 'Участник')


@router.chat_member()
async def on_member_update(event: ChatMemberUpdated):
    # Проверяем, что событие произошло в флуд-чате
    if event.chat.id != GENERAL_CHAT_ID:
        return

    user = event.from_user
    user_id = user.id
    full_name = html.escape(user.full_name)
    emoji = get_user_emoji(user_id)

    # Получаем роль и персонажа
    role_name = get_user_role_name(user_id)
    character = get_role_from_roles(user_id) or "Неизвестно"

    # ============================================================
    # 📥 ВХОД УЧАСТНИКА
    # ============================================================
    if event.new_chat_member.status == 'member' and event.old_chat_member.status == 'left':
        history = load_user_history(user_id)

        # Формируем приветствие с ролью
        if history and history.get('first_joined'):
            # Возвращение старого участника
            await event.bot.send_message(
                chat_id=GENERAL_CHAT_ID,
                text=f'<a href="tg://user?id={user_id}">{emoji}</a> Рад видеть вас снова, {full_name}! 👋\n📌 Роль: {role_name}\n📌 Персонаж: {character}',
                parse_mode="HTML"
            )
        else:
            # Новый участник
            await event.bot.send_message(
                chat_id=GENERAL_CHAT_ID,
                text=f'<a href="tg://user?id={user_id}">{emoji}</a> Приветствуем, {full_name}! 🎉\n📌 Роль: {role_name}\n📌 Персонаж: {character}\n\nДобро пожаловать в наш флуд!',
                parse_mode="HTML"
            )

        # Сохраняем историю
        save_user_history(user_id, {
            "first_joined": datetime.date.today().isoformat(),
            "total_visits": history.get("total_visits", 0) + 1,
            "emoji": emoji
        })

        # 🔄 Синхронизируем users.txt (добавляем пользователя, если его нет)
        await sync_users_with_group(event.bot)

    # ============================================================
    # 📤 ВЫХОД УЧАСТНИКА
    # ============================================================
    elif event.new_chat_member.status == 'left':
        reason = 'banned' if event.old_chat_member.status == 'kicked' else 'left'
        save_user_history(user_id, {
            "last_left": get_current_datetime(),
            "left_reason": reason
        })

        if reason == 'banned':
            logger.info(f"🚫 {full_name} забанен в {get_current_datetime()}")
        else:
            logger.info(f"👋 {full_name} вышел из группы")

        # 🔄 Синхронизируем users.txt (удаляем пользователя, если его нет в группе)
        await sync_users_with_group(event.bot)