import os
import re
import logging
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import ChatMemberUpdated

from config import GENERAL_CHAT_ID
from utils.admin_utils import is_owner, is_admin, get_admin_rank
from utils.user_utils import (
    get_user_by_id, get_notify_norm,
)
from utils.counters import (
    increment_message_count, get_message_count as get_stored_count,
    set_joined_at, get_joined_at, is_new_user,
    update_last_message_at, mark_norm_notified, is_norm_notified,
)
from utils.warns_utils import add_warn
from utils.settings_utils import get_messages_norm, get_setting

logger = logging.getLogger(__name__)
router = Router()

# Счётчик для напоминалки незарегистрированным (в памяти)
message_counter = {}

# ======================== ПАРСЕР ВАРНОВ/БАНОВ ========================
# ⚠️ 02.10.2026: перешли на МИНУТЫ.
# Поддерживаем единицы (русские):
#   мин, м       — минуты
#   ч, час, часов — часы (× 60)
#   д, дней, день — дни (× 1440)
#   н, нед, недель — недели (× 10080)
#   мес, месяц, месяцев — месяцы (× 43200 = 30 дней)
#   г, год, лет  — годы (× 525600 = 365 дней)
# Если срок не указан → 7 дней = 10080 минут

WARN_PATTERN = re.compile(
    r'^(варн|бан)\s+@?(\S+)'
    r'(?:\s+(\d+)\s*'
    r'(мин|м|ч|час|часов|д|день|дней|н|нед|недель|мес|месяц|месяцев|г|год|лет)'
    r')?'
    r'(?:\s+(.+))?$',
    re.IGNORECASE
)

_UNIT_TO_MINUTES = {
    'мин': 1, 'м': 1,
    'ч': 60, 'час': 60, 'часов': 60,
    'д': 1440, 'день': 1440, 'дней': 1440,
    'н': 10080, 'нед': 10080, 'недель': 10080,
    'мес': 43200, 'месяц': 43200, 'месяцев': 43200,
    'г': 525600, 'год': 525600, 'лет': 525600,
}

DEFAULT_WARN_MINUTES = 7 * 24 * 60  # 7 дней

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

def _parse_duration_to_minutes(num_str: str, unit: str) -> int:
    """Переводит '6 д' → 8640 минут."""
    try:
        num = int(num_str)
    except (ValueError, TypeError):
        return DEFAULT_WARN_MINUTES

    unit_lower = (unit or '').lower().strip()
    multiplier = _UNIT_TO_MINUTES.get(unit_lower, 1440)
    return num * multiplier

async def _try_parse_warn_command(message: types.Message) -> bool:
    """Проверяет: сообщение это команда варн/бан? Только во флуде."""
    text = (message.text or '').strip()
    if not text:
        return False

    if message.chat.id != GENERAL_CHAT_ID:
        return False

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

    target_id = None
    if target_str.isdigit():
        target_id = int(target_str)
    else:
        try:
            from utils.user_utils import load_users
            for u in load_users():
                if u.get('username') and u['username'].lower() == target_str.lower():
                    target_id = u['id']
                    break
        except Exception:
            pass

    if not target_id:
        return False

    if action == 'бан':
        logger.info(f"🚫 Пойман БАН @{target_str} (ID {target_id}) от {user_id}. Причина: {reason}")
        return True

    if action == 'варн':
        if duration_num and duration_unit:
            minutes = _parse_duration_to_minutes(duration_num, duration_unit)
        else:
            minutes = DEFAULT_WARN_MINUTES

        add_warn(target_id, minutes=minutes, issued_by=user_id,
                 reason=reason or "Нарушение")
        logger.info(f"⚠️ ВАРН @{target_str} (ID {target_id}) на {minutes} мин от {user_id}. Причина: {reason}")
        return True

    return False

# ======================== 🔧 ИСПРАВЛЕНО: ЛС при наборе нормы ========================

async def _maybe_notify_norm(bot, user_id: int):
    """
    Проверяет: набрал ли юзер норму, не уведомляли ли его, подписан ли он.
    Если да — отправляет ЛС и ставит флаг norm_notified.
    🔧 ИСПРАВЛЕНО: добавлена проверка результата mark_norm_notified.
    """
    try:
        # Глобальная настройка
        global_enabled = get_setting('norm_auto_message_enabled', True)
        if not global_enabled:
            return

        # Локальная подписка
        if not get_notify_norm(user_id):
            return

        # Уже уведомляли?
        if is_norm_notified(user_id):
            return

        # Набрал норму?
        norm = get_messages_norm()
        count = get_stored_count(user_id)
        if count < norm:
            return

        # Отправляем ЛС
        try:
            await bot.send_message(
                user_id,
                "🎉 <b>Поздравляю! Ты набрал норму за эту неделю!</b>",
                parse_mode="HTML"
            )
        except Exception as send_error:
            logger.error(f"❌ Не удалось отправить уведомление {user_id}: {send_error}")
            return

        # 🔧 ИСПРАВЛЕНО: проверяем результат сохранения флага
        if not mark_norm_notified(user_id):
            logger.warning(f"⚠️ Не удалось сохранить флаг norm_notified для {user_id} — возможно повторное уведомление!")
        
        logger.info(f"📩 Уведомление о норме отправлено {user_id} ({count}/{norm})")

    except Exception as e:
        logger.error(f"❌ Ошибка уведомления о норме для {user_id}: {e}")

# ======================== ОСНОВНОЙ ОБРАБОТЧИК ========================

@router.message()
async def handle_message(message: types.Message):
    """Обработчик всех сообщений"""
    if message.text and message.text.startswith('/'):
        return

    if message.chat.type in ['group', 'supergroup']:
        if message.chat.id != GENERAL_CHAT_ID:
            return
    else:
        return

    user_id = message.from_user.id

    # ========== Парсер варн/бан ==========
    try:
        if await _try_parse_warn_command(message):
            return
    except Exception as e:
        logger.error(f"❌ Ошибка парсера варнов: {e}")

    # ========== Счётчик нормы ==========
    is_registered = check_user_registration(user_id)

    if is_registered:
        if not get_joined_at(user_id):
            set_joined_at(user_id)
            logger.info(f"📅 Установлен joined_at для {user_id}")

        if _is_user_in_rest(user_id):
            logger.debug(f"⏳ {user_id} в ресте — не считаем")
        else:
            if is_new_user(user_id, days=7):
                logger.debug(f"👶 {user_id} Нью (<7 дней) — не считаем")
            else:
                increment_message_count(user_id)

                # ⚠️ НОВОЕ: проверяем норму
                await _maybe_notify_norm(message.bot, user_id)

        if user_id in message_counter:
            message_counter[user_id] = 0
        return

    # ========== Напоминалка ==========
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

# ======================== ПРИВЕТСТВИЕ ========================

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

    # ⚠️ НОВОЕ: обновляем last_message_at в истории
    try:
        from utils.user_history import set_last_message_at
        set_last_message_at(user_id)
    except Exception as e:
        logger.error(f"❌ Не удалось обновить last_message_at: {e}")

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
    """Сброс счётчика напоминалки (только владелец)"""
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