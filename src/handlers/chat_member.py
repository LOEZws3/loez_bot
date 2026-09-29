import os
import re
import logging
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import ChatMemberUpdated

from config import GENERAL_CHAT_ID
from utils.admin_utils import is_owner, is_admin, get_admin_rank
from utils.user_utils import get_user_by_id
from utils.counters import (
    increment_message_count, get_message_count as get_stored_count,
    set_joined_at, get_joined_at, is_new_user,
)
from utils.warns_utils import add_warn

logger = logging.getLogger(__name__)
router = Router()

# Счётчик для напоминалки незарегистрированным (в памяти)
message_counter = {}


def get_message_count(user_id: int) -> int:
    return message_counter.get(user_id, 0)


def set_message_count(user_id: int, count: int):
    message_counter[user_id] = count


def check_user_registration(user_id: int) -> bool:
    """Проверяет, есть ли пользователь в users.json"""
    try:
        user = get_user_by_id(user_id)
        if user:
            logger.info(f"✅ Пользователь {user_id} найден в users.json")
            return True
        logger.info(f"❌ Пользователь {user_id} НЕ найден в users.json")
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке пользователя {user_id}: {e}")
        return False


def _is_user_in_rest(user_id: int) -> bool:
    """Проверяет, в ресте ли юзер."""
    try:
        from utils.role_utils import load_roles_status
        data = load_roles_status()
        for role_key, info in data.items():
            if isinstance(info, dict) and info.get('owner_id') == user_id:
                return info.get('status') == 'рест'
        return False
    except Exception:
        return False


# ======================== ПАРСЕР ВАРНОВ/БАНОВ ========================

# Форматы:
# - варн @username 6д [причина]
# - варн @username 6ч [причина]
# - варн @username [причина]  (без срока = 6 дней)
# - бан @username [причина]
WARN_PATTERN = re.compile(
    r'^(варн|бан)\s+@?(\S+)(?:\s+(\d+)\s*([дч]))?(?:\s+(.+))?$',
    re.IGNORECASE
)


async def _try_parse_warn_command(message: types.Message) -> bool:
    """
    Проверяет: сообщение это команда варн/бан?
    Если да — парсит, сохраняет в warns.json.
    Возвращает True если обработал.
    """
    text = (message.text or '').strip()
    if not text:
        return False

    # Только для админов/модераторов
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        return False
    if not is_admin(user_id):
        return False

    match = WARN_PATTERN.match(text)
    if not match:
        return False

    action = match.group(1).lower()
    target_str = match.group(2).lstrip('@')
    duration_num = match.group(3)
    duration_unit = match.group(4)
    reason = (match.group(5) or '').strip()

    # Находим юзера по username
    target_id = None
    if target_str.isdigit():
        target_id = int(target_str)
    else:
        # Ищем по username
        try:
            from utils.user_utils import load_users
            for u in load_users():
                if u.get('username') and u['username'].lower() == target_str.lower():
                    target_id = u['id']
                    break
        except Exception:
            pass

    if not target_id:
        # Если не нашли — не обрабатываем (пусть это сделает Iris)
        return False

    if action == 'бан':
        # Бан — сохраняем как варн навсегда + логируем
        logger.info(f"🚫 Пойман БАН @{target_str} (ID {target_id}) от админа {user_id}. Причина: {reason}")
        # TODO: логика бана (очистка + Iris)
        return True

    if action == 'варн':
        # Определяем срок
        if duration_num and duration_unit == 'д':
            days = int(duration_num)
        elif duration_num and duration_unit == 'ч':
            days = max(1, int(duration_num) // 24)
        else:
            days = 6  # по умолчанию

        add_warn(target_id, days=days, issued_by=user_id, reason=reason or "Нарушение")
        logger.info(f"⚠️ Пойман ВАРН @{target_str} (ID {target_id}) на {days} дней от {user_id}. Причина: {reason}")
        return True

    return False


# ======================== ОСНОВНОЙ ОБРАБОТЧИК ========================

@router.message()
async def handle_message(message: types.Message):
    """Обработчик всех сообщений"""
    # Пропускаем команды (не перехватываем /stats, /diag, /apply и т.д.)
    if message.text and message.text.startswith('/'):
        return

    # Работаем только во флуд-чате
    if message.chat.type in ['group', 'supergroup']:
        if message.chat.id != GENERAL_CHAT_ID:
            return
    else:
        # В ЛС ничего не делаем
        return

    user_id = message.from_user.id

    # ========== Парсер варн/бан команд ==========
    try:
        if await _try_parse_warn_command(message):
            return  # команда обработана, не считаем как сообщение
    except Exception as e:
        logger.error(f"❌ Ошибка парсера варнов: {e}")

    # ========== Счётчик для нормы (только для зарегистрированных) ==========
    is_registered = check_user_registration(user_id)

    if is_registered:
        # Записываем joined_at если первый раз (авто)
        if not get_joined_at(user_id):
            set_joined_at(user_id)
            logger.info(f"📅 Установлен joined_at для {user_id}")

        # Проверяем рест
        if _is_user_in_rest(user_id):
            logger.debug(f"⏳ {user_id} в ресте — сообщение не считаем")
        else:
            # Проверяем Нью
            if is_new_user(user_id, days=7):
                logger.debug(f"👶 {user_id} Нью (<7 дней) — в норму не считаем")
            else:
                # Обычный юзер — считаем в норму
                increment_message_count(user_id)

        # Сбрасываем напоминалку если была
        if user_id in message_counter:
            message_counter[user_id] = 0
        return

    # ========== Напоминалка для незарегистрированных ==========
    count = get_message_count(user_id) + 1
    set_message_count(user_id, count)

    if count % 5 == 0:
        try:
            await message.reply(
                "👤 Я не вижу вас в системе, вы не зарегистрированы или ваши данные не обновлены!\n\n"
                "📌 Пожалуйста, обновите свои данные через бота и команду /update:\n"
                "👉 @REG_sf_BOT\n\n"
                "Или зарегистрируйтесь через команду /apply в личных сообщениях с ботом.",
                disable_notification=True
            )
            logger.info(f"📨 Напоминание отправлено {user_id} (#{count})")
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания: {e}")


# ======================== ПРИВЕТСТВИЕ НОВЫХ ========================

@router.my_chat_member()
async def on_user_join(update: ChatMemberUpdated):
    """Приветствие новых пользователей"""
    if update.chat.id != GENERAL_CHAT_ID:
        return

    if update.new_chat_member.status not in ['member', 'administrator', 'creator']:
        return

    if update.old_chat_member.status in ['member', 'administrator', 'creator']:
        return

    user = update.new_chat_member.user
    user_id = user.id

    if not check_user_registration(user_id):
        try:
            await update.bot.send_message(
                chat_id=update.chat.id,
                text=f"👋 Привет, {user.first_name}!\n\n"
                     f"❗ Для полного доступа зарегистрируйтесь:\n"
                     f"1. Напишите @loez_bot в личку\n"
                     f"2. Используйте команду /apply",
                disable_notification=True
            )
            logger.info(f"📨 Приветствие отправлено {user_id}")
        except Exception as e:
            logger.error(f"Ошибка приветствия: {e}")


# ======================== СБРОС СЧЁТЧИКА ========================

@router.message(Command("reset_counter"))
async def reset_counter_command(message: types.Message):
    """Команда для сброса счётчика напоминалки (только для владельца)"""
    if not is_owner(message.from_user.id):
        await message.reply("⛔ У вас нет прав для использования этой команды.")
        return

    parts = message.text.split()
    user_id = int(parts[1]) if len(parts) > 1 else message.from_user.id

    if user_id in message_counter:
        message_counter[user_id] = 0
        await message.reply(f"✅ Счётчик для {user_id} сброшен.")
    else:
        await message.reply(f"⚠️ Пользователь {user_id} не найден в счётчике.")


__all__ = ['router']