import html
import asyncio
import datetime
import time
import calendar
import json
import os
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import logging
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import ADMIN_PASSWORD, USER_PASSWORD, CHAT_INVITE_LINK, ADMIN_GROUP_ID, MODERATOR_LINK, ADMIN_LINK, \
    GENERAL_CHAT_ID
from utils.admin_utils import get_admin_rank, is_admin, is_owner, set_rank, add_admin, save_admins, load_admins
from utils.user_utils import (
    add_user, remove_user, load_users, get_users_count,
    get_users_by_role, get_role_stats as get_user_role_stats, get_role_names,
    update_user_role, get_user_role as get_user_role_name,
    # Новые функции для отписок
    load_unsubscribed, add_unsubscribed, remove_unsubscribed, is_unsubscribed
)
from utils.file_utils import days_since_creation
from utils.requests_utils import (
    add_request, get_pending_requests, approve_request, reject_request,
    get_pending_count, get_request_by_user_id, load_requests, save_requests
)
from utils.user_history import load_user_history
from utils.role_utils import (
    load_roles, save_roles, get_role_by_name, get_roles_by_season,
    get_all_seasons, get_role_status, update_role_status,
    get_taken_roles, get_role_stats, get_user_role as get_user_role_from_roles,
    occupy_role, free_role, ensure_roles_dir, count_taken_roles,
    set_rest, clear_rest, load_roles_status
)
from .keyboards import get_main_keyboard
from utils.emoji_utils import get_user_emoji

# Исправлено: __name__ вместо name
logger = logging.getLogger(__name__)
router = Router()
closed_mode = False

ROLE_NAMES = {
    '0': 'Участник',
    '1': 'Небезопасный клиент',
    '2': 'Неприемлемый ник',
    '3': 'Временный статус (рест/нью)',
    '4': 'Администрация',
    '5': 'Администрация в ресте'
}

BOTS = [
    {'username': 'iris_cm_bot', 'full_name': 'Iris'},
    {'username': 'MafiososBot', 'full_name': 'Мафия'},
    {'username': 'igra_v_slovo_bot', 'full_name': 'Игра в слова'},
    {'username': 'ZazyvalaTag4Bot', 'full_name': 'Зазывала'}
]


class RejectReason(StatesGroup):
    waiting_for_reason = State()


class FreeRoleStates(StatesGroup):
    waiting_confirmation = State()


class RestRequestStates(StatesGroup):
    waiting_for_date = State()
    waiting_for_reason = State()


call_cooldowns = {}
callfal_cooldowns = {}

REST_REQUESTS_FILE = "data/requests/rest_requests.json"


def safe_user_id(message: Message):
    if message.from_user:
        return message.from_user.id
    return None


def safe_user_name(message: Message):
    if message.from_user:
        return message.from_user.full_name
    return "Неизвестный"


def safe_username(message: Message):
    if message.from_user and message.from_user.username:
        return f"@{message.from_user.username}"
    return "без юзернейма"


async def check_admin_state(message: Message, state: FSMContext) -> bool:
    current_state = await state.get_state()
    if current_state == RejectReason.waiting_for_reason:
        await message.answer(
            "⏳ Вы сейчас вводите причину отклонения заявки.\n"
            "Завершите ввод или отмените действие (кнопка '🔙 Отменить')."
        )
        return False
    return True


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ КАЛЕНДАРЯ И РЕСТОВ
# ============================================================

def generate_calendar_keyboard(year, month, callback_prefix="rest_cal"):
    cal = calendar.monthcalendar(year, month)
    keyboard = []
    month_name = calendar.month_name[month]
    header = InlineKeyboardButton(text=f"{month_name} {year}", callback_data="ignore")
    keyboard.append([header])

    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    keyboard.append([InlineKeyboardButton(text=day, callback_data="ignore") for day in week_days])

    today = datetime.date.today()

    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                date_obj = datetime.date(year, month, day)
                if date_obj < today:
                    row.append(InlineKeyboardButton(text=str(day), callback_data="ignore"))
                else:
                    callback_data = f"{callback_prefix}_{year}_{month}_{day}"
                    row.append(InlineKeyboardButton(text=str(day), callback_data=callback_data))
        keyboard.append(row)

    nav_row = []
    if month > 1:
        nav_row.append(InlineKeyboardButton(text="<", callback_data=f"{callback_prefix}_prev_{year}_{month}"))
    else:
        nav_row.append(InlineKeyboardButton(text="<", callback_data=f"{callback_prefix}_prev_{year - 1}_12"))

    nav_row.append(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_rest_request"))

    if month < 12:
        nav_row.append(InlineKeyboardButton(text=">", callback_data=f"{callback_prefix}_next_{year}_{month}"))
    else:
        nav_row.append(InlineKeyboardButton(text=">", callback_data=f"{callback_prefix}_next_{year + 1}_1"))

    keyboard.append(nav_row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def load_rest_requests():
    os.makedirs(os.path.dirname(REST_REQUESTS_FILE), exist_ok=True)
    try:
        with open(REST_REQUESTS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_rest_requests(requests):
    os.makedirs(os.path.dirname(REST_REQUESTS_FILE), exist_ok=True)
    with open(REST_REQUESTS_FILE, 'w') as f:
        json.dump(requests, f, indent=4)


# ============================================================
# КОМАНДЫ ДЛЯ ВСЕХ
# ============================================================

@router.message(Command('start'))
async def cmd_start(message: Message):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    logger.info(f"👤 {safe_user_name(message)} нажал /start")

    request = get_request_by_user_id(user_id)
    status_text = ""
    if request:
        if request['status'] == 'pending':
            status_text = "\n\n📌 Ваша заявка рассматривается администрацией."
        elif request['status'] == 'approved':
            status_text = "\n\n✅ Ваша заявка одобрена!"
        elif request['status'] == 'rejected':
            status_text = "\n\n❌ Ваша заявка отклонена. Попробуйте подать новую."

    safe_name = html.escape(safe_user_name(message))
    text = (
        f"👋 Добро пожаловать, <b>{safe_name}</b>!\n\n"
        f"Я бот для управления ролями и заявками.\n"
        f"Если у вас есть вопросы — напишите <b>@Sedrikai_bot</b> (бот-пересыльщик), "
        f"и ближайший освободившийся администратор ответит вам, как только сможет.\n\n"
        f"📌 Используйте /help для списка команд.{status_text}"
    )

    # ЖЕСТКОЕ ПРАВИЛО: Никаких клавиатур во флуде
    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))


@router.message(Command('help'))
async def cmd_help(message: Message):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    is_admin_user = is_admin(user_id)

    help_text = (
        "📚 <b>Доступные команды</b>\n\n"
        "👤 <b>Для всех:</b>\n"
        "/start – приветствие\n"
        "/help – эта справка\n"
        "/about – информация о флуд-чате\n"
        "/aboutme – ваши данные\n"
        "/members – список участников\n"
        "/roles – список ролей\n"
        "/apply – подать заявку\n"
        "/free – освободить роль\n"
        "/cancel_request – отменить заявку\n"
        "/unregc – отписаться от калов\n"
        "/regc – подписаться на калы\n"
        "/rest – подать заявку на рест\n"
    )

    if is_admin_user:
        help_text += (
            "\n🔐 <b>Административные команды:</b>\n"
            "/admins – список администраторов\n"
            "/users – список участников\n"
            "/adduser – добавить участника\n"
            "/removeuser – удалить участника\n"
            "/resetuser – сбросить пользователя\n"
            "/refresh – обновить список участников\n"
            "/find – найти пользователя\n"
            "/finduser – найти пользователя по юзернейму\n"
            "/broadcast – рассылка всем участникам\n"
            "/call – сделать кал\n"
            "/callfal – непропускаемый кал\n"
            "/check_chats – диагностика чатов\n"
            "/diag – диагностика команд (владелец)\n"
            "/unregister_admin – удалить себя из админов\n"
            "/unregister_user – удалить себя из участников\n\n"
            "📝 <b>Управление заявками:</b>\n"
            "/requests – список заявок\n"
            "/approve – одобрить заявку\n"
            "/reject – отклонить заявку\n\n"
            "📋 <b>Списки и статистика:</b>\n"
            "/roster – полный список с индексами\n"
            "/stats – статистика по ролям\n"
            "/restlist – список активных рестов\n\n"
            "⏳ <b>Рест:</b>\n"
            "/unrest – снять рест с роли\n"
            "/restextend – продлить рест\n\n"
            "👑 <b>Владелец:</b>\n"
            "/setrank – назначить ранг\n"
            "/close – закрыть набор\n"
            "/open – открыть набор\n"
        )
    else:
        help_text += (
            "\n💬 <b>Связь с администрацией:</b>\n"
            "Если у вас есть вопросы – напишите <b>@Sedrikai_bot</b>\n"
            "Ближайший администратор ответит вам, как только сможет."
        )

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(help_text, parse_mode="HTML")
    else:
        await message.answer(help_text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))


@router.message(Command('about'))
async def cmd_about(message: Message):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    users_count = count_taken_roles()
    pending_count = get_pending_count()
    flood_creation = datetime.date(2026, 5, 12)
    days = (datetime.date.today() - flood_creation).days

    text = (
        f"💬 <b>Информация о флуде (чате)</b>\n\n"
        f"👥 Участников: {users_count}\n"
        f"📅 Чату: {days} дн. (создан 12 мая 2026 года)\n"
        f"📝 Заявок в ожидании: {pending_count}\n\n"
        f"🔗 <b>Ссылка для просмотра инфо:</b>\n"
        f"👉 <a href='https://t.me/+p7g_-IQv-v5kYjgy'>Нажмите для просмотра</a>\n\n"
        f"📝 <b>Хотите вступить?</b>\n"
        f"Подайте заявку через /apply"
    )

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text, parse_mode="HTML", disable_web_page_preview=False)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id),
                             disable_web_page_preview=False)


@router.message(Command('aboutme'))
async def cmd_aboutme(message: Message):
    user = message.from_user
    if user is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    rank = get_admin_rank(user.id)
    rank_name = {1: "👑 Владелец", 2: "🔐 Админ", 3: "🛡️ Модератор"}.get(rank, "👤 Нет")
    user_role = get_user_role_from_roles(user.id) or get_user_role_name(user.id)
    role_name = ROLE_NAMES.get(user_role, "Не определена") if user_role else "Не определена"
    character = get_user_role_from_roles(user.id) or "Не указан"

    request = get_request_by_user_id(user.id)
    status_text = " "
    if request:
        status_map = {
            'pending': '⏳ Ожидает рассмотрения',
            'approved': '✅ Одобрена',
            'rejected': '❌ Отклонена'
        }
        status_text = f"\n📝 Статус заявки: {status_map.get(request['status'], 'Неизвестно')} "
        if request['status'] == 'pending':
            status_text += f"\n📌 Роль: {request.get('role', 'Не указана')} "
            status_text += f"\n📌 Должность: {request.get('position', 'Не указана')} "

    safe_name = html.escape(user.full_name)
    safe_username = html.escape(user.username if user.username else 'не указан')

    text = (
        f"📝 <b>Ваши данные</b>\n\n"
        f"👤 Имя: <b>{safe_name}</b>\n"
        f"🔖 Юзернейм: @{safe_username}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"⭐ Ранг: {rank_name}\n"
        f"📌 Роль: {role_name}\n"
        f"🎭 Персонаж: {character}{status_text}"
    )

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user.id, message.chat.id))


@router.message(Command('members'))
async def cmd_members(message: Message):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    if message.chat.id == GENERAL_CHAT_ID:
        is_admin_user = is_admin(user_id)
        users = load_users()
        if not users:
            await message.answer("📭 В списке пока нет участников.")
            return
        if is_admin_user:
            text = f"👥 <b>Список участников (полный из локального хранилища)</b>\n"
            text += f"📅 {datetime.date.today().strftime('%d.%m.%Y')}\n"
            text += f"👥 Всего: {len(users)}\n\n"
            text += "<b>Пользователи:</b>\n"
            for u in users:
                role_name = ROLE_NAMES.get(u.get('role', '0'), 'Неизвестно')
                character = get_user_role_from_roles(u['id']) or "Нет роли"
                username = f"@{u['username']}" if u['username'] else "без юзернейма"
                text += f"ID: <code>{u['id']}</code> | {username} | {html.escape(u['full_name'])} | {role_name} | {character}\n"
            await message.answer(text, parse_mode="HTML")
        else:
            taken = get_taken_roles()
            if not taken:
                await message.answer("📭 Нет занятых ролей.")
                return
            text = f"👥 <b>Занятые роли ({len(taken)})</b>\n\n"
            for role in sorted(taken):
                text += f"• {html.escape(role)}\n"
            await message.answer(text, parse_mode="HTML")
    else:
        is_admin_user = is_admin(user_id)
        users = load_users()
        if not users:
            await message.answer("📭 В списке пока нет участников.")
            return
        if is_admin_user:
            text = f"👥 <b>Список участников (полный)</b>\n"
            text += f"📅 {datetime.date.today().strftime('%d.%m.%Y')}\n"
            text += f"👥 Всего: {len(users)}\n\n"
            text += "<b>Пользователи:</b>\n"
            for u in users:
                role_name = ROLE_NAMES.get(u.get('role', '0'), 'Неизвестно')
                character = get_user_role_from_roles(u['id']) or "Нет роли"
                username = f"@{u['username']}" if u['username'] else "без юзернейма"
                text += f"ID: <code>{u['id']}</code> | {username} | {html.escape(u['full_name'])} | {role_name} | {character}\n"
            await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))
        else:
            taken = get_taken_roles()
            if not taken:
                await message.answer("📭 Нет занятых ролей.")
                return
            text = f"👥 <b>Занятые роли ({len(taken)})</b>\n\n"
            for role in sorted(taken):
                text += f"• {html.escape(role)}\n"
            await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))


@router.message(Command('roster'))
async def cmd_roster(message: Message):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён. Только для администраторов.")
        return
    users = load_users()
    if not users:
        await message.answer("📭 В списке пока нет участников.")
        return
    role_order = ['2', '4', '0', '1', '3', '5']
    roles = {}
    for u in users:
        role = u.get('role', '0')
        if role not in roles:
            roles[role] = []
        roles[role].append(u)
    text = f"📋 <b>Список на {datetime.date.today().strftime('%d.%m.%Y')}</b>\n"
    text += f"Версия 5.4.0.0 (отсортирован: 2→4→0→1→3→5)\n\n"
    counter = 1
    for role_key in role_order:
        if role_key in roles:
            for u in roles[role_key]:
                username = f"@{u['username']}" if u['username'] else "без юзернейма"
                extra = f" ({html.escape(u.get('extra', ''))}) " if u.get('extra') else " "
                text += f"{counter}. (ind:{role_key}) {username} {html.escape(u['full_name'])}{extra}\n"
                counter += 1
    text += f"\n{counter}. Боты\n"
    text += f"{counter + 1}. Боты\n"
    text += f"{counter + 2}. Боты\n"
    text += f"{counter + 3}. Боты"
    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))


@router.message(Command('stats'))
async def cmd_stats(message: Message):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён. Только для администраторов.")
        return
    stats = get_role_stats()
    total = get_users_count()
    text = f"📊 <b>Статистика по ролям</b>\n"
    text += f"📅 {datetime.date.today().strftime('%d.%m.%Y')}\n"
    text += f"👥 Всего: {total + len(BOTS)}\n\n"
    role_order = ['4', '2', '0', '1', '3', '5']
    for role_key in role_order:
        if role_key in stats:
            role_name = ROLE_NAMES.get(role_key, role_key)
            text += f"• {role_name}: {stats[role_key]}\n"
    text += f"\n🤖 Боты: {len(BOTS)}"
    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))


@router.message(Command('roles'))
async def cmd_roles(message: Message):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    seasons = get_all_seasons()
    if not seasons:
        await message.answer("📭 Сезоны не найдены.")
        return
    buttons = []
    for season in sorted(seasons):
        roles = get_roles_by_season(season)
        buttons.append([InlineKeyboardButton(
            text=f"📂 {season} ({len(roles)})",
            callback_data=f"roles_season_{season}"
        )])
    buttons.append([InlineKeyboardButton(
        text="🔙 Назад в меню",
        callback_data="back_to_menu_from_roles"
    )])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(
        "📋 <b>Список ролей по сезонам</b>\n\n"
        "Выберите сезон для просмотра всех ролей с их статусами.\n"
        "В скобках указано общее количество ролей в сезоне.\n\n"
        "🟢 свободна | 🟡 забронирована | 🔴 занята | 🔵 рест",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "back_to_menu_from_roles")
async def back_to_menu_from_roles(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    await callback.message.delete()
    if callback.message.chat.id == GENERAL_CHAT_ID:
        await callback.message.answer("🔙 Вы вернулись в главное меню.")
    else:
        await callback.message.answer("🔙 Вы вернулись в главное меню.",
                                      reply_markup=get_main_keyboard(user_id, callback.message.chat.id))


@router.callback_query(F.data.startswith("roles_season_"))
async def show_roles_by_season(callback: CallbackQuery):
    await callback.answer()
    season = callback.data.replace("roles_season_", "")
    roles = get_roles_by_season(season)
    status_data = load_roles_status()
    if not roles:
        await callback.message.edit_text(
            f"📭 В сезоне <b>{html.escape(season)}</b> нет ролей.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К сезонам", callback_data="back_to_roles_seasons")]
            ])
        )
        return
    text = f"📋 <b>Сезон: {html.escape(season)}</b>\n\n"
    for role in roles:
        status = status_data.get(role, {}).get('status', 'свободна')
        if status == 'свободна':
            status_text = "🟢 свободна"
        elif status == 'бронь':
            status_text = "🟡 забронирована"
        elif status == 'рест':
            extra = status_data.get(role, {}).get('extra', '')
            status_text = f"🔵 рест до {extra}" if extra else "🔵 рест"
        else:
            status_text = "🔴 занята"
        text += f"  • {html.escape(role)} — {status_text}\n"
    if len(text) > 4000:
        part1 = text[:3900]
        part2 = "\n... продолжение ...\n" + text[3900:]
        await callback.message.edit_text(part1, parse_mode="HTML")
        await callback.message.answer(
            part2,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К сезонам", callback_data="back_to_roles_seasons")]
            ])
        )
    else:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К сезонам", callback_data="back_to_roles_seasons")]
            ])
        )


@router.callback_query(F.data == "back_to_roles_seasons")
async def back_to_roles_seasons(callback: CallbackQuery):
    await callback.answer()
    seasons = get_all_seasons()
    if not seasons:
        await callback.message.edit_text("📭 Сезоны не найдены.")
        return
    buttons = []
    for season in sorted(seasons):
        roles = get_roles_by_season(season)
        buttons.append([InlineKeyboardButton(
            text=f"📂 {season} ({len(roles)})",
            callback_data=f"roles_season_{season}"
        )])
    buttons.append([InlineKeyboardButton(
        text="🔙 Назад в меню",
        callback_data="back_to_menu_from_roles"
    )])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(
        "📋 <b>Список ролей по сезонам</b>\n\n"
        "Выберите сезон для просмотра всех ролей с их статусами.\n"
        "В скобках указано общее количество ролей в сезоне.\n\n"
        "🟢 свободна | 🟡 забронирована | 🔴 занята | 🔵 рест",
        parse_mode="HTML",
        reply_markup=keyboard
    )


# ============================================================
# СИСТЕМА КАЛОВ И ОТВИЗКИ
# ============================================================

@router.message(Command('call'))
async def cmd_call(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if chat_id != GENERAL_CHAT_ID:
        return

    if not is_admin(user_id):
        try:
            chat_member = await message.bot.get_chat_member(chat_id, user_id)
            if chat_member.status not in ['creator', 'administrator']:
                await message.answer("⛔ Только модераторы и администраторы могут использовать эту команду.")
                return
        except Exception as e:
            logger.error(f"❌ Ошибка проверки прав во флуде: {e}")
            await message.answer("⛔ У вас недостаточно прав для использования этой команды.")
            return

    last_call = call_cooldowns.get(user_id, 0)
    current_time = time.time()
    if current_time - last_call < 15:
        remaining = int(15 - (current_time - last_call))
        await message.answer(f"⏳ Подождите {remaining} секунд перед следующим калом.")
        return

    parts = message.text.split(maxsplit=1)
    call_text = parts[1][:300] if len(parts) > 1 else ""

    status_msg = await message.answer("📡 Получаю список участников из локального хранилища...")

    users = load_users()
    unsubscribed = load_unsubscribed()

    members = []
    for u in users:
        u_id = u['id']
        if u_id in unsubscribed:
            continue
        if u_id == user_id:
            continue

        class SimpleUser:
            def __init__(self, user_dict):
                self.id = user_dict['id']

        members.append(SimpleUser(u))

    logger.info(f"✅ Загружено {len(members)} участников из локального хранилища (исключены отписавшиеся и вызывающий)")

    if not members:
        await status_msg.edit_text("❌ В локальном списке нет участников для кала.")
        return

    await status_msg.delete()

    sent_count = 0
    batch_size = 5
    first_batch = True
    errors = 0
    for i in range(0, len(members), batch_size):
        batch = members[i:i + batch_size]
        mentions = []
        for user in batch:
            u_id = user.id
            emoji = get_user_emoji(u_id)
            mentions.append(f'<a href="tg://user?id={u_id}">{emoji}</a>')

        if first_batch:
            if call_text:
                message_text = f"{' '.join(mentions)} {call_text}"
            else:
                message_text = f"{' '.join(mentions)}"
            first_batch = False
        else:
            message_text = f"{' '.join(mentions)}"

        try:
            await message.answer(message_text, parse_mode="HTML")
            sent_count += len(batch)
        except Exception as e:
            errors += 1
            logger.error(f"❌ Ошибка отправки кала во флуде: {e}")
        await asyncio.sleep(0.3)

    call_cooldowns[user_id] = current_time
    logger.info(
        f"📢 Кал отправлен во флуде пользователем {user_id}. Упомянуто участников: {sent_count}, Ошибок: {errors}")

    result_text = f"✅ Кал отправлен! Упомянуто участников: {sent_count}"
    if errors > 0:
        result_text += f"\n⚠️ Ошибок при отправке: {errors}"

    await message.answer(result_text)


@router.message(Command('callfal'))
async def cmd_callfal(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if chat_id != GENERAL_CHAT_ID:
        return

        # Только Админ и Владелец (Модер НЕ может)
    if not (is_admin(user_id) and get_admin_rank(user_id) in [1, 2]):
        await message.answer("⛔ Только владелец и администраторы могут использовать эту команду.")
        return

    last_call = callfal_cooldowns.get(user_id, 0)
    current_time = time.time()
    if current_time - last_call < 30:
        remaining = int(30 - (current_time - last_call))
        await message.answer(f"⏳ Подождите {remaining} секунд перед следующим непропускаемым калом.")
        return

    parts = message.text.split(maxsplit=1)
    call_text = parts[1][:300] if len(parts) > 1 else ""

    status_msg = await message.answer("📡 Получаю список участников...")

    users = load_users()
    unsubscribed = load_unsubscribed()

    members = []
    for u in users:
        u_id = u['id']
        if u_id in unsubscribed:
            continue

        class SimpleUser:
            def __init__(self, user_dict):
                self.id = user_dict['id']

        members.append(SimpleUser(u))

    if not members:
        await status_msg.edit_text("❌ В локальном списке нет участников.")
        return

    await status_msg.delete()

    sent_count = 0
    batch_size = 5
    first_batch = True
    errors = 0
    for i in range(0, len(members), batch_size):
        batch = members[i:i + batch_size]
        mentions = []
        for user in batch:
            u_id = user.id
            emoji = get_user_emoji(u_id)
            mentions.append(f'<a href="tg://user?id={u_id}">{emoji}</a>')

        if first_batch:
            if call_text:
                message_text = f"{' '.join(mentions)} {call_text}"
            else:
                message_text = f"{' '.join(mentions)}"
            first_batch = False
        else:
            message_text = f"{' '.join(mentions)}"

        try:
            await message.answer(message_text, parse_mode="HTML")
            sent_count += len(batch)
        except Exception as e:
            errors += 1
            logger.error(f"❌ Ошибка отправки /callfal: {e}")
        await asyncio.sleep(0.3)

    callfal_cooldowns[user_id] = current_time
    logger.info(f"📢 /callfal отправлен пользователем {user_id}. Упомянуто: {sent_count}, Ошибок: {errors}")

    result_text = f"✅ Непропускаемый кал отправлен! Упомянуто участников: {sent_count}"
    if errors > 0:
        result_text += f"\n⚠️ Ошибок при отправке: {errors}"
    await message.answer(result_text)


@router.message(Command('unregc'))
async def cmd_unregc(message: Message):
    user_id = message.from_user.id
    users = load_users()
    user_ids = [u['id'] for u in users]

    if user_id not in user_ids:
        await message.answer("❌ Не вижу вас в списке. Зарегистрируйтесь в @REG_sf_bot через /apply")
        return

    if is_unsubscribed(user_id):
        await message.answer("ℹ️ Вы уже отписаны от калов.")
        return

    add_unsubscribed(user_id)
    logger.info(f"👤 Пользователь {user_id} отписался от калов")
    await message.answer("✅ Вы успешно отписались от калов. Теперь вас не будут упоминать.")


@router.message(Command('regc'))
async def cmd_regc(message: Message):
    user_id = message.from_user.id
    users = load_users()
    user_ids = [u['id'] for u in users]

    if user_id not in user_ids:
        await message.answer("❌ Не вижу вас в списке. Зарегистрируйтесь в @REG_sf_bot через /apply")
        return

    if not is_unsubscribed(user_id):
        await message.answer("ℹ️ Вы уже в списке рассылки.")
        return

    remove_unsubscribed(user_id)
    logger.info(f"👤 Пользователь {user_id} подписался на калы")
    await message.answer("✅ Вы успешно подписались на калы. Теперь вас будут упоминать.")


# ============================================================
# ДИАГНОСТИКА КОМАНД (/diag)
# ============================================================

@router.message(Command('diag'))
async def cmd_diag(message: Message):
    """Диагностика всех команд (только для владельца)."""
    user_id = message.from_user.id

    # Проверка прав: только владелец
    if not is_owner(user_id):
        await message.answer("⛔ Доступ запрещён. Только для владельца.")
        return

    logger.info(f"🔍 Владелец {user_id} запустил диагностику команд")

    # Получаем информацию о боте
    me = await message.bot.get_me()
    bot_username = me.username
    bot_id = me.id

    # Получаем список всех зарегистрированных хендлеров сообщений
    handlers_info = []
    for handler in router.message.handlers:
        # Проверяем фильтры хендлера на наличие команды
        if hasattr(handler, 'filters'):
            for f in handler.filters:
                if hasattr(f, 'command') and f.command:
                    # f.command может быть строкой или списком/кортежем
                    cmds = f.command if isinstance(f.command, (list, tuple)) else [f.command]
                    for cmd in cmds:
                        handlers_info.append(f"/{cmd}")

    # Убираем дубликаты и сортируем
    handlers_info = sorted(list(set(handlers_info)))

    # Формируем отчет
    report = "📋 <b>Диагностика команд</b>\n\n"
    report += f"🤖 Бот: @{bot_username}\n"
    report += f"🆔 ID бота: <code>{bot_id}</code>\n"
    report += f"👤 Ваш ID: <code>{user_id}</code>\n\n"

    report += f"✅ Зарегистрировано команд: {len(handlers_info)}\n\n"

    if handlers_info:
        report += "<b>Список команд:</b>\n"
        for cmd in handlers_info:
            report += f"• {cmd}\n"
    else:
        report += "⚠️ Команды не найдены!\n"

    # Информация о фоновых задачах
    report += "\n🔄 <b>Фоновые задачи:</b>\n"
    report += "• Синхронизация пользователей: Активна\n"
    report += "• Проверка рестов: Активна\n"

    await message.answer(report, parse_mode="HTML")


# ============================================================
# ДИАГНОСТИКА ЧАТОВ (/check_chats)
# ============================================================

@router.message(Command('check_chats'))
async def cmd_check_chats(message: Message):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not is_owner(user_id):
        await message.answer("⛔ Доступ запрещён. Только для владельца.")
        return
    if message.chat.id != GENERAL_CHAT_ID:
        await message.answer("🔍 Проверка чатов доступна только во флуд-чате для владельца.")
        return

    await message.answer("🔍 Проверяю чаты, где есть бот...")
    try:
        result = "📋 <b>Статус бота в чатах:</b>\n\n"
        try:
            chat = await message.bot.get_chat(GENERAL_CHAT_ID)
            member = await message.bot.get_chat_member(GENERAL_CHAT_ID, message.bot.id)
            status = member.status
            status_emoji = {'creator': '👑', 'administrator': '🔐', 'member': '👤', 'restricted': '⛔', 'left': '❌',
                            'kicked': '🚫'}.get(status, '❓')
            result += f"{status_emoji} <b>Флуд-чат:</b>\n   • ID: <code>{GENERAL_CHAT_ID}</code>\n   • Название: {html.escape(chat.title)}\n   • Статус: <b>{status}</b>\n"
            if status in ['creator', 'administrator']:
                permissions = []
                if member.can_manage_chat: permissions.append("Управление чатом")
                if member.can_delete_messages: permissions.append("Удаление сообщений")
                if member.can_restrict_members: permissions.append("Ограничение участников")
                if member.can_promote_members: permissions.append("Назначение админов")
                if member.can_invite_users: permissions.append("Приглашение")
                if member.can_pin_messages: permissions.append("Закрепление")
                if member.can_manage_video_chats: permissions.append("Управление видеочатами")
                if hasattr(member, 'can_manage_topics') and member.can_manage_topics: permissions.append(
                    "Управление темами")
                result += f"   • Права: {', '.join(permissions) if permissions else 'Только базовые'}\n"
                if hasattr(member, 'can_manage_tags'):
                    result += f"   • Управление тегами: {'✅' if member.can_manage_tags else '❌'}\n"
            result += "\n"
        except Exception as e:
            result += f"❌ <b>Флуд-чат:</b> Ошибка — {e}\n\n"
        try:
            chat = await message.bot.get_chat(ADMIN_GROUP_ID)
            member = await message.bot.get_chat_member(ADMIN_GROUP_ID, message.bot.id)
            status = member.status
            status_emoji = {'creator': '👑', 'administrator': '🔐', 'member': '👤', 'restricted': '⛔', 'left': '❌',
                            'kicked': '🚫'}.get(status, '❓')
            result += f"{status_emoji} <b>Админ-группа:</b>\n   • ID: <code>{ADMIN_GROUP_ID}</code>\n   • Название: {html.escape(chat.title)}\n   • Статус: <b>{status}</b>\n"
            if status in ['creator', 'administrator']:
                permissions = []
                if member.can_delete_messages: permissions.append("Удаление сообщений")
                if member.can_restrict_members: permissions.append("Ограничение участников")
                if member.can_invite_users: permissions.append("Приглашение")
                result += f"   • Права: {', '.join(permissions) if permissions else 'Только базовые'}\n"
            result += "\n"
        except Exception as e:
            result += f"❌ <b>Админ-группа:</b> Ошибка — {e}\n\n"
        try:
            chat = await message.bot.get_chat(message.chat.id)
            member = await message.bot.get_chat_member(message.chat.id, message.bot.id)
            status = member.status
            status_emoji = {'creator': '👑', 'administrator': '🔐', 'member': '👤', 'restricted': '⛔', 'left': '❌',
                            'kicked': '🚫'}.get(status, '❓')
            result += f"{status_emoji} <b>Текущий чат:</b>\n   • ID: <code>{message.chat.id}</code>\n   • Название: {html.escape(chat.title) if chat.title else 'Личка'}\n   • Тип: {message.chat.type}\n   • Статус: <b>{status}</b>\n"
        except Exception as e:
            result += f"❌ <b>Текущий чат:</b> Ошибка — {e}\n"
        try:
            total_members = await message.bot.get_chat_member_count(chat_id=GENERAL_CHAT_ID)
            result += f"\n📊 <b>Всего участников в флуд-чате:</b> {total_members}"
        except AttributeError:
            try:
                total_members = await message.bot.get_chat_members_count(chat_id=GENERAL_CHAT_ID)
                result += f"\n📊 <b>Всего участников в флуд-чате:</b> {total_members}"
            except Exception as e2:
                result += f"\n❌ Не удалось посчитать участников: {e2}"
        except Exception as e:
            result += f"\n❌ Не удалось посчитать участников: {e}"
        await message.answer(result, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка диагностики: {e}")


# ============================================================
# ОСВОБОЖДЕНИЕ РОЛИ (С ПОДТВЕРЖДЕНИЕМ)
# ============================================================

@router.message(Command('free'))
async def cmd_free(message: Message, state: FSMContext):
    user = message.from_user
    if user is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    user_role = get_user_role_from_roles(user.id)
    if not user_role:
        await message.answer("❌ У вас нет занятой или забронированной роли.")
        return
    role_data = get_role_by_name(user_role)
    if not role_data:
        await message.answer("❌ Ошибка: роль не найдена.")
        return
    status = role_data.get('status', '')
    if status not in ['занята', 'бронь']:
        await message.answer(f"❌ Роль '{html.escape(user_role)}' имеет статус '{status}'. Освобождение невозможно.")
        return
    request = get_request_by_user_id(user.id)
    has_pending_request = request and request.get('status') == 'pending'
    await state.update_data(role_to_free=user_role, has_pending_request=has_pending_request,
                            request_role=request.get('role') if has_pending_request else None)
    await state.set_state(FreeRoleStates.waiting_confirmation)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, освободить", callback_data="free_confirm_yes"),
         InlineKeyboardButton(text="❌ Отмена", callback_data="free_confirm_no")]
    ])
    status_text = "забронирована" if status == 'бронь' else "занята"
    warning_text = ""
    if has_pending_request:
        warning_text = f"\n\n⚠️ <b>Внимание!</b> У вас есть активная заявка на роль '<b>{html.escape(request['role'])}</b>'.\nОна будет автоматически удалена при освобождении роли."
    await message.answer(
        f"⚠️ <b>Вы уверены, что хотите освободить роль?</b>\n\n"
        f"📌 Роль: <b>{html.escape(user_role)}</b>\n"
        f"📊 Статус: <b>{status_text}</b>{warning_text}\n\n"
        f"После освобождения вы сможете подать новую заявку через /apply.",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "free_confirm_yes")
async def free_confirm_yes(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    data = await state.get_data()
    role_to_free = data.get('role_to_free')
    has_pending_request = data.get('has_pending_request', False)
    if not role_to_free:
        await callback.message.edit_text("❌ Ошибка: роль не найдена. Попробуйте снова через /free.")
        await state.clear()
        return
    current_role = get_user_role_from_roles(user_id)
    if current_role != role_to_free:
        await callback.message.edit_text(f"❌ Роль '{html.escape(role_to_free)}' уже была освобождена или изменена.",
                                         parse_mode="HTML")
        await state.clear()
        return
    role_data = get_role_by_name(role_to_free)
    if not role_data:
        await callback.message.edit_text(f"❌ Роль '{html.escape(role_to_free)}' не найдена в системе.",
                                         parse_mode="HTML")
        await state.clear()
        return
    status = role_data.get('status', '')
    if status not in ['занята', 'бронь']:
        await callback.message.edit_text(f"❌ Роль '{html.escape(role_to_free)}' уже свободна.", parse_mode="HTML")
        await state.clear()
        return
    success = update_role_status(role_to_free, 'свободна', None, None, "")
    if success:
        if has_pending_request:
            requests = load_requests()
            new_requests = [r for r in requests if not (r.get('user_id') == user_id and r.get('status') == 'pending')]
            if len(new_requests) < len(requests):
                save_requests(new_requests)
                logger.info(f"🗑️ Удалена заявка пользователя {user_id} при освобождении роли")
        try:
            await callback.bot.set_chat_member_tag(chat_id=GENERAL_CHAT_ID, user_id=user_id, tag="")
            logger.info(f"🏷️ Удалён тег у пользователя {user_id}")
        except Exception as e:
            logger.error(f"❌ Не удалось удалить тег: {e}")
        await callback.message.edit_text(
            f"✅ <b>Роль успешно освобождена!</b>\n\n"
            f"📌 Освобожденная роль: <b>{html.escape(role_to_free)}</b>\n"
            f"📊 Статус до освобождения: <b>{'забронирована' if status == 'бронь' else 'занята'}</b>\n"
            f"{'🗑️ Активная заявка удалена.\n' if has_pending_request else ''}\n"
            f"Теперь вы можете подать новую заявку через /apply.",
            parse_mode="HTML"
        )
        if callback.message.chat.id == GENERAL_CHAT_ID:
            await callback.message.answer("🔙 Выберите действие:")
        else:
            await callback.message.answer("🔙 Выберите действие:",
                                          reply_markup=get_main_keyboard(user_id, callback.message.chat.id))
        logger.info(f"👤 Пользователь {user_id} освободил роль {role_to_free} (была {status})")
    else:
        await callback.message.edit_text("❌ Ошибка при освобождении роли. Попробуйте позже.")
    await state.clear()


@router.callback_query(F.data == "free_confirm_no")
async def free_confirm_no(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    user_id = callback.from_user.id
    await callback.message.edit_text("🔒 Освобождение роли отменено.", parse_mode="HTML")
    if callback.message.chat.id == GENERAL_CHAT_ID:
        await callback.message.answer("🔙 Выберите действие:")
    else:
        await callback.message.answer("🔙 Выберите действие:",
                                      reply_markup=get_main_keyboard(user_id, callback.message.chat.id))
    logger.info(f"👤 Пользователь {user_id} отменил освобождение роли")


# ============================================================
# ЗАЯВКИ (ОТМЕНА)
# ============================================================

@router.message(Command('cancel_request'))
async def cmd_cancel_request(message: Message):
    user = message.from_user
    if user is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    request = get_request_by_user_id(user.id)
    if not request:
        await message.answer("❌ У вас нет активных заявок.")
        return
    if request.get('status') != 'pending':
        await message.answer(f"ℹ️ Ваша заявка уже {request.get('status')}.")
        return
    role_name = request.get('role')
    if not role_name:
        await message.answer("❌ Ошибка: роль не указана в заявке.")
        return
    role_data = get_role_by_name(role_name)
    if role_data and role_data.get('status') == 'бронь' and role_data.get('owner_id') == user.id:
        update_role_status(role_name, 'свободна', None, None, "")
        logger.info(f"🔓 Снята бронь с роли {role_name} для пользователя {user.id}")
    else:
        logger.info(f"ℹ️ Роль {role_name} уже не в брони или не принадлежит пользователю")
    requests = load_requests()
    new_requests = [r for r in requests if not (r.get('user_id') == user.id and r.get('status') == 'pending')]
    if len(new_requests) < len(requests):
        save_requests(new_requests)
        text = f"✅ Заявка на роль '<b>{html.escape(role_name)}</b>' отменена.\n\nРоль освобождена и снова доступна для других пользователей."
        if message.chat.id == GENERAL_CHAT_ID:
            await message.answer(text, parse_mode="HTML")
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user.id, message.chat.id))
        logger.info(f"👤 Пользователь {user.id} отменил заявку на роль {role_name}")
    else:
        await message.answer("❌ Ошибка при отмене заявки. Попробуйте позже.")


# ============================================================
# РЕГИСТРАЦИЯ
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


@router.message(Command('unregister_admin'))
async def cmd_unregister_admin(message: Message):
    user = message.from_user
    if user is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not is_admin(user.id):
        await message.answer("⛔ Вы не администратор.")
        return
    if is_owner(user.id):
        await message.answer("⛔ Владелец не может удалить себя. Передайте права другому.")
        return
    admins = load_admins()
    new_admins = [a for a in admins if a['id'] != user.id]
    save_admins(new_admins)
    text = "✅ Вы удалены из списка администраторов."
    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text)
    else:
        await message.answer(text, reply_markup=get_main_keyboard(user.id, message.chat.id))
    logger.info(f"🔄 АДМИН {user.full_name} удалил себя")


@router.message(Command('unregister_user'))
async def cmd_unregister_user(message: Message):
    user = message.from_user
    if user is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not remove_user(user.id):
        await message.answer("⛔ Вы не зарегистрированы как участник.")
        return
    text = "✅ Вы удалены из списка участников."
    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text)
    else:
        await message.answer(text, reply_markup=get_main_keyboard(user.id, message.chat.id))
    logger.info(f"🔄 УЧАСТНИК {user.full_name} удалил себя")


# ============================================================
# АДМИНИСТРИРОВАНИЕ
# ============================================================

@router.message(Command('admins'))
async def cmd_admins(message: Message, state: FSMContext):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not await check_admin_state(message, state):
        return
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
async def cmd_users(message: Message, state: FSMContext):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not await check_admin_state(message, state):
        return
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
        text += f"• {html.escape(u['full_name'])} ({username}) – {role_name} ({character}) (ID: <code>{u['id']}</code>)\n"
    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))


@router.message(Command('adduser'))
async def cmd_adduser(message: Message, state: FSMContext):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not await check_admin_state(message, state):
        return
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
async def cmd_removeuser(message: Message, state: FSMContext):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not await check_admin_state(message, state):
        return
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
async def cmd_resetuser(message: Message, state: FSMContext):
    admin_id = safe_user_id(message)
    if admin_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not await check_admin_state(message, state):
        return
    if not is_admin(admin_id):
        await message.answer("⛔ Доступ запрещён. Только для администраторов.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /resetuser [ID]\n📌 Пример: /resetuser 123456789")
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
        logger.info(f"🏷️ Удалён тег у пользователя {target_id} через resetuser")
    except Exception as e:
        logger.error(f"❌ Не удалось удалить тег: {e}")
    freed_role = free_role(target_id)
    removed = remove_user(target_id)
    if freed_role or removed:
        response = "✅ Пользователь сброшен:\n"
        if freed_role:
            response += f"📌 Освобождена роль: {html.escape(freed_role)}\n"
        if removed:
            response += f"👤 Удалён из списка участников.\n"
        if message.chat.id == GENERAL_CHAT_ID:
            await message.answer(response)
        else:
            await message.answer(response, reply_markup=get_main_keyboard(admin_id, message.chat.id))
        logger.info(f"Админ {admin_id} сбросил пользователя {target_id}")
    else:
        await message.answer(f"ℹ️ Пользователь {target_id} не найден в списке участников и не имеет роли.")


@router.message(Command('refresh'))
async def cmd_refresh(message: Message, state: FSMContext):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not await check_admin_state(message, state):
        return
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
async def cmd_find(message: Message, state: FSMContext):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not await check_admin_state(message, state):
        return
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /find [ID]\n📌 Пример: /find 123456789")
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
        text += f"👤 Пользователь не найден в списке участников.\n"
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
async def cmd_finduser(message: Message, state: FSMContext):
    admin_id = safe_user_id(message)
    if admin_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not await check_admin_state(message, state):
        return
    if not is_admin(admin_id):
        await message.answer("⛔ Доступ запрещён.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /finduser [юзернейм]\n📌 Пример: /finduser Sedrik_loez")
        return
    username = parts[1].replace('@', '').strip()
    users = load_users()
    found = None
    for u in users:
        if u.get('username') and u['username'].lower() == username.lower():
            found = u
            break
    if not found:
        await message.answer(f"❌ Пользователь @{username} не найден в списке участников.")
        return
    safe_name = html.escape(found['full_name'])
    text = f"🔍 <b>Информация о пользователе</b>\n\n"
    text += f"👤 Имя: {safe_name}\n"
    text += f"🔖 Юзернейм: @{found['username']}\n"
    text += f"🆔 ID: <code>{found['id']}</code>\n"
    text += f"🔗 <a href='tg://user?id={found['id']}'>Открыть профиль</a>\n"
    role = get_user_role_from_roles(found['id'])
    if role:
        text += f"📌 Текущая роль: {html.escape(role)}\n"
    else:
        text += f"📌 Роль: не занята\n"
    request = get_request_by_user_id(found['id'])
    if request and request['status'] == 'pending':
        text += f"\n📝 <b>Есть активная заявка!</b>\n"
        text += f"📌 Роль в заявке: {html.escape(request['role'])}\n"
        text += f"🏷️ Должность: {html.escape(request['position'])}\n"
    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(admin_id, message.chat.id))


@router.message(Command('requests'))
async def cmd_requests(message: Message, state: FSMContext):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not await check_admin_state(message, state):
        return
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return
    pending = get_pending_requests()
    if not pending:
        await message.answer("📭 Нет заявок в ожидании.")
        return
    buttons = []
    for req in pending:
        safe_name = html.escape(req['full_name'])
        safe_role = html.escape(req['role'])
        button_text = f"{safe_name} (@{req['username']}) - {safe_role}"
        callback_data = f"view_req_{req['user_id']}"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])
    buttons.append([InlineKeyboardButton(text="🔄 Обновить список", callback_data="refresh_requests")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(
        f"📝 <b>Заявки в ожидании ({len(pending)})</b>\n\n"
        f"Нажмите на заявку, чтобы управлять ею:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def cmd_requests_impl(message: Message, user_id: int):
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return
    pending = get_pending_requests()
    if not pending:
        await message.answer("📭 Нет заявок в ожидании.")
        return
    buttons = []
    for req in pending:
        safe_name = html.escape(req['full_name'])
        safe_role = html.escape(req['role'])
        button_text = f"{safe_name} (@{req['username']}) - {safe_role}"
        callback_data = f"view_req_{req['user_id']}"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])
    buttons.append([InlineKeyboardButton(text="🔄 Обновить список", callback_data="refresh_requests")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(
        f"📝 <b>Заявки в ожидании ({len(pending)})</b>\n\n"
        f"Нажмите на заявку, чтобы управлять ею:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "refresh_requests")
async def refresh_requests(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.message.edit_text("⛔ Доступ запрещён.")
        return
    await callback.message.delete()
    await cmd_requests_impl(callback.message, user_id)


@router.callback_query(F.data == "back_to_requests")
async def back_to_requests(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.message.edit_text("⛔ Доступ запрещён.")
        return
    await callback.message.delete()
    await cmd_requests_impl(callback.message, user_id)


@router.callback_query(F.data.startswith("view_req_"))
async def view_request(callback: CallbackQuery):
    await callback.answer()
    try:
        parts = callback.data.split("_")
        if len(parts) < 3:
            await callback.answer("❌ Неверный формат")
            return
        user_id = int(parts[2])
    except (IndexError, ValueError) as e:
        logger.error(f"Ошибка парсинга callback: {e}")
        await callback.answer("❌ Ошибка")
        return
    request = get_request_by_user_id(user_id)
    if not request or request.get('status') != 'pending':
        await callback.message.edit_text(
            "❌ Заявка уже обработана или не существует.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_requests")]
            ])
        )
        return
    safe_name = html.escape(request['full_name'])
    safe_role = html.escape(request['role'])
    safe_position = html.escape(request['position'])
    text = (
        f"📝 <b>Заявка</b>\n\n"
        f"👤 <b>Пользователь:</b> {safe_name}\n"
        f"🔖 <b>Юзернейм:</b> @{request['username'] if request['username'] else 'не указан'}\n"
        f"🆔 <b>ID:</b> <code>{request['user_id']}</code>\n"
        f"📌 <b>Роль:</b> {safe_role}\n"
        f"🏷️ <b>Должность:</b> {safe_position}\n"
        f"📊 <b>Статус:</b> ⏳ Ожидает рассмотрения"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_req_{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_req_{user_id}")
        ],
        [InlineKeyboardButton(text="🔙 Назад к списку", callback_data="back_to_requests")]
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith("approve_req_"))
async def approve_request_button(callback: CallbackQuery):
    await callback.answer()
    admin_id = callback.from_user.id
    if not is_admin(admin_id):
        await callback.message.edit_text("⛔ Доступ запрещён.")
        return
    try:
        parts = callback.data.split("_")
        if len(parts) < 3:
            await callback.answer("❌ Неверный формат")
            return
        user_id = int(parts[2])
    except (IndexError, ValueError) as e:
        logger.error(f"Ошибка парсинга callback: {e}")
        await callback.answer("❌ Ошибка")
        return
    request = get_request_by_user_id(user_id)
    if not request or request['status'] != 'pending':
        await callback.message.edit_text(
            "❌ Заявка уже обработана.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_requests")]
            ])
        )
        return
    if approve_request(user_id):
        update_role_status(request['role'], 'занята', user_id, request['username'])
        try:
            await callback.bot.set_chat_member_tag(chat_id=GENERAL_CHAT_ID, user_id=user_id, tag=request['role'])
            logger.info(f"🏷️ Назначен тег '{request['role']}' для пользователя {user_id}")
        except Exception as e:
            logger.error(f"❌ Не удалось назначить тег: {e}")
        user_message = (
            f"✅ <b>Ваша заявка одобрена!</b>\n\n"
            f"📌 Роль: <b>{html.escape(request['role'])}</b>\n"
            f"📅 Дата вступления: <b>{datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}</b>\n\n"
            f"🔗 <b>Ссылка на чат:</b>\n"
            f"👉 <a href='{CHAT_INVITE_LINK}'>Присоединиться</a>\n\n"
        )
        if request['position'] in ['Админ', 'Модер']:
            user_message += (
                f"🔗 <b>Ссылки на чаты для администраторов:</b>\n"
                f"• Админ группа: <a href='{ADMIN_LINK}'>Ссылка</a>\n"
                f"• Принятие нью группа: <a href='{MODERATOR_LINK}'>Ссылка</a>\n\n"
            )
        user_message += f"🎉 Добро пожаловать!"
        try:
            await callback.bot.send_message(chat_id=user_id, text=user_message, parse_mode="HTML",
                                            disable_web_page_preview=False)
        except Exception as e:
            logger.error(f"❌ Не удалось уведомить пользователя {user_id}: {e}")
            await callback.message.answer(f"⚠️ Заявка одобрена, но не удалось уведомить пользователя.")
        safe_name = html.escape(request['full_name'])
        safe_role = html.escape(request['role'])
        safe_position = html.escape(request['position'])
        await callback.message.edit_text(
            f"✅ <b>Заявка одобрена!</b>\n\n"
            f"👤 Пользователь: {safe_name}\n"
            f"📌 Роль: {safe_role}\n"
            f"📌 Должность: {safe_position}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 К списку заявок", callback_data="back_to_requests")]
            ])
        )
        logger.info(f"✅ Админ {admin_id} одобрил заявку {user_id}")
    else:
        await callback.message.edit_text(
            "❌ Ошибка при одобрении заявки.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_requests")]
            ])
        )


@router.callback_query(F.data.startswith("reject_req_"))
async def reject_request_button(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    admin_id = callback.from_user.id
    if not is_admin(admin_id):
        await callback.message.edit_text("⛔ Доступ запрещён.")
        return
    try:
        parts = callback.data.split("_")
        if len(parts) < 3:
            await callback.answer("❌ Неверный формат")
            return
        user_id = int(parts[2])
    except (IndexError, ValueError) as e:
        logger.error(f"Ошибка парсинга callback: {e}")
        await callback.answer("❌ Ошибка")
        return
    request = get_request_by_user_id(user_id)
    if not request or request['status'] != 'pending':
        await callback.message.edit_text(
            "❌ Заявка уже обработана.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_requests")]
            ])
        )
        return
    await state.update_data(target_user_id=user_id, role=request['role'], position=request['position'],
                            request_data=request)
    await state.set_state(RejectReason.waiting_for_reason)
    safe_name = html.escape(request['full_name'])
    safe_role = html.escape(request['role'])
    safe_position = html.escape(request['position'])
    await callback.message.edit_text(
        f"📝 <b>Введите причину отклонения</b>\n\n"
        f"👤 Пользователь: {safe_name}\n"
        f"📌 Роль: {safe_role}\n"
        f"📌 Должность: {safe_position}\n\n"
        f"✏️ Напишите причину в следующем сообщении:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Отменить", callback_data=f"cancel_reject_{user_id}")]
        ])
    )
    logger.info(f"Админ {admin_id} начал отклонение заявки {user_id}")


@router.message(RejectReason.waiting_for_reason)
async def reject_with_reason(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    if not is_admin(admin_id):
        await message.answer("⛔ Доступ запрещён.")
        await state.clear()
        return
    data = await state.get_data()
    user_id = data.get('target_user_id')
    role = data.get('role', 'неизвестная')
    position = data.get('position', 'неизвестная')
    request = data.get('request_data')
    if not user_id or not request:
        await message.answer("❌ Ошибка: данные заявки не найдены.")
        await state.clear()
        return
    current_request = get_request_by_user_id(user_id)
    if not current_request or current_request.get('status') != 'pending':
        await message.answer("❌ Заявка уже обработана.")
        await state.clear()
        return
    reason = message.text
    safe_reason = html.escape(reason)
    safe_role = html.escape(role)
    safe_position = html.escape(position)
    try:
        await message.bot.send_message(
            chat_id=user_id,
            text=f"❌ <b>Ваша заявка отклонена.</b>\n\n📌 Роль: {safe_role}\n📌 Должность: {safe_position}\n📝 <b>Причина:</b> {safe_reason}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"❌ Не удалось уведомить пользователя {user_id}: {e}")
        await message.answer(f"⚠️ Не удалось уведомить пользователя, но заявка будет отклонена.")
    if reject_request(user_id):
        safe_name = html.escape(request.get('full_name', 'Пользователь'))
        text = f"✅ Заявка отклонена!\n\n👤 Пользователь: {safe_name}\n📌 Роль: {safe_role}\n📝 Причина: {reason}"
        if message.chat.id == GENERAL_CHAT_ID:
            await message.answer(text, parse_mode="HTML")
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(admin_id, message.chat.id))
        logger.info(f"Админ {admin_id} отклонил заявку {user_id} с причиной: {reason}")
    else:
        await message.answer("❌ Ошибка при отклонении заявки.")
    await state.clear()


@router.callback_query(F.data.startswith("cancel_reject_"))
async def cancel_reject(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    admin_id = callback.from_user.id
    if not is_admin(admin_id):
        await callback.message.edit_text("⛔ Доступ запрещён.")
        return
    try:
        parts = callback.data.split("_")
        if len(parts) < 3:
            await callback.answer("❌ Неверный формат")
            return
        user_id = int(parts[2])
    except (IndexError, ValueError) as e:
        logger.error(f"Ошибка парсинга callback: {e}")
        await callback.answer("❌ Ошибка")
        return
    request = get_request_by_user_id(user_id)
    if not request or request['status'] != 'pending':
        await callback.message.edit_text(
            "❌ Заявка уже обработана.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_requests")]
            ])
        )
        await state.clear()
        return
    safe_name = html.escape(request['full_name'])
    safe_role = html.escape(request['role'])
    safe_position = html.escape(request['position'])
    text = (
        f"📝 <b>Заявка</b>\n\n"
        f"👤 <b>Пользователь:</b> {safe_name}\n"
        f"🔖 <b>Юзернейм:</b> @{request['username'] if request['username'] else 'не указан'}\n"
        f"🆔 <b>ID:</b> <code>{request['user_id']}</code>\n"
        f"📌 <b>Роль:</b> {safe_role}\n"
        f"🏷️ <b>Должность:</b> {safe_position}\n"
        f"📊 <b>Статус:</b> ⏳ Ожидает рассмотрения"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_req_{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_req_{user_id}")
        ],
        [InlineKeyboardButton(text="🔙 Назад к списку", callback_data="back_to_requests")]
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await state.clear()
    logger.info(f"Админ {admin_id} отменил отклонение заявки {user_id}")


@router.message(Command('reject'))
async def cmd_reject(message: Message, state: FSMContext):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not await check_admin_state(message, state):
        return
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /reject [ID] [причина]\n📌 Пример: /reject 123456789 Не подходит по роли")
        return
    try:
        target_id = int(parts[1])
        reason = parts[2] if len(parts) > 2 else "Причина не указана"
        safe_reason = html.escape(reason)
    except ValueError:
        await message.answer("❌ Неверный ID. Введите число.")
        return
    request = get_request_by_user_id(target_id)
    if not request:
        await message.answer(f"❌ Заявка от пользователя {target_id} не найдена.")
        return
    if request['status'] != 'pending':
        await message.answer(f"ℹ️ Заявка уже {request['status']}.")
        return
    try:
        await message.bot.send_message(chat_id=target_id,
                                       text=f"❌ <b>Ваша заявка отклонена.</b>\n\n📌 Роль: {html.escape(request['role'])}\n📌 Должность: {html.escape(request['position'])}\n📝 <b>Причина:</b> {safe_reason}",
                                       parse_mode="HTML")
    except Exception as e:
        logger.error(f"❌ Не удалось уведомить пользователя {target_id}: {e}")
    if reject_request(target_id):
        safe_name = html.escape(request['full_name'])
        safe_role = html.escape(request['role'])
        text = f"❌ Заявка от {safe_name} (@{request['username']}) отклонена.\n📌 Роль: {safe_role} освобождена.\n📝 Причина: {reason}"
        if message.chat.id == GENERAL_CHAT_ID:
            await message.answer(text, parse_mode="HTML")
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))
        logger.info(f"Админ {user_id} отклонил заявку {target_id} с причиной: {reason}")
    else:
        await message.answer("❌ Ошибка при отклонении заявки.")


@router.message(Command('approve'))
async def cmd_approve(message: Message, state: FSMContext):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not await check_admin_state(message, state):
        return
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /approve [ID]\n\n📌 Пример: /approve 123456789")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID. Введите число.")
        return
    request = get_request_by_user_id(target_id)
    if not request:
        await message.answer(f"❌ Заявка от пользователя {target_id} не найдена.")
        return
    if request['status'] != 'pending':
        await message.answer(f"ℹ️ Заявка уже {request['status']}.")
        return
    if approve_request(target_id):
        update_role_status(request['role'], 'занята', target_id, request['username'])
        try:
            await message.bot.set_chat_member_tag(chat_id=GENERAL_CHAT_ID, user_id=target_id, tag=request['role'])
            logger.info(f"🏷️ Назначен тег '{request['role']}' для пользователя {target_id}")
        except Exception as e:
            logger.error(f"❌ Не удалось назначить тег: {e}")
        user_message = (
            f"✅ <b>Ваша заявка одобрена!</b>\n\n"
            f"📌 Роль: <b>{html.escape(request['role'])}</b>\n"
            f"📅 Дата вступления: <b>{datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}</b>\n\n"
            f"🔗 <b>Ссылка на чат:</b>\n"
            f"👉 <a href='{CHAT_INVITE_LINK}'>Присоединиться</a>\n\n"
        )
        if request['position'] in ['Админ', 'Модер']:
            user_message += (
                f"🔗 <b>Ссылки на чаты для администраторов:</b>\n"
                f"• Админ группа: <a href='{ADMIN_LINK}'>Ссылка</a>\n"
                f"• Принятие нью группа: <a href='{MODERATOR_LINK}'>Ссылка</a>\n\n"
            )
        user_message += f"🎉 Добро пожаловать!"
        try:
            await message.bot.send_message(chat_id=target_id, text=user_message, parse_mode="HTML",
                                           disable_web_page_preview=False)
        except Exception as e:
            logger.error(f"❌ Не удалось уведомить пользователя {target_id}: {e}")
            await message.answer(f"⚠️ Заявка одобрена, но не удалось уведомить пользователя.")
        safe_name = html.escape(request['full_name'])
        safe_role = html.escape(request['role'])
        safe_position = html.escape(request['position'])
        text = f"✅ Заявка от {safe_name} (@{request['username']}) одобрена!\n📌 Роль: {safe_role}\n📌 Должность: {safe_position}"
        if message.chat.id == GENERAL_CHAT_ID:
            await message.answer(text, parse_mode="HTML")
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))
        logger.info(f"✅ Админ {user_id} одобрил заявку {target_id}")
    else:
        await message.answer("❌ Ошибка при одобрении заявки.")


# ============================================================
# РЕСТЫ 2.0 (ЗАЯВКИ ЧЕРЕЗ ИНЛАЙН-МЕНЮ)
# ============================================================

@router.message(Command('rest'))
async def cmd_rest(message: Message, state: FSMContext):
    user_id = message.from_user.id

    # Рест можно подавать только в личке или админ-чате
    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("❌ Эта команда доступна только в личных сообщениях или админ-чате.")
        return

    user_role = get_user_role_from_roles(user_id)
    if not user_role:
        await message.answer("❌ У вас нет занятой роли. Рест можно взять только для своей роли.")
        return

    role_data = get_role_by_name(user_role)
    if not role_data:
        await message.answer("❌ Ошибка: роль не найдена.")
        return

    if role_data.get('status') == 'рест':
        current_until = role_data.get('extra', 'неизвестная дата')
        await message.answer(
            f"⚠️ У вас уже есть активный рест до {current_until}. Новая заявка обновит дату и причину.")

    await state.update_data(rest_role=user_role, rest_user_id=user_id)
    await state.set_state(RestRequestStates.waiting_for_date)

    now = datetime.datetime.now()
    keyboard = generate_calendar_keyboard(now.year, now.month)
    await message.answer("📅 Выберите дату окончания реста:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("rest_cal_"))
async def handle_rest_calendar(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = callback.data.split("_")

    # Проверка длины, чтобы избежать ошибок
    if len(data) < 3:
        return

    try:
        if data[1] == "prev":
            year, month = int(data[2]), int(data[3])
            if month == 1:
                year -= 1
                month = 12
            else:
                month -= 1
            keyboard = generate_calendar_keyboard(year, month)
            await callback.message.edit_reply_markup(reply_markup=keyboard)

        elif data[1] == "next":
            year, month = int(data[2]), int(data[3])
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
            keyboard = generate_calendar_keyboard(year, month)
            await callback.message.edit_reply_markup(reply_markup=keyboard)

        elif data[1] == "ignore":
            pass

        else:
            # Выбор даты: rest_cal_YYYY_MM_DD
            # data[0]="rest", data[1]="cal", data[2]=YYYY, data[3]=MM, data[4]=DD
            if len(data) < 5:
                logger.error(f"Неверный формат даты в callback: {callback.data}")
                return

            year, month, day = int(data[2]), int(data[3]), int(data[4])
            selected_date = datetime.date(year, month, day)

            await state.update_data(rest_date=selected_date.isoformat())
            await state.set_state(RestRequestStates.waiting_for_reason)
            await callback.message.edit_text(
                f"📅 Вы выбрали дату: **{selected_date.strftime('%d.%m.%Y')}**\n\n"
                f"✏️ Теперь введите **причину** реста (обязательно):",
                parse_mode="Markdown"
            )
    except (ValueError, IndexError) as e:
        logger.error(f"Ошибка при обработке календаря: {e}")
        await callback.answer("❌ Ошибка выбора даты", show_alert=True)


@router.callback_query(F.data == "cancel_rest_request")
async def cancel_rest_request(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("❌ Заявка на рест отменена.")


@router.message(RestRequestStates.waiting_for_reason)
async def process_rest_reason(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    role_name = data.get('rest_role')
    until_date = data.get('rest_date')
    reason = message.text

    if not role_name or not until_date:
        await message.answer("❌ Ошибка данных. Попробуйте снова через /rest")
        await state.clear()
        return

    requests = load_rest_requests()

    new_request = {
        "id": len(requests) + 1,
        "user_id": user_id,
        "role_name": role_name,
        "until_date": until_date,
        "reason": reason,
        "status": "pending",
        "timestamp": time.time()
    }
    requests.append(new_request)
    save_rest_requests(requests)

    await state.clear()

    safe_name = html.escape(safe_user_name(message))
    safe_username = safe_username(message)

    admin_text = (
        f"📝 <b>Заявка на рест</b>\n\n"
        f"👤 Пользователь: {safe_name} ({safe_username})\n"
        f"🎭 Роль: {html.escape(role_name)}\n"
        f"📅 Дата: {until_date}\n"
        f"📝 Причина: {html.escape(reason)}\n\n"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_rest_{new_request['id']}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_rest_{new_request['id']}")
        ]
    ])

    try:
        await message.bot.send_message(chat_id=ADMIN_GROUP_ID, text=admin_text, parse_mode="HTML",
                                       reply_markup=keyboard)
        await message.answer("✅ Ваша заявка на рест отправлена администрации.")
        logger.info(f"📝 Пользователь {user_id} подал заявку на рест для роли {role_name} до {until_date}")
    except Exception as e:
        logger.error(f"❌ Не удалось отправить заявку на рест в админ-группу: {e}")
        await message.answer("❌ Произошла ошибка при отправке заявки. Попробуйте позже.")


@router.callback_query(F.data.startswith("approve_rest_"))
async def approve_rest_request(callback: CallbackQuery):
    await callback.answer()
    admin_id = callback.from_user.id
    if not is_admin(admin_id):
        await callback.message.edit_text("⛔ Доступ запрещён.")
        return

    req_id = int(callback.data.split("_")[2])
    requests = load_rest_requests()

    target_req = None
    for r in requests:
        if r['id'] == req_id:
            target_req = r
            break

    if not target_req or target_req['status'] != 'pending':
        await callback.message.edit_text("❌ Заявка уже обработана или не найдена.")
        return

    target_req['status'] = 'approved'
    save_rest_requests(requests)

    role_name = target_req['role_name']
    until_date = target_req['until_date']
    user_id = target_req['user_id']

    success = set_rest(role_name, until_date)

    if success:
        try:
            await callback.bot.send_message(
                chat_id=user_id,
                text=f"✅ Ваш рест на роль <b>{html.escape(role_name)}</b> одобрен до <b>{until_date}</b>.",
                parse_mode="HTML"
            )
        except Exception:
            pass

        await callback.message.edit_text(f"✅ Рест для роли <b>{html.escape(role_name)}</b> установлен до {until_date}.",
                                         parse_mode="HTML")
        logger.info(f"✅ Админ {admin_id} одобрил рест для роли {role_name} до {until_date}")
    else:
        await callback.message.edit_text("❌ Ошибка при установке реста.")


@router.callback_query(F.data.startswith("reject_rest_"))
async def reject_rest_request(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    admin_id = callback.from_user.id
    if not is_admin(admin_id):
        await callback.message.edit_text("⛔ Доступ запрещён.")
        return

    req_id = int(callback.data.split("_")[2])
    requests = load_rest_requests()

    target_req = None
    for r in requests:
        if r['id'] == req_id:
            target_req = r
            break

    if not target_req or target_req['status'] != 'pending':
        await callback.message.edit_text("❌ Заявка уже обработана или не найдена.")
        return

    await state.update_data(reject_rest_id=req_id, reject_user_id=target_req['user_id'],
                            reject_role=target_req['role_name'])
    await state.set_state(RejectReason.waiting_for_reason)

    await callback.message.edit_text(
        f"📝 <b>Отклонение заявки на рест</b>\n\n"
        f"👤 Пользователь: ID {target_req['user_id']}\n"
        f"🎭 Роль: {html.escape(target_req['role_name'])}\n\n"
        f"✏️ Введите причину отклонения (или нажмите 'Пропустить' ниже):",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить причину", callback_data=f"skip_rest_reject_{req_id}")]
        ])
    )


@router.callback_query(F.data.startswith("skip_rest_reject_"))
async def skip_rest_reject(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    req_id = int(callback.data.split("_")[3])
    await process_rest_rejection_final(callback.message, state, req_id, "Причина не указана")


async def process_rest_rejection_final(message_or_callback, state, req_id, reason):
    requests = load_rest_requests()

    target_req = None
    for r in requests:
        if r['id'] == req_id:
            target_req = r
            break

    if not target_req or target_req['status'] != 'pending':
        if isinstance(message_or_callback, Message):
            await message_or_callback.answer("❌ Заявка уже обработана.")
        else:
            await message_or_callback.message.edit_text("❌ Заявка уже обработана.")
        await state.clear()
        return

    target_req['status'] = 'rejected'
    save_rest_requests(requests)

    user_id = target_req['user_id']
    role_name = target_req['role_name']

    try:
        bot = message_or_callback.bot if hasattr(message_or_callback, 'bot') else message_or_callback
        await bot.send_message(
            chat_id=user_id,
            text=f"❌ Ваша заявка на рест для роли <b>{html.escape(role_name)}</b> отклонена.\n📝 Причина: {html.escape(reason)}",
            parse_mode="HTML"
        )
    except Exception:
        pass

    if isinstance(message_or_callback, Message):
        await message_or_callback.answer(f"✅ Заявка на рест отклонена. Причина: {reason}")
    else:
        await message_or_callback.message.edit_text(f"✅ Заявка на рест отклонена. Причина: {reason}")

    logger.info(f"❌ Админ отклонил рест для роли {role_name}. Причина: {reason}")
    await state.clear()


@router.message(Command('unrest'))
async def cmd_unrest(message: Message, state: FSMContext):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not await check_admin_state(message, state):
        return
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён. Только для администраторов.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /unrest [роль]\n📌 Пример: /unrest Глен")
        return
    role_name = parts[1]
    role = get_role_by_name(role_name)
    if role is None:
        await message.answer(f"❌ Роль '{html.escape(role_name)}' не найдена.")
        return
    if role['status'] != 'рест':
        await message.answer(f"❌ Роль '{html.escape(role_name)}' не в ресте.")
        return
    success = clear_rest(role_name)
    if success:
        owner_id = role['owner_id']
        if owner_id:
            try:
                await message.bot.send_message(chat_id=owner_id,
                                               text=f"✅ Рест с роли '{html.escape(role_name)}' снят. Вы снова активны!")
            except Exception:
                pass
        text = f"✅ Рест с роли '{html.escape(role_name)}' снят."
        if message.chat.id == GENERAL_CHAT_ID:
            await message.answer(text)
        else:
            await message.answer(text, reply_markup=get_main_keyboard(user_id, message.chat.id))
        logger.info(f"Админ {user_id} снял рест с роли {role_name}")
    else:
        await message.answer("❌ Ошибка при снятии реста.")


@router.message(Command('restlist'))
async def cmd_restlist(message: Message):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return

    requests = load_rest_requests()
    today = datetime.date.today()
    one_week_ago = today - datetime.timedelta(days=7)

    active = []
    past = []

    for r in requests:
        if r['status'] == 'approved':
            try:
                until_date = datetime.datetime.strptime(r['until_date'], '%Y-%m-%d').date()
                if until_date >= today:
                    active.append(r)
                elif until_date >= one_week_ago:
                    past.append(r)
            except Exception:
                pass

    text = "📋 <b>Список рестов:</b>\n\n"

    if active:
        text += "🔵 <b>Активные:</b>\n"
        for r in active:
            role = get_role_by_name(r['role_name'])
            owner_name = role.get('owner_username', 'Неизвестно') if role else 'Неизвестно'
            until_date = datetime.datetime.strptime(r['until_date'], '%Y-%m-%d').date()
            days_left = (until_date - today).days
            text += f"• {html.escape(r['role_name'])} — владелец: @{owner_name} — до {r['until_date']} (осталось {days_left} дн.)\n"
        text += "\n"
    else:
        text += "🔵 Активных рестов нет.\n\n"

    if past:
        text += "⚫ <b>Прошедшие (за неделю):</b>\n"
        for r in past:
            role = get_role_by_name(r['role_name'])
            owner_name = role.get('owner_username', 'Неизвестно') if role else 'Неизвестно'
            text += f"• {html.escape(r['role_name'])} — владелец: @{owner_name} — истёк {r['until_date']}\n"
    else:
        text += "⚫ Прошедших рестов за неделю нет."

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))


@router.message(Command('restextend'))
async def cmd_restextend(message: Message, state: FSMContext):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not await check_admin_state(message, state):
        return
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён. Только для администраторов.")
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("❌ Используйте: /restextend [роль] [дд.мм.гггг]\n📌 Пример: /restextend Глен 20.07.2026")
        return
    role_name = parts[1]
    date_str = parts[2]
    role = get_role_by_name(role_name)
    if role is None:
        await message.answer(f"❌ Роль '{html.escape(role_name)}' не найдена.")
        return
    if role['status'] != 'рест':
        await message.answer(f"❌ Роль '{html.escape(role_name)}' не в ресте. Используйте /rest для установки.")
        return
    try:
        day, month, year = map(int, date_str.split('.'))
        if year < 100:
            year += 2000
        new_date = datetime.date(year, month, day)
        current_until_str = role.get('extra', '')
        if current_until_str:
            current_until = datetime.datetime.strptime(current_until_str, '%Y-%m-%d').date()
            if new_date <= current_until:
                await message.answer(
                    f"❌ Новая дата ({date_str}) меньше или равна текущей дате реста ({current_until_str}).")
                return
        else:
            await message.answer("❌ Не удалось определить текущую дату реста.")
            return
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте: дд.мм.гггг")
        return

    success = set_rest(role_name, new_date.isoformat())
    if success:
        owner_id = role['owner_id']
        if owner_id:
            try:
                await message.bot.send_message(chat_id=owner_id,
                                               text=f"⏳ Ваш рест для роли '{html.escape(role_name)}' продлен до {date_str}.")
            except Exception:
                pass
        text = f"✅ Рест для роли '{html.escape(role_name)}' продлен до {date_str}."
        if message.chat.id == GENERAL_CHAT_ID:
            await message.answer(text)
        else:
            await message.answer(text, reply_markup=get_main_keyboard(user_id, message.chat.id))
        logger.info(f"Админ {user_id} продлил рест для роли {role_name} до {date_str}")
    else:
        await message.answer("❌ Ошибка при продлении реста.")


# ============================================================
# АВТО-СНЯТИЕ RESTОВ (Вызывать из main.py)
# ============================================================

async def check_expired_rests(bot):
    """Проверяет и снимает истекшие ресты. Вызывать раз в сутки и в субботу в 18:00 МСК."""
    logger.info("🔄 Проверка истекших рестов...")
    roles = load_roles()
    today = datetime.date.today().isoformat()
    updated = False

    for role_name, role_data in roles.items():
        if role_data.get('status') == 'рест':
            until_date = role_data.get('extra')
            if until_date and until_date <= today:
                logger.info(f"⏰ Рест для роли {role_name} истёк ({until_date}). Снимаю.")
                clear_rest(role_name)
                owner_id = role_data.get('owner_id')
                if owner_id:
                    try:
                        await bot.send_message(chat_id=owner_id, text=f"⏳ Ваш рест для роли '{role_name}' истёк.")
                    except Exception:
                        pass
                updated = True

    if updated:
        save_roles(roles)
        logger.info("✅ Ресты обновлены.")


# ============================================================
# РАССЫЛКА
# ============================================================

@router.message(Command('broadcast'))
async def cmd_broadcast(message: Message, state: FSMContext):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not await check_admin_state(message, state):
        return
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён. Только для администраторов.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❌ Используйте: /broadcast [текст сообщения]\n\n📌 Пример: /broadcast Всем привет! Завтра встреча в 18:00")
        return
    text = parts[1]
    users = load_users()
    if not users:
        await message.answer("📭 Нет зарегистрированных участников для рассылки.")
        return
    status_msg = await message.answer(f"📤 Начинаю рассылку {len(users)} участникам...")
    success_count = 0
    fail_count = 0
    failed_users = []
    for user in users:
        try:
            await message.bot.send_message(chat_id=user['id'], text=f"📢 <b>Объявление от администрации:</b>\n\n{text}",
                                           parse_mode="HTML")
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            fail_count += 1
            failed_users.append(f"{user['id']} ({html.escape(user['full_name'])})")
            logger.error(f"❌ Не удалось отправить пользователю {user['id']}: {e}")
    report = (
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📨 Отправлено: {success_count}\n"
        f"❌ Не доставлено: {fail_count}\n"
        f"👥 Всего участников: {len(users)}"
    )
    if failed_users and len(failed_users) <= 10:
        report += f"\n\n⚠️ Не доставлено:\n" + "\n".join(failed_users[:10])
    elif failed_users:
        report += f"\n\n⚠️ Не доставлено: {len(failed_users)} пользователей"
    await status_msg.edit_text(report, parse_mode="HTML")
    logger.info(f"📢 Админ {user_id} отправил рассылку. Успешно: {success_count}, Ошибок: {fail_count}")


# ============================================================
# КОМАНДЫ ВЛАДЕЛЬЦА
# ============================================================

@router.message(Command('setrank'))
async def cmd_setrank(message: Message, state: FSMContext):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not await check_admin_state(message, state):
        return
    if not is_owner(user_id):
        await message.answer("⛔ Только владелец может назначать ранги.")
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("❌ Используйте: /setrank [ID] [ранг]\nРанг: 1-владелец, 2-админ, 3-модер")
        return
    try:
        target_id = int(parts[1])
        rank = int(parts[2])
        if rank not in (1, 2, 3):
            await message.answer("❌ Ранг должен быть 1, 2 или 3.")
            return
        if set_rank(target_id, rank):
            text = f"✅ Ранг пользователя {target_id} изменён на {rank}."
            if message.chat.id == GENERAL_CHAT_ID:
                await message.answer(text)
            else:
                await message.answer(text, reply_markup=get_main_keyboard(user_id, message.chat.id))
            logger.info(f"Владелец {user_id} изменил ранг {target_id} на {rank}")
        else:
            await message.answer(f"❌ Пользователь {target_id} не найден в списке админов.")
    except ValueError:
        await message.answer("❌ Неверный ID или ранг.")


@router.message(Command('close'))
async def cmd_close(message: Message, state: FSMContext):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not await check_admin_state(message, state):
        return
    if not is_owner(user_id):
        await message.answer("⛔ Только владелец может закрыть набор.")
        return
    global closed_mode
    closed_mode = True
    text = "🔒 Режим «набор закрыт» включён."
    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text)
    else:
        await message.answer(text, reply_markup=get_main_keyboard(user_id, message.chat.id))
    logger.info("Владелец включил режим закрытого набора")


@router.message(Command('open'))
async def cmd_open(message: Message, state: FSMContext):
    user_id = safe_user_id(message)
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not await check_admin_state(message, state):
        return
    if not is_owner(user_id):
        await message.answer("⛔ Только владелец может открыть набор.")
        return
    global closed_mode
    closed_mode = False
    text = "🔓 Режим «набор закрыт» выключен."
    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text)
    else:
        await message.answer(text, reply_markup=get_main_keyboard(user_id, message.chat.id))
    logger.info("Владелец выключил режим закрытого набора")


# ============================================================
# КНОПКИ
# ============================================================

@router.message(F.text == "📚 Помощь")
async def btn_help(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    await cmd_help(message)


@router.message(F.text == "ℹ️ О чате")
async def btn_about(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    await cmd_about(message)


@router.message(F.text == "👤 Мои данные")
async def btn_aboutme(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    await cmd_aboutme(message)


@router.message(F.text == "👥 Список админов")
async def btn_admins(message: Message, state: FSMContext):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    await cmd_admins(message, state)


@router.message(F.text == "👥 Список участников")
async def btn_users(message: Message, state: FSMContext):
    if message.chat.id == GENERAL_CHAT_ID:
        await cmd_members(message)
    else:
        await cmd_users(message, state)


@router.message(F.text == "🔒 Закрыть набор")
async def btn_close(message: Message, state: FSMContext):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    await cmd_close(message, state)


@router.message(F.text == "🔓 Открыть набор")
async def btn_open(message: Message, state: FSMContext):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    await cmd_open(message, state)


@router.message(F.text == "📢 Рассылка")
async def btn_broadcast(message: Message, state: FSMContext):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    await cmd_broadcast(message, state)


@router.message(F.text == "📝 Подать заявку")
async def btn_apply(message: Message, state: FSMContext):
    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("❌ Подача заявки недоступна во флуд-чате. Напишите боту в личные сообщения.")
        return
    from .apply_handlers import cmd_apply
    await cmd_apply(message, state)


@router.message(F.text == "🔄 Освободить роль")
async def btn_free(message: Message, state: FSMContext):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    await cmd_free(message, state)


@router.message(F.text == "❌ Отменить заявку")
async def btn_cancel_request(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    await cmd_cancel_request(message)


@router.message(F.text == "🔊 Сделать кал")
async def btn_call(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    await message.answer(
        "📢 Чтобы сделать кал, используйте команду:\n"
        "/call [текст] — позвать всех участников\n\n"
        "📌 Пример: /call Внимание! Голосование началось!\n"
        "📌 Без текста: /call — просто упоминания"
    )


# ============================================================
# ИНЛАЙН-КНОПКИ
# ============================================================

@router.callback_query(F.data == "help")
async def inline_help(callback):
    if callback.message.chat.id == GENERAL_CHAT_ID:
        return
    await callback.answer()
    await cmd_help(callback.message)
    await callback.message.delete()


@router.callback_query(F.data == "about")
async def inline_about(callback):
    if callback.message.chat.id == GENERAL_CHAT_ID:
        return
    await callback.answer()
    await cmd_about(callback.message)
    await callback.message.delete()


@router.callback_query(F.data == "aboutme")
async def inline_aboutme(callback):
    if callback.message.chat.id == GENERAL_CHAT_ID:
        return
    await callback.answer()
    await cmd_aboutme(callback.message)
    await callback.message.delete()


@router.callback_query(F.data == "admins")
async def inline_admins(callback):
    if callback.message.chat.id == GENERAL_CHAT_ID:
        return
    await callback.answer()
    await cmd_admins(callback.message)
    await callback.message.delete()


@router.callback_query(F.data == "users")
async def inline_users(callback):
    if callback.message.chat.id == GENERAL_CHAT_ID:
        return
    await callback.answer()
    await cmd_users(callback.message)
    await callback.message.delete()


@router.callback_query(F.data == "close")
async def inline_close(callback):
    if callback.message.chat.id == GENERAL_CHAT_ID:
        return
    await callback.answer()
    await cmd_close(callback.message)
    await callback.message.delete()


@router.callback_query(F.data == "open")
async def inline_open(callback):
    if callback.message.chat.id == GENERAL_CHAT_ID:
        return
    await callback.answer()
    await cmd_open(callback.message)
    await callback.message.delete()


# ============================================================
# ПЕРЕСЫЛКА (ИМПОРТ ИЗ forward)
# ============================================================

from .forward import forward_to_admin_group, reply_from_admin_group


# ============================================================
# ОБРАБОТЧИК ВСЕХ ОСТАЛЬНЫХ СООБЩЕНИЙ
# ============================================================

@router.message()
async def handle_any_message(message: Message, state: FSMContext):
    global closed_mode
    user_id = safe_user_id(message)
    if user_id is None:
        return

    current_state = await state.get_state()
    if current_state == RejectReason.waiting_for_reason:
        if message.text and not message.text.startswith('/'):
            return
        else:
            await message.answer(
                "⏳ Вы сейчас вводите причину отклонения заявки.\n"
                "Напишите причину текстом или нажмите '🔙 Отменить'."
            )
            return

    if message.text and message.text.startswith('/'):
        return

    if closed_mode and not is_admin(user_id):
        await message.answer("Извините, набор закрыт.")
        return

    logger.info(f"💬 Сообщение от {safe_user_name(message)} (ID: {user_id})")
    