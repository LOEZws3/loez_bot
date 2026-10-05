import html
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import asyncio
import time
import datetime
import json
import os
from config import GENERAL_CHAT_ID, OWNER_ID, DATA_DIR, LEFTOVER_FILE
from utils.admin_utils import is_admin, is_owner, load_admins, save_admins, get_admin_rank, set_rank, add_admin
from utils.user_utils import (
    load_users, add_user, remove_user, get_users_count,
    get_changes_count, reset_changes_count,
)
from utils.role_utils import (
    free_role, get_user_role as get_user_role_from_roles,
    find_roles, get_role_by_name,
    format_role_display,
    load_roles_status, save_roles_status,
)
from utils.norm_utils import get_user_category, get_emoji, get_category_label
from utils.requests_utils import get_request_by_user_id
from utils.settings_utils import get_messages_norm, get_messages_norm_low
from .keyboards import get_main_keyboard
import logging

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

closed_mode = False

# ============================================================
# ⚠️ НОВОЕ (05.10.2026): СТАТИСТИКА С КНОПКАМИ
# ============================================================

def _load_leftdata() -> dict:
    """Загружает leftdata.json (ушедшие юзеры)."""
    if not os.path.exists(LEFTOVER_FILE):
        return {}
    try:
        with open(LEFTOVER_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, IOError):
        return {}

def _parse_iso(s: str):
    """Безопасный парсинг ISO-даты."""
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None

def _count_users_joined_in_period(days: int) -> int:
    """Сколько юзеров появилось за последние N дней (по joined_at)."""
    from utils.counters import load_counters
    data = load_counters()
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    count = 0
    for uid_str, info in data.items():
        if not isinstance(info, dict):
            continue
        joined = _parse_iso(info.get('joined_at', ''))
        if joined and joined >= cutoff:
            count += 1
    return count

def _count_active_in_period(days: int) -> int:
    """Сколько юзеров писали за последние N дней (по last_message_at)."""
    from utils.counters import load_counters
    data = load_counters()
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    count = 0
    for uid_str, info in data.items():
        if not isinstance(info, dict):
            continue
        last = _parse_iso(info.get('last_message_at', ''))
        if last and last >= cutoff:
            count += 1
    return count

def _count_left_in_period(days: int) -> int:
    """Сколько юзеров ушло за последние N дней (по leftdata.json)."""
    data = _load_leftdata()
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    count = 0
    for uid_str, info in data.items():
        if not isinstance(info, dict):
            continue
        left_at = _parse_iso(info.get('left_at', ''))
        if left_at and left_at >= cutoff:
            count += 1
    return count

def _get_categories_stats() -> dict:
    """{good, warn, ban, rest, new} — счётчики по категориям."""
    from utils.norm_utils import (
        CATEGORY_GOOD, CATEGORY_WARN, CATEGORY_BAN,
        CATEGORY_NEW, CATEGORY_REST,
    )
    result = {'good': 0, 'warn': 0, 'ban': 0, 'rest': 0, 'new': 0}
    users = load_users()
    for u in users:
        uid = u.get('id')
        if not uid:
            continue
        try:
            cat = get_user_category(uid)
            if cat == CATEGORY_GOOD:
                result['good'] += 1
            elif cat == CATEGORY_WARN:
                result['warn'] += 1
            elif cat == CATEGORY_BAN:
                result['ban'] += 1
            elif cat == CATEGORY_REST:
                result['rest'] += 1
            elif cat == CATEGORY_NEW:
                result['new'] += 1
        except Exception:
            continue
    return result

def _build_stats_base_text() -> str:
    """Базовая статистика (роли, юзеры, админы) — БЕЗ прокси."""
    from utils.role_utils import get_all_seasons, get_roles_by_season

    seasons = get_all_seasons()
    roles_stats = {"свободна": 0, "занята": 0, "ожидает": 0, "рест": 0, "бронь": 0}
    total_roles = 0
    for season in seasons:
        roles = get_roles_by_season(season)
        for role in roles:
            status = role.get('status', 'свободна')
            if status in roles_stats:
                roles_stats[status] += 1
            total_roles += 1

    users = load_users()
    total_users = len(users)

    admins = load_admins()
    total_admins = len(admins)

    text = (
        f"📊 <b>Статистика (база)</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎭 <b>РОЛИ:</b>\n"
        f"  Всего: {total_roles}\n"
        f"  🟢 Свободна: {roles_stats['свободна']}\n"
        f"  🔴 Занята: {roles_stats['занята']}\n"
        f"  ⏳ Ожидает: {roles_stats['ожидает']}\n"
        f"  🔵 Рест: {roles_stats['рест']}\n"
        f"  🟡 Бронь: {roles_stats['бронь']}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>УЧАСТНИКИ:</b>\n"
        f"  Всего: {total_users}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 <b>АДМИНЫ:</b> {total_admins}\n"
    )
    return text

def _build_stats_period_text(period: str) -> str:
    """Статистика за период: day / week / month."""
    days_map = {'day': 1, 'week': 7, 'month': 30}
    titles = {'day': 'за день', 'week': 'за неделю', 'month': 'за месяц'}
    days = days_map.get(period, 7)
    title = titles.get(period, period)

    cats = _get_categories_stats()
    joined = _count_users_joined_in_period(days)
    active = _count_active_in_period(days)
    left = _count_left_in_period(days)
    total_users = len(load_users())

    text = (
        f"📊 <b>Статистика {title}</b>\n\n"
        f"👥 Всего зарегистрировано: {total_users}\n"
        f"👶 Нью (пришло за период): {joined}\n\n"
        f"✅ Хороших: {cats['good']}\n"
        f"⚠️ Варн: {cats['warn']}\n"
        f"🚫 Бан: {cats['ban']}\n"
        f"⏳ В ресте: {cats['rest']}\n"
        f"👶 Всего Нью: {cats['new']}\n\n"
        f"📈 Активных за период: {active}\n"
        f"📉 Ушло (кикнуто): {left}\n"
    )
    return text

def _build_stats_keyboard(current_period: str = 'base') -> InlineKeyboardMarkup:
    """Кнопки периодов."""
    def mark(p):
        return "✅ " if current_period == p else ""

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"{mark('base')}📊 База", callback_data="stats_period_base"),
            InlineKeyboardButton(text=f"{mark('day')}📅 День", callback_data="stats_period_day"),
        ],
        [
            InlineKeyboardButton(text=f"{mark('week')}📆 Неделя", callback_data="stats_period_week"),
            InlineKeyboardButton(text=f"{mark('month')}📈 Месяц", callback_data="stats_period_month"),
        ],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"stats_period_{current_period}")],
    ])

@router.message(Command('stats'))
async def cmd_stats(message: Message):
    """Статистика с кнопками."""
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён. Только для администраторов.")
        return

    # Во флуде — краткая версия
    if message.chat.id == GENERAL_CHAT_ID:
        from utils.role_utils import get_all_seasons, get_roles_by_season
        seasons = get_all_seasons()
        total_roles = 0
        for season in seasons:
            total_roles += len(get_roles_by_season(season))
        total_users = len(load_users())
        text = (
            f"📊 <b>Статистика</b>\n\n"
            f"🎭 Роли: {total_roles}\n"
            f"👥 Участников: {total_users}"
        )
        await message.answer(text, parse_mode="HTML")
        return

    text = _build_stats_base_text()
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=_build_stats_keyboard('base')
    )

@router.callback_query(F.data.startswith("stats_period_"))
async def stats_period_callback(callback: CallbackQuery):
    await callback.answer()

    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    if callback.message.chat.id == GENERAL_CHAT_ID:
        await callback.answer("⛔ В ЛС, пожалуйста.", show_alert=True)
        return

    period = callback.data.replace("stats_period_", "")

    if period == 'base':
        text = _build_stats_base_text()
    else:
        text = _build_stats_period_text(period)

    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=_build_stats_keyboard(period)
        )
    except Exception:
        pass

# ============================================================
# 🔍 ПОИСК ПО РОЛИ (/findrole)
# ============================================================

@router.message(Command('findrole'))
async def cmd_findrole(message: Message):
    user_id = message.from_user.id

    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❌ Используйте: /findrole [запрос]\n\n"
            "Можно искать по:\n"
            "• названию роли (частично)\n"
            "• @юзернейму владельца\n"
            "• ID владельца\n"
            "• имени владельца"
        )
        return

    query = parts[1].strip()
    results = find_roles(query)

    if not results:
        await message.answer(f"❌ По запросу <b>{html.escape(query)}</b> ничего не найдено.", parse_mode="HTML")
        return

    if len(results) > 10:
        text = f"🔍 <b>Найдено {len(results)} ролей</b> (показаны первые 10):\n\n"
        results = results[:10]
    else:
        text = f"🔍 <b>Найдено: {len(results)}</b>\n\n"

    buttons = []
    for r in results:
        role_name = r['name']
        role_key = r.get('key', role_name)
        status_emoji = "🟢" if r['status'] == 'свободна' else "🔴" if r['status'] == 'занята' else "⏳"
        buttons.append([InlineKeyboardButton(
            text=f"{status_emoji} {role_name} ({r['season']})",
            callback_data=f"findrole_view_{role_key}"
        )])

    await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("findrole_view_"))
async def findrole_view(callback: CallbackQuery):
    await callback.answer()
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    role_key = callback.data.replace("findrole_view_", "")
    role_short = format_role_display(role_key)

    status_data = load_roles_status()
    role = status_data.get(role_key)

    if not role:
        await callback.message.edit_text(f"❌ Роль '{html.escape(role_short)}' не найдена.")
        return

    status = role.get('status', '?')
    season = role.get('season', '?')
    owner_id = role.get('owner_id')
    username = role.get('username', '')

    full_name = '—'
    if owner_id:
        from utils.user_utils import get_user_by_id
        user_data = get_user_by_id(int(owner_id))
        if user_data:
            full_name = user_data.get('full_name', '—')

    status_emoji = "🟢" if status == 'свободна' else "🔴" if status == 'занята' else "⏳"

    text = (
        f"🎭 <b>Роль: {html.escape(role_short)}</b>\n\n"
        f"📁 Сезон: {html.escape(season)}\n"
        f"{status_emoji} Статус: {status}\n"
    )

    if owner_id:
        text += f"\n👤 <b>Владелец:</b>\n"
        text += f"• Имя: {html.escape(full_name)}\n"
        text += f"• Юзернейм: @{username if username else 'нет'}\n"
        text += f"• ID: <code>{owner_id}</code>\n"
    else:
        text += f"\n👤 Владелец: нет\n"

    buttons = [[InlineKeyboardButton(text="🔙 К поиску", callback_data="findrole_back")]]

    if owner_id:
        buttons.insert(0, [InlineKeyboardButton(
            text="🗑️ Удалить роль и юзера",
            callback_data=f"findrole_delete_{role_key}"
        )])

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(F.data.startswith("findrole_delete_yes_"))
async def findrole_delete_do(callback: CallbackQuery):
    await callback.answer()
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    role_key = callback.data.replace("findrole_delete_yes_", "")
    role_short = format_role_display(role_key)

    status_data = load_roles_status()
    role = status_data.get(role_key)

    if not role or not role.get('owner_id'):
        await callback.message.edit_text("❌ Роль уже свободна или не найдена.")
        return

    owner_id = int(role.get('owner_id'))

    status_data[role_key]['status'] = 'свободна'
    status_data[role_key]['owner_id'] = None
    status_data[role_key]['username'] = None
    save_roles_status(status_data)

    removed = remove_user(owner_id)

    try:
        reset_changes_count(owner_id)
    except Exception:
        pass

    try:
        await callback.bot.set_chat_member_tag(chat_id=GENERAL_CHAT_ID, user_id=owner_id, tag="")
        logger.info(f"🏷️ Удалён тег у пользователя {owner_id}")
    except Exception as e:
        logger.error(f"❌ Не удалось удалить тег: {e}")

    response = f"✅ <b>Роль «{html.escape(role_short)}» удалена:</b>\n"
    response += f"• 📌 Роль освобождена\n"
    if removed:
        response += f"• 👤 Юзер <code>{owner_id}</code> удалён из users.json\n"
    response += f"• 🏷️ Тег удалён в чате\n"
    response += f"• 🔄 Счётчик смен сброшен"

    await callback.message.edit_text(response, parse_mode="HTML")
    logger.info(f"Админ {admin_id} удалил роль {role_key} и юзера {owner_id}")

@router.callback_query(F.data.startswith("findrole_delete_"))
async def findrole_delete_confirm(callback: CallbackQuery):
    await callback.answer()
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    role_key = callback.data.replace("findrole_delete_", "")
    role_short = format_role_display(role_key)

    status_data = load_roles_status()
    role = status_data.get(role_key)

    if not role or not role.get('owner_id'):
        await callback.message.edit_text("❌ Роль уже свободна или не найдена.")
        return

    owner_id = role.get('owner_id')

    await callback.message.edit_text(
        f"⚠️ <b>Вы уверены?</b>\n\n"
        f"Роль: <b>{html.escape(role_short)}</b>\n"
        f"Владелец ID: <code>{owner_id}</code>\n\n"
        f"Будет удалено:\n"
        f"• Роль → статус «свободна»\n"
        f"• Юзер из users.json\n"
        f"• Тег в чате\n"
        f"• Счётчик смен\n\n"
        f"История (users_history) сохранится.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"findrole_delete_yes_{role_key}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="findrole_back")
            ]
        ])
    )

@router.callback_query(F.data == "findrole_back")
async def findrole_back(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "🔍 Для нового поиска используйте /findrole [запрос]"
    )

# ============================================================
# 📊 СТАТИСТИКА ПОЛЬЗОВАТЕЛЯ
# ============================================================

class UserStatsStates(StatesGroup):
    waiting_for_user_id = State()

@router.message(Command('userstats'))
async def cmd_userstats(message: Message, state: FSMContext):
    user_id = message.from_user.id

    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /userstats [ID]")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID. Введите число.")
        return

    await _show_user_stats(message, target_id, caller_id=user_id)

async def _show_user_stats(message: Message, target_id: int, caller_id: int = None):
    from utils.user_utils import get_user_by_id

    user_data = get_user_by_id(target_id)
    role = get_user_role_from_roles(target_id)
    changes = get_changes_count(target_id)

    from handlers.settings_commands import load_settings
    settings = load_settings()
    max_changes = int(settings.get('max_role_changes', 3))

    text = f"📊 <b>Статистика пользователя</b>\n\n"
    text += f"🆔 ID: <code>{target_id}</code>\n"
    text += f"🔗 <a href='tg://user?id={target_id}'>Открыть профиль</a>\n"

    if user_data:
        safe_name = html.escape(user_data.get('full_name', '?'))
        text += f"👤 Имя: {safe_name}\n"
        username = user_data.get('username')
        text += f"🔖 Юзернейм: @{username if username else 'не указан'}\n"
    else:
        text += f"👤 Не найден в users.json\n"

    text += f"🎭 Роль: {html.escape(role) if role else 'нет'}\n"
    text += f"🔄 Смен роли: <b>{changes} / {max_changes}</b>\n"

    try:
        category = get_user_category(target_id)
        emoji = get_emoji(category)
        category_label = get_category_label(category)
        from utils.counters import get_message_count
        msg_count = get_message_count(target_id)
        text += f"{emoji} Норма: {category_label} ({msg_count} соо)\n"
    except Exception as e:
        logger.error(f"Ошибка получения нормы для {target_id}: {e}")

    buttons = [
        [InlineKeyboardButton(
            text="🔄 Сбросить счётчик смен",
            callback_data=f"reset_changes_{target_id}"
        )],
        [InlineKeyboardButton(
            text="🗑️ Сбросить пользователя",
            callback_data=f"confirm_reset_{target_id}"
        )],
    ]

    if caller_id and caller_id == OWNER_ID and caller_id != target_id:
        buttons.append([InlineKeyboardButton(
            text="🗑️ Очистить данные (полностью)",
            callback_data=f"clearme_other_{target_id}"
        )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)

@router.callback_query(F.data.startswith("reset_changes_"))
async def reset_changes_callback(callback: CallbackQuery):
    await callback.answer()
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    target_id = int(callback.data.replace("reset_changes_", ""))

    if reset_changes_count(target_id):
        logger.info(f"🔄 Админ {admin_id} сбросил счётчик смен роли для {target_id}")
        await callback.message.edit_text(
            f"✅ Счётчик смен роли пользователя <code>{target_id}</code> сброшен на 0.",
            parse_mode="HTML"
        )
    else:
        await callback.answer("❌ Не удалось сбросить (юзер не найден).", show_alert=True)

@router.callback_query(F.data.startswith("confirm_reset_"))
async def confirm_reset_callback(callback: CallbackQuery):
    await callback.answer()
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    target_id = int(callback.data.replace("confirm_reset_", ""))

    await callback.message.edit_text(
        f"⚠️ <b>Вы уверены?</b>\n\n"
        f"Сбросить пользователя <code>{target_id}</code>?\n"
        f"Роль будет освобождена, юзер удалён из users.json.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, сбросить", callback_data=f"do_reset_{target_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_reset")
            ]
        ])
    )

@router.callback_query(F.data.startswith("do_reset_"))
async def do_reset_callback(callback: CallbackQuery):
    await callback.answer()
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    target_id = int(callback.data.replace("do_reset_", ""))

    if is_admin(target_id):
        await callback.message.edit_text("⛔ Нельзя сбросить администратора.")
        return

    try:
        await callback.bot.set_chat_member_tag(chat_id=GENERAL_CHAT_ID, user_id=target_id, tag="")
        logger.info(f"🏷️ Удалён тег у пользователя {target_id}")
    except Exception as e:
        logger.error(f"❌ Не удалось удалить тег: {e}")

    old_role = get_user_role_from_roles(target_id)
    freed_role = free_role(target_id) if old_role else None
    removed = remove_user(target_id)

    response = "✅ <b>Пользователь сброшен:</b>\n"
    if freed_role:
        response += f"📌 Освобождена роль: {html.escape(old_role)}\n"
    if removed:
        response += f"👤 Удалён из users.json.\n"
    if not freed_role and not removed:
        response += "ℹ️ Нечего было сбрасывать.\n"

    await callback.message.edit_text(response, parse_mode="HTML")
    logger.info(f"Админ {admin_id} сбросил пользователя {target_id}")

@router.callback_query(F.data == "cancel_reset")
async def cancel_reset_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("❌ Сброс отменён.")

# ============================================================
# 📝 РЕГИСТРАЦИЯ И РОЛИ
# ============================================================

@router.message(Command('register_admin'))
async def cmd_register_admin(message: Message):
    user = message.from_user
    if user is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /register_admin [пароль]")
        return

    password = parts[1]
    from config import ADMIN_PASSWORD
    if password != ADMIN_PASSWORD:
        await message.answer("❌ Неверный пароль для регистрации администратора.")
        logger.warning(f"⚠️ Неудачная попытка регистрации админа от {user.full_name}")
        return

    if is_admin(user.id):
        await message.answer("ℹ️ Вы уже администратор.")
        return

    success = add_admin(user.id, user.username, user.full_name)
    if success:
        rank = get_admin_rank(user.id)
        rank_name = "Владелец" if rank == 1 else "Админ"
        text = f"✅ Вы стали администратором!\nВаш ранг: {rank_name}\nТеперь вам доступны админ-команды."
        if message.chat.id == GENERAL_CHAT_ID:
            await message.answer(text)
        else:
            await message.answer(text, reply_markup=get_main_keyboard(user.id, message.chat.id))
        logger.info(f"✅ НОВЫЙ АДМИН: {user.full_name} (@{user.username}) ID: {user.id}")
    else:
        await message.answer("❌ Ошибка регистрации. Попробуйте позже.")

@router.message(Command('register_user'))
async def cmd_register_user(message: Message):
    user = message.from_user
    if user is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /register_user [пароль]")
        return

    password = parts[1]
    from config import USER_PASSWORD
    if password != USER_PASSWORD:
        await message.answer("❌ Неверный пароль для регистрации участника.")
        logger.warning(f"⚠️ Неудачная попытка регистрации участника от {user.full_name}")
        return

    if user.id in [u['id'] for u in load_users()]:
        await message.answer("ℹ️ Вы уже зарегистрированы как участник.")
        return

    success = add_user(user.id, user.username, user.full_name)
    if success:
        text = "✅ Вы успешно зарегистрированы как участник!"
        if message.chat.id == GENERAL_CHAT_ID:
            await message.answer(text)
        else:
            await message.answer(text, reply_markup=get_main_keyboard(user.id, message.chat.id))
        logger.info(f"✅ НОВЫЙ УЧАСТНИК: {user.full_name} (@{user.username}) ID: {user.id}")
    else:
        await message.answer("❌ Ошибка регистрации. Попробуйте позже.")

@router.message(Command('admins'))
async def cmd_admins(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return

    admins = load_admins()
    if not admins:
        await message.answer("📭 Нет администраторов.")
        return

    text = "👥 <b>Список администраторов:</b>\n\n"
    for a in admins:
        rank_name = {1: "👑 Владелец", 2: "🔐 Админ", 3: "🛡️ Модератор"}.get(a['rank'], "Неизвестно")
        username = f"@{a['username']}" if a['username'] else "без юзернейма"
        text += f"• {html.escape(a['full_name'])} ({username}) – {rank_name} (ID: <code>{a['id']}</code>)\n"

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))

@router.message(Command('users'))
async def cmd_users(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return

    users = load_users()
    if not users:
        await message.answer("📭 Нет участников.")
        return

    text = "👥 <b>Список участников (полный):</b>\n\n"
    for u in users:
        username = f"@{u['username']}" if u['username'] else "без юзернейма"
        role_name = ROLE_NAMES.get(u.get('role', '0'), 'Неизвестно')
        character = get_user_role_from_roles(u['id']) or "Нет роли"

        try:
            category = get_user_category(u['id'])
            emoji = get_emoji(category)
        except Exception:
            emoji = ''

        text += f"{emoji} • {html.escape(u['full_name'])} ({username}) – {role_name} ({character}) (ID: <code>{u['id']}</code>)\n"

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))

@router.message(Command('adduser'))
async def cmd_adduser(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /adduser [ID]")
        return

    try:
        new_user_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID. Введите число.")
        return

    users = load_users()
    for u in users:
        if u['id'] == new_user_id:
            await message.answer(f"ℹ️ Пользователь с ID {new_user_id} уже есть.")
            return

    if add_user(new_user_id, None, f"User {new_user_id}"):
        text = f"✅ Пользователь с ID {new_user_id} добавлен."
        if message.chat.id == GENERAL_CHAT_ID:
            await message.answer(text)
        else:
            await message.answer(text, reply_markup=get_main_keyboard(user_id, message.chat.id))
        logger.info(f"Админ {user_id} добавил участника {new_user_id}")
    else:
        await message.answer("❌ Ошибка при добавлении.")

@router.message(Command('removeuser'))
async def cmd_removeuser(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /removeuser [ID]")
        return

    try:
        remove_user_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID. Введите число.")
        return

    if remove_user(remove_user_id):
        text = f"✅ Пользователь с ID {remove_user_id} удалён."
        if message.chat.id == GENERAL_CHAT_ID:
            await message.answer(text)
        else:
            await message.answer(text, reply_markup=get_main_keyboard(user_id, message.chat.id))
        logger.info(f"Админ {user_id} удалил участника {remove_user_id}")
    else:
        await message.answer(f"❌ Пользователь с ID {remove_user_id} не найден.")

@router.message(Command('resetuser'))
async def cmd_resetuser(message: Message):
    admin_id = message.from_user.id
    if not is_admin(admin_id):
        await message.answer("⛔ Доступ запрещён. Только для администраторов.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /resetuser [ID]")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID. Введите число.")
        return

    if is_admin(target_id):
        await message.answer("⛔ Нельзя сбросить администратора.")
        return

    try:
        await message.bot.set_chat_member_tag(chat_id=GENERAL_CHAT_ID, user_id=target_id, tag="")
        logger.info(f"🏷️ Удалён тег у пользователя {target_id}")
    except Exception as e:
        logger.error(f"❌ Не удалось удалить тег: {e}")

    old_role = get_user_role_from_roles(target_id)
    freed_role = free_role(target_id) if old_role else None
    removed = remove_user(target_id)

    if freed_role or removed:
        response = "✅ Пользователь сброшен:\n"
        if freed_role:
            response += f"📌 Освобождена роль: {html.escape(old_role)}\n"
        if removed:
            response += f"👤 Удалён из списка участников.\n"

        if message.chat.id == GENERAL_CHAT_ID:
            await message.answer(response)
        else:
            await message.answer(response, reply_markup=get_main_keyboard(admin_id, message.chat.id))
        logger.info(f"Админ {admin_id} сбросил пользователя {target_id}")
    else:
        await message.answer(f"ℹ️ Пользователь {target_id} не найден.")

@router.message(Command('refresh'))
async def cmd_refresh(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return

    count = get_users_count()
    text = f"🔄 Список участников обновлён. Всего: {count} человек."

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text)
    else:
        await message.answer(text, reply_markup=get_main_keyboard(user_id, message.chat.id))

@router.message(Command('find'))
async def cmd_find(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /find [ID]")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID. Введите число.")
        return

    users = load_users()
    user_data = None
    for u in users:
        if u['id'] == target_id:
            user_data = u
            break

    request = get_request_by_user_id(target_id)
    role = get_user_role_from_roles(target_id)

    text = f"🔍 <b>Информация о пользователе</b>\n\n"
    text += f"🆔 ID: <code>{target_id}</code>\n"
    text += f"🔗 <a href='tg://user?id={target_id}'>Открыть профиль</a>\n"

    if user_data:
        safe_name = html.escape(user_data['full_name'])
        text += f"👤 Имя: {safe_name}\n"
        text += f"🔖 Юзернейм: @{user_data['username'] if user_data['username'] else 'не указан'}\n"
    else:
        text += f"👤 Пользователь не найден.\n"

    if role:
        text += f"📌 Текущая роль: {html.escape(role)}\n"
    else:
        text += f"📌 Роль: не занята\n"

    if request and request['status'] == 'pending':
        text += f"\n📝 <b>Есть активная заявка!</b>\n"
        text += f"📌 Роль в заявке: {html.escape(request['role'])}\n"
        text += f"🏷️ Должность: {html.escape(request['position'])}\n"

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))

@router.message(Command('finduser'))
async def cmd_finduser(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /finduser [@username]")
        return

    query = parts[1].strip().lstrip('@').lower()
    users = load_users()
    found = [u for u in users if (u.get('username') or '').lower() == query]

    if not found:
        await message.answer(f"❌ Пользователь с юзернеймом @{html.escape(query)} не найден.")
        return

    text = f"🔍 <b>Найдено: {len(found)}</b>\n\n"
    for u in found:
        role = get_user_role_from_roles(u['id']) or "нет"
        text += f"• {html.escape(u['full_name'])} – {html.escape(role)} (ID: <code>{u['id']}</code>)\n"

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))

@router.message(Command('close'))
async def cmd_close(message: Message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        await message.answer("⛔ Только для владельца.")
        return

    from utils.role_utils import set_closed_mode
    set_closed_mode(True)
    await message.answer("🔒 Набор ролей закрыт.")

@router.message(Command('open'))
async def cmd_open(message: Message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        await message.answer("⛔ Только для владельца.")
        return

    from utils.role_utils import set_closed_mode
    set_closed_mode(False)
    await message.answer("🔓 Набор ролей открыт.")

@router.message(Command('setrank'))
async def cmd_setrank(message: Message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        await message.answer("⛔ Только для владельца.")
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("❌ Используйте: /setrank [ID] [ранг]\nРанг: 1/2/3")
        return

    try:
        target_id = int(parts[1])
        new_rank = int(parts[2])
    except ValueError:
        await message.answer("❌ Неверные аргументы.")
        return

    if new_rank not in [1, 2, 3]:
        await message.answer("❌ Ранг должен быть 1, 2 или 3.")
        return

    if target_id == OWNER_ID:
        await message.answer("⛔ Нельзя изменить ранг главного владельца.")
        return

    admins = load_admins()
    found = False
    for a in admins:
        if a['id'] == target_id:
            a['rank'] = new_rank
            found = True
            break

    if not found:
        await message.answer(f"❌ Пользователь {target_id} не в списке админов.")
        return

    save_admins(admins)
    await message.answer(f"✅ Ранг пользователя {target_id} изменён на {new_rank}.")
    logger.info(f"Владелец {user_id} установил ранг {new_rank} для {target_id}")

# ============================================================
# 📢 /message_all — рассылка
# ============================================================

class MessageAllStates(StatesGroup):
    waiting_for_text = State()

@router.message(Command('message_all'))
async def cmd_message_all(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_owner(user_id):
        await message.answer("⛔ Только для владельца.")
        return

    await state.set_state(MessageAllStates.waiting_for_text)
    await message.answer(
        "📢 <b>Рассылка</b>\n\n"
        "Отправьте текст сообщения (HTML разрешён).\n"
        "Для отмены — /cancel",
        parse_mode="HTML"
    )

@router.message(MessageAllStates.waiting_for_text, Command('cancel'))
async def cancel_message_all(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Рассылка отменена.")

@router.message(MessageAllStates.waiting_for_text)
async def do_message_all(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_owner(user_id):
        await state.clear()
        return

    text = message.html_text or message.text or ""
    if not text:
        await message.answer("❌ Пустое сообщение. Отмена.")
        await state.clear()
        return

    users = load_users()
    sent, failed = 0, 0

    await message.answer(f"📢 Начинаю рассылку для {len(users)} юзеров...")

    for u in users:
        try:
            await message.bot.send_message(u['id'], text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await state.clear()
    await message.answer(
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"📨 Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}",
        parse_mode="HTML"
    )
    logger.info(f"Владелец {user_id} сделал рассылку: {sent} ок, {failed} ошибок")

# ============================================================
# ⚠️ /checknorm (кнопка-заглушка для keyboards.py)
# ============================================================

@router.message(Command('checknorm'))
async def cmd_checknorm(message: Message):
    """Перенаправление в checknorm_commands.py."""
    from .checknorm_commands import cmd_checknorm as real_cmd
    await real_cmd(message)