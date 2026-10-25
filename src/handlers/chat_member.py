import os
import json
import re
import logging
import datetime
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import ChatMemberUpdated

from config import GENERAL_CHAT_ID, DATA_DIR
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

# ⚠️ НОВОЕ: Защита от гонки данных при уведомлении о норме
_notified_norm_users = set()

# ⚠️ НОВОЕ: Кэш для предупреждений о неполном профиле
_last_profile_warn_sent = {}

# ======================== АЛИАСЫ (СОХРАНЕНИЕ СТАРЫХ НИКОВ) ========================
ALIASES_FILE = os.path.join(DATA_DIR, 'users', 'aliases.json')

def _load_aliases() -> dict:
    if not os.path.exists(ALIASES_FILE):
        return {}
    try:
        with open(ALIASES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _save_aliases(data: dict):
    try:
        os.makedirs(os.path.dirname(ALIASES_FILE), exist_ok=True)
        with open(ALIASES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения aliases.json: {e}")

def _update_aliases(user_id: int, username: str, full_name: str):
    """Проверяет, менялись ли данные, и сохраняет старые."""
    aliases = _load_aliases()
    uid_str = str(user_id)
    
    if uid_str not in aliases:
        aliases[uid_str] = {'usernames': [], 'full_names': []}
        
    user_aliases = aliases[uid_str]
    
    # Проверка юзернейма
    if username and username not in user_aliases['usernames']:
        if user_aliases['usernames']: # Если это не первый ник
            logger.info(f"🏷️ Юзер {user_id} сменил юзернейм: добавлен старый @{user_aliases['usernames'][-1]}")
        user_aliases['usernames'].append(username)
        
    # Проверка имени
    if full_name and full_name not in user_aliases['full_names']:
        if user_aliases['full_names']:
            logger.info(f"📝 Юзер {user_id} сменил имя: добавлено старое '{user_aliases['full_names'][-1]}'")
        user_aliases['full_names'].append(full_name)
        
    _save_aliases(aliases)

# ======================== ПАРСЕР ВАРНОВ/БАНОВ ========================
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
    try:
        num = int(num_str)
    except (ValueError, TypeError):
        return DEFAULT_WARN_MINUTES

    unit_lower = (unit or '').lower().strip()
    multiplier = _UNIT_TO_MINUTES.get(unit_lower, 1440)
    return num * multiplier

async def _try_parse_warn_command(message: types.Message) -> bool:
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

# ======================== 🔧 НОВЫЕ ПРОВЕРКИ ========================

async def _maybe_notify_norm(bot, user_id: int):
    try:
        global_enabled = get_setting('norm_auto_message_enabled', True)
        if not global_enabled:
            return
        if not get_notify_norm(user_id):
            return
        if user_id in _notified_norm_users:
            return
        if is_norm_notified(user_id):
            _notified_norm_users.add(user_id)
            return
        norm = get_messages_norm()
        count = get_stored_count(user_id)
        if count < norm:
            return

        _notified_norm_users.add(user_id)
        mark_norm_notified(user_id)

        try:
            await bot.send_message(
                user_id,
                "🎉 <b>Поздравляю! Ты набрал норму за эту неделю!</b>",
                parse_mode="HTML"
            )
            logger.info(f"📩 Уведомление о норме отправлено {user_id} ({count}/{norm})")
        except Exception as send_error:
            logger.error(f"❌ Не удалось отправить уведомление {user_id}: {send_error}")
    except Exception as e:
        logger.error(f"❌ Ошибка уведомления о норме для {user_id}: {e}")

async def _check_profile_completeness(message: types.Message, user_id: int):
    """Проверяет полноту профиля. Нью — раз в час, остальные — раз в 12 часов."""
    if not get_setting('require_profile_completeness', True):
        return
    try:
        user = get_user_by_id(user_id)
        if not user:
            return
        
        missing = []
        if not user.get('birthday'):
            missing.append('дата рождения')
        if not user.get('role') or str(user.get('role')) == '0':
            missing.append('роль')
            
        if not missing:
            return
            
        is_new = not user.get('role') or str(user.get('role')) == '0'
        cooldown_hours = 1 if is_new else 12
        
        now = datetime.datetime.now()
        last_sent = _last_profile_warn_sent.get(user_id)
        if last_sent and (now - last_sent).total_seconds() < cooldown_hours * 3600:
            return
            
        bot_info = await message.bot.get_me()
        deep_link = f"https://t.me/{bot_info.username}?start=fill_profile"
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="📝 Заполнить профиль", url=deep_link)]
        ])
        
        await message.reply(
            f"⚠️ <b>{message.from_user.full_name}</b>, у нас недостаточно информации о вас!\n"
            f"Пожалуйста, заполните: <b>{', '.join(missing)}</b>.\n\n"
            f"<i>(Это сообщение появляется раз в {cooldown_hours} ч. и только если профиль не заполнен)</i>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        _last_profile_warn_sent[user_id] = now
        logger.info(f"⚠️ Профиль {user_id} неполный. Отправлено предупреждение.")
    except Exception as e:
        logger.error(f"❌ Ошибка проверки профиля {user_id}: {e}")

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

    # ⚠️ Проверка: Если юзер в ресте — не трогаем
    user = get_user_by_id(user_id)
    if user and user.get('rest', False):
        logger.debug(f"⏳ {user_id} в ресте — пропускаем все проверки")
        return

    # ⚠️ Если юзер полностью зарегистрирован — считаем сообщения
    if user and user.get('is_fully_registered', False):
        # Логика для зарегистрированных
        await _check_profile_completeness(message, user_id)
        _update_aliases(user_id, message.from_user.username or '', message.from_user.full_name or '')

        if not get_joined_at(user_id):
            set_joined_at(user_id)
            logger.info(f"📅 Установлен joined_at для {user_id}")

        if is_new_user(user_id, days=7):
            logger.debug(f"👶 {user_id} Нью (<7 дней) — не считаем")
        else:
            increment_message_count(user_id)
            await _maybe_notify_norm(message.bot, user_id)

        if user_id in message_counter:
            message_counter[user_id] = 0
        return

    # ========== Напоминалка для незарегистрированных (нет роли) ==========
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
    if update.chat.id != GENERAL_CHAT_ID:
        return
    if update.new_chat_member.status not in ['member', 'administrator', 'creator']:
        return
    if update.old_chat_member.status in ['member', 'administrator', 'creator']:
        return

    user = update.new_chat_member.user
    user_id = user.id

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