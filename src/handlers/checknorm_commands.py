"""
Команда /checknorm — проверка нормы сообщений.
Интерактив: админ отмечает кого наказывать.
Отправка команд Iris через чат.
"""

import os
import time
import asyncio
import datetime
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import GENERAL_CHAT_ID
from utils.admin_utils import is_admin, get_admin_rank
from utils.user_utils import load_users, get_user_by_id
from utils.norm_utils import (
    CATEGORY_GOOD, CATEGORY_WARN, CATEGORY_BAN,
    get_user_category,
)
from utils.counters import get_message_count
from utils.settings_utils import (
    get_messages_norm, get_messages_norm_low,
    get_warns_accumulate,
    get_checknorm_time_window_enabled,
)

logger = logging.getLogger(__name__)
router = Router()

# FSM
class CheckNormStates(StatesGroup):
    choosing = State()
    preview = State()
    iris_check = State()

# Кулдаун: rank 1 — без, rank 2 — 5 минут
CHECKNORM_COOLDOWN = {}
CHECKNORM_COOLDOWN_SECONDS = 300

# Таймаут FSM — 15 минут
FSM_TIMEOUT = 900

# Активные сессии: {admin_id: {...}}
ACTIVE_SESSIONS = {}
# Глобальный флаг: время последнего запуска /checknorm (для main.py)
CHECKNORM_STARTED_AT = 0

# ⚠️ 02.10.2026: сроки в МИНУТАХ
WARN_MINUTES_DEFAULT = 6 * 24 * 60        # 6 дней
WARN_MINUTES_ACCUMULATE = 21 * 24 * 60    # 21 день (БАГ 3: было 9!)
BAN_MINUTES = 90 * 24 * 60                # 90 дней

def _cleanup_session(admin_id: int):
    if admin_id in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[admin_id]

def _has_active_sessions() -> bool:
    """Есть ли активные сессии чистки (для main.py)."""
    return len(ACTIVE_SESSIONS) > 0

async def _safe_answer(callback: CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass

def _get_mention(user_id: int, full_name: str, username: str = None) -> str:
    safe_name = full_name or f"ID {user_id}"
    if username:
        return f'<a href="tg://user?id={user_id}">@{username}</a>'
    return f'<a href="tg://user?id={user_id}">{safe_name}</a> (ID: <code>{user_id}</code>)'

def _build_checklist_keyboard(admin_id: int) -> InlineKeyboardMarkup:
    session = ACTIVE_SESSIONS.get(admin_id, {})
    selected = session.get('selected', set())
    users_by_cat = session.get('users_by_cat', {})

    all_users = {u['id']: u for u in load_users()}

    buttons = []

    warn_users = users_by_cat.get(CATEGORY_WARN, [])
    if warn_users:
        buttons.append([InlineKeyboardButton(text="⚠️ ВАРН:", callback_data="checknorm_ignore")])
        for uid, count in warn_users:
            user = all_users.get(uid, {})
            name = user.get('full_name', f'ID {uid}')
            mark = "✅" if uid in selected else "❌"
            buttons.append([InlineKeyboardButton(
                text=f"{mark} {name[:25]}",
                callback_data=f"checknorm_toggle_{uid}"
            )])

    ban_users = users_by_cat.get(CATEGORY_BAN, [])
    if ban_users:
        buttons.append([InlineKeyboardButton(text="🚫 БАН:", callback_data="checknorm_ignore")])
        for uid, count in ban_users:
            user = all_users.get(uid, {})
            name = user.get('full_name', f'ID {uid}')
            mark = "✅" if uid in selected else "❌"
            buttons.append([InlineKeyboardButton(
                text=f"{mark} {name[:25]}",
                callback_data=f"checknorm_toggle_{uid}"
            )])

    buttons.append([InlineKeyboardButton(text="📋 Показать итог", callback_data="checknorm_preview")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="checknorm_cancel")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def _build_preview(admin_id: int) -> str:
    session = ACTIVE_SESSIONS.get(admin_id, {})
    selected = session.get('selected', set())
    users_by_cat = session.get('users_by_cat', {})

    all_users = {u['id']: u for u in load_users()}

    warn_users = [u for u in users_by_cat.get(CATEGORY_WARN, []) if u[0] in selected]
    ban_users = [u for u in users_by_cat.get(CATEGORY_BAN, []) if u[0] in selected]
    excluded = (
        [u for u in users_by_cat.get(CATEGORY_WARN, []) if u[0] not in selected] +
        [u for u in users_by_cat.get(CATEGORY_BAN, []) if u[0] not in selected]
    )

    text = "📋 <b>ИТОГ ЧИСТКИ</b>\n\n"

    if excluded:
        text += f"✅ <b>Исключены ({len(excluded)}):</b>\n"
        for uid, count in excluded[:10]:
            user = all_users.get(uid, {})
            text += f"• {_get_mention(uid, user.get('full_name', ''), user.get('username'))}\n"
        if len(excluded) > 10:
            text += f"... и ещё {len(excluded) - 10}\n"
        text += "\n"

    if warn_users:
        text += f"⚠️ <b>Получат ВАРН ({len(warn_users)}):</b>\n"
        for uid, count in warn_users[:15]:
            user = all_users.get(uid, {})
            text += f"• {_get_mention(uid, user.get('full_name', ''), user.get('username'))} — {count} соо\n"
        if len(warn_users) > 15:
            text += f"... и ещё {len(warn_users) - 15}\n"
        text += "\n"

    if ban_users:
        text += f"🚫 <b>Получат БАН ({len(ban_users)}):</b>\n"
        for uid, count in ban_users[:15]:
            user = all_users.get(uid, {})
            text += f"• {_get_mention(uid, user.get('full_name', ''), user.get('username'))} — {count} соо\n"
        if len(ban_users) > 15:
            text += f"... и ещё {len(ban_users) - 15}\n"

    return text

def _build_preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить", callback_data="checknorm_edit")],
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="checknorm_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="checknorm_cancel")],
    ])

def _build_commands(admin_id: int) -> list:
    """Формирует список команд Iris для выбранных юзеров (в днях)."""
    session = ACTIVE_SESSIONS.get(admin_id, {})
    selected = session.get('selected', set())
    users_by_cat = session.get('users_by_cat', {})

    all_users = {u['id']: u for u in load_users()}
    warns_accumulate = get_warns_accumulate()
    warn_minutes = WARN_MINUTES_ACCUMULATE if warns_accumulate else WARN_MINUTES_DEFAULT
    warn_days = warn_minutes // (24 * 60)
    ban_days = BAN_MINUTES // (24 * 60)

    commands = []

    for uid, count in users_by_cat.get(CATEGORY_WARN, []):
        if uid not in selected:
            continue
        user = all_users.get(uid, {})
        username = user.get('username')
        target = f"@{username}" if username else str(uid)
        commands.append(f"Варн {warn_days} дней {target}\nНеактив")

    for uid, count in users_by_cat.get(CATEGORY_BAN, []):
        if uid not in selected:
            continue
        user = all_users.get(uid, {})
        username = user.get('username')
        target = f"@{username}" if username else str(uid)
        commands.append(f"Бан {ban_days} дней {target}\nНеактив")

    return commands

# ======================== КОМАНДА /CHECKNORM ========================

@router.message(Command('checknorm'))
async def cmd_checknorm(message: Message, state: FSMContext = None):
    user_id = message.from_user.id

    if message.chat.id != GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда доступна только во флуд-чате.")
        return

    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return

    # БАГ 9: окно чистки (только 20:00–21:00 МСК)
    if get_checknorm_time_window_enabled():
        now_utc = datetime.datetime.now(datetime.UTC)
        now_msk = now_utc + datetime.timedelta(hours=3)
        if not (now_msk.hour == 20 or (now_msk.hour == 21 and now_msk.minute == 0)):
            await message.answer(
                "⏰ <b>Чистка доступна только с 20:00 до 21:00 МСК.</b>\n\n"
                "Попробуйте позже.",
                parse_mode="HTML"
            )
            return

    rank = get_admin_rank(user_id)

    if rank == 2:
        now = time.time()
        last = CHECKNORM_COOLDOWN.get(user_id, 0)
        if now - last < CHECKNORM_COOLDOWN_SECONDS:
            remaining = int(CHECKNORM_COOLDOWN_SECONDS - (now - last))
            await message.answer(f"⏳ Подождите {remaining} сек перед следующим запуском.")
            return
        CHECKNORM_COOLDOWN[user_id] = now

    norm = get_messages_norm()
    norm_low = get_messages_norm_low()

    users = load_users()
    users_by_cat = {CATEGORY_WARN: [], CATEGORY_BAN: [], CATEGORY_GOOD: []}

    for u in users:
        uid = u.get('id')
        if not uid:
            continue
        try:
            cat = get_user_category(uid)
        except Exception:
            continue
        if cat in users_by_cat:
            count = get_message_count(uid)
            users_by_cat[cat].append((uid, count))

    selected = set()
    for uid, _ in users_by_cat[CATEGORY_WARN]:
        selected.add(uid)
    for uid, _ in users_by_cat[CATEGORY_BAN]:
        selected.add(uid)

    if not selected:
        await message.answer(
            f"✅ <b>Все молодцы!</b>\n\n"
            f"Норма: {norm} соо\n"
            f"НПНДБ: {norm_low} соо\n"
            f"Проблемных нет.",
            parse_mode="HTML"
        )
        return

    global CHECKNORM_STARTED_AT
    CHECKNORM_STARTED_AT = time.time()

    ACTIVE_SESSIONS[user_id] = {
        'started_at': time.time(),
        'selected': selected,
        'users_by_cat': users_by_cat,
    }

    warn_count = len(users_by_cat[CATEGORY_WARN])
    ban_count = len(users_by_cat[CATEGORY_BAN])
    good_count = len(users_by_cat[CATEGORY_GOOD])

    await message.answer(
        f"📊 <b>Проверка нормы за неделю</b>\n\n"
        f"⚠️ Варн: {warn_count}\n"
        f"🚫 Бан: {ban_count}\n"
        f"✅ Хороших: {good_count}\n\n"
        f"Все отмечены ✅ по умолчанию.\n"
        f"Нажмите на юзера чтобы исключить (станет ❌).\n\n"
        f"⏰ У вас 15 минут на завершение.",
        parse_mode="HTML",
        reply_markup=_build_checklist_keyboard(user_id)
    )

# ======================== ИНТЕРАКТИВ ========================

@router.callback_query(F.data == "checknorm_ignore")
async def checknorm_ignore(callback: CallbackQuery):
    await _safe_answer(callback)

@router.callback_query(F.data.startswith("checknorm_toggle_"))
async def checknorm_toggle(callback: CallbackQuery):
    await _safe_answer(callback)
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        return

    session = ACTIVE_SESSIONS.get(admin_id)
    if not session:
        return

    if time.time() - session['started_at'] > FSM_TIMEOUT:
        _cleanup_session(admin_id)
        return

    try:
        target_id = int(callback.data.replace("checknorm_toggle_", ""))
    except ValueError:
        return

    if target_id in session['selected']:
        session['selected'].discard(target_id)
    else:
        session['selected'].add(target_id)

    try:
        await callback.message.edit_reply_markup(reply_markup=_build_checklist_keyboard(admin_id))
    except Exception:
        pass

@router.callback_query(F.data == "checknorm_preview")
async def checknorm_preview(callback: CallbackQuery):
    await _safe_answer(callback)
    admin_id = callback.from_user.id

    session = ACTIVE_SESSIONS.get(admin_id)
    if not session:
        return

    text = _build_preview(admin_id)

    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=_build_preview_keyboard()
        )
    except Exception:
        pass

@router.callback_query(F.data == "checknorm_edit")
async def checknorm_edit(callback: CallbackQuery):
    await _safe_answer(callback)
    admin_id = callback.from_user.id
    session = ACTIVE_SESSIONS.get(admin_id)
    if not session:
        return

    try:
        await callback.message.edit_text(
            "📊 <b>Отметьте кого наказывать</b>\n\n"
            "✅ — наказать, ❌ — исключить.",
            parse_mode="HTML",
            reply_markup=_build_checklist_keyboard(admin_id)
        )
    except Exception:
        pass

@router.callback_query(F.data == "checknorm_cancel")
async def checknorm_cancel(callback: CallbackQuery):
    await _safe_answer(callback)
    admin_id = callback.from_user.id
    _cleanup_session(admin_id)
    try:
        await callback.message.edit_text("❌ Проверка отменена.")
    except Exception:
        pass

@router.callback_query(F.data == "checknorm_confirm")
async def checknorm_confirm(callback: CallbackQuery):
    await _safe_answer(callback)
    admin_id = callback.from_user.id

    session = ACTIVE_SESSIONS.get(admin_id)
    if not session:
        return

    try:
        await callback.message.edit_text(
            "📋 <b>Готово к отправке</b>\n\n"
            "Бот отправит список команд вам в <b>ЛС</b>.\n"
            "Скопируйте и выдайте вручную.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Отправить команды в ЛС", callback_data="checknorm_send_ls")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="checknorm_cancel")],
            ])
        )
    except Exception:
        pass

@router.callback_query(F.data == "checknorm_send_ls")
async def checknorm_send_ls(callback: CallbackQuery):
    await _safe_answer(callback)
    admin_id = callback.from_user.id

    session = ACTIVE_SESSIONS.get(admin_id)
    if not session:
        return

    commands = _build_commands(admin_id)

    if not commands:
        _cleanup_session(admin_id)
        try:
            await callback.message.edit_text("❌ Некого наказывать.")
        except Exception:
            pass
        return

    text = "📋 <b>Команды для ручной выдачи</b>\n\n<code>"
    text += "\n---\n".join(commands)
    text += "</code>\n\n📌 Скопируйте и отправьте в чат вручную."

    try:
        await callback.bot.send_message(admin_id, text, parse_mode="HTML")
        await callback.message.edit_text(
            "✅ Список команд отправлен вам в ЛС.\n"
            "Выдайте наказания вручную."
        )
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка отправки в ЛС: {e}")

    _cleanup_session(admin_id)