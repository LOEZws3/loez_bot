# ============================================================
# ⚠️ ВАЖНОЕ ПРАВИЛО ДЛЯ КОМАНД ВО ФЛУДЕ
# ============================================================
# 
# Во флуд-чате (GENERAL_CHAT_ID) РАЗРЕШЕНЫ ТОЛЬКО:
# - /members (только количество)
# - /roles (только список, БЕЗ КНОПОК)
# - /call, /callfal (для админов)
# - /hide, /menu (управление клавиатурой)
# 
# ВСЕ ОСТАЛЬНЫЕ КОМАНДЫ — ЗАПРЕЩЕНЫ!
# Они должны отвечать: "⛔ Эта команда недоступна во флуд-чате."
# ============================================================

import html
import datetime
import logging
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardRemove

from config import GENERAL_CHAT_ID
from utils.admin_utils import get_admin_rank, is_admin
from utils.user_utils import load_users, get_users_count, get_user_by_id
from utils.requests_utils import get_request_by_user_id, get_pending_count
from utils.role_utils import (
    get_taken_roles, count_taken_roles,
    get_user_role as get_user_role_from_roles,
    get_all_seasons, get_roles_by_season, load_roles_status
)
from .keyboards import get_main_keyboard

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


# ============================================================
# ⛔ КОМАНДЫ, ЗАПРЕЩЁННЫЕ ВО ФЛУДЕ
# ============================================================

@router.message(Command('start'))
async def cmd_start(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда недоступна во флуд-чате.")
        logger.info(f"⛔ Команда /start заблокирована во флуде от {user_id}")
        return

    logger.info(f"👤 {message.from_user.full_name} нажал /start")

    request = get_request_by_user_id(user_id)
    status_text = ""
    if request:
        if request.get('status') == 'pending':
            status_text = "\n\n📌 Ваша заявка рассматривается администрацией."
        elif request.get('status') == 'approved':
            status_text = "\n\n✅ Ваша заявка одобрена!"
        elif request.get('status') == 'rejected':
            status_text = "\n\n❌ Ваша заявка отклонена. Попробуйте подать новую."

    safe_name = html.escape(message.from_user.full_name)
    text = (
        f"👋 Добро пожаловать, <b>{safe_name}</b>!\n\n"
        f"Я бот для управления ролями и заявками.\n"
        f"Если у вас есть вопросы — напишите <b>@Sedrikai_bot</b> (бот-пересыльщик), "
        f"и ближайший освободившийся администратор ответит вам, как только сможет.\n\n"
        f"📌 Используйте /help для списка команд.{status_text}"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))


@router.message(Command('help'))
async def cmd_help(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда недоступна во флуд-чате.")
        logger.info(f"⛔ Команда /help заблокирована во флуде от {user_id}")
        return

    is_admin_user = is_admin(user_id)

    help_text = (
        "📚 <b>Доступные команды</b>\n\n"
        "👤 <b>Для всех:</b>\n"
        "/start – приветствие (ТОЛЬКО В ЛС)\n"
        "/help – эта справка (ТОЛЬКО В ЛС)\n"
        "/about – информация о флуд-чате (ТОЛЬКО В ЛС)\n"
        "/aboutme – ваши данные (ТОЛЬКО В ЛС)\n"
        "/members – список участников (во флуде — только количество)\n"
        "/roles – список ролей (во флуде — БЕЗ КНОПОК)\n"
        "/apply – подать заявку (ТОЛЬКО В ЛС)\n"
        "/free – освободить роль (ТОЛЬКО В ЛС)\n"
        "/cancel_request – отменить заявку (ТОЛЬКО В ЛС)\n"
        "/unregc – отписаться от калов (ТОЛЬКО В ЛС)\n"
        "/regc – подписаться на калы (ТОЛЬКО В ЛС)\n"
        "/rest – подать заявку на рест (ТОЛЬКО В ЛС)\n"
        "/update – обновить данные (ТОЛЬКО В ЛС)\n"
        "/hide – скрыть клавиатуру\n"
        "/menu – показать клавиатуру\n"
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
            "/finduser – найти по юзернейму\n"
            "/broadcast – рассылка\n"
            "/call – сделать кал (ДОСТУПНА ВО ФЛУДЕ)\n"
            "/callfal – непропускаемый кал (ДОСТУПНА ВО ФЛУДЕ)\n"
            "/check_chats – диагностика\n"
            "/diag – диагностика (владелец)\n\n"
            "📝 <b>Заявки:</b>\n"
            "/requests – список заявок\n"
            "/approve – одобрить\n"
            "/reject – отклонить\n\n"
            "📋 <b>Списки:</b>\n"
            "/roster – полный список\n"
            "/stats – статистика по ролям\n"
            "/restlist – активные ресты\n\n"
            "⏳ <b>Рест:</b>\n"
            "/unrest – снять рест\n"
            "/restextend – продлить рест\n\n"
            "👑 <b>Владелец:</b>\n"
            "/setrank – назначить ранг\n"
            "/close /open – закрыть/открыть набор\n"
        )
    else:
        help_text += (
            "\n💬 <b>Связь с администрацией:</b>\n"
            "Если у вас есть вопросы – напишите <b>@Sedrikai_bot</b>"
        )

    await message.answer(help_text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))


@router.message(Command('about'))
async def cmd_about(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда недоступна во флуд-чате.")
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
        f"Подайте заявку через /apply в личных сообщениях с ботом."
    )

    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id), disable_web_page_preview=False)


@router.message(Command('aboutme'))
async def cmd_aboutme(message: Message):
    user = message.from_user
    if user is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда недоступна во флуд-чате.")
        return

    rank = get_admin_rank(user.id)
    rank_name = {1: "👑 Владелец", 2: "🔐 Админ", 3: "🛡️ Модератор"}.get(rank, "👤 Нет")
    character = get_user_role_from_roles(user.id) or "Не указан"

    request = get_request_by_user_id(user.id)
    status_text = " "
    if request:
        status_map = {
            'pending': '⏳ Ожидает рассмотрения',
            'approved': '✅ Одобрена',
            'rejected': '❌ Отклонена'
        }
        status_text = f"\n📝 Статус заявки: {status_map.get(request.get('status'), 'Неизвестно')} "
        if request.get('status') == 'pending':
            status_text += f"\n📌 Роль: {request.get('role', 'Не указана')} "
            status_text += f"\n📌 Должность: {request.get('position_name', request.get('position', 'Не указана'))} "

    safe_name = html.escape(user.full_name)
    safe_username = html.escape(user.username if user.username else 'не указан')

    text = (
        f"📝 <b>Ваши данные</b>\n\n"
        f"👤 Имя: <b>{safe_name}</b>\n"
        f"🔖 Юзернейм: @{safe_username}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"⭐ Ранг: {rank_name}\n"
        f"🎭 Персонаж: {character}{status_text}"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user.id, message.chat.id))


@router.message(Command('update'))
async def cmd_update(message: Message):
    user = message.from_user
    if user is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда недоступна во флуд-чате.")
        return

    user_id = user.id
    user_data = get_user_by_id(user_id)

    if user_data is None:
        await message.answer(
            "❌ Вы не зарегистрированы!\n\n"
            "📌 Чтобы зарегистрироваться, перейдите в бота:\n"
            f"👉 @REG_sf_BOT\n\n"
            "И подайте заявку через команду /apply в личных сообщениях с ботом."
        )
        return

    user_role = get_user_role_from_roles(user_id)

    if user_role:
        await message.answer(
            f"👤 <b>Ваши данные:</b>\n\n"
            f"📌 Имя: {html.escape(user_data['full_name'])}\n"
            f"🎭 Персонаж: {html.escape(user_role)}\n\n"
            f"✅ Вы зарегистрированы!\n"
            f"📌 Чтобы обновить данные, перейдите в бота:\n"
            f"👉 @REG_sf_BOT",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"👤 Вы зарегистрированы, но у вас нет роли!\n\n"
            f"📌 Чтобы получить роль, перейдите в бота:\n"
            f"👉 @REG_sf_BOT\n\n"
            f"И подайте заявку через команду /apply в личных сообщениях с ботом.",
            parse_mode="HTML"
        )


@router.message(Command('unregc'))
async def cmd_unregc(message: Message):
    user_id = message.from_user.id
    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда недоступна во флуд-чате.")
        return
    # TODO: реализовать


@router.message(Command('regc'))
async def cmd_regc(message: Message):
    user_id = message.from_user.id
    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда недоступна во флуд-чате.")
        return
    # TODO: реализовать


# ============================================================
# ⌨️ УПРАВЛЕНИЕ КЛАВИАТУРОЙ
# ============================================================

@router.message(Command('hide'))
async def cmd_hide(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    await message.answer(
        "🗑️ <b>Клавиатура скрыта!</b>\n\n"
        "Чтобы вернуть меню, отправьте /menu",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )
    logger.info(f"👤 Пользователь {user_id} скрыл клавиатуру")


@router.message(Command('menu'))
async def cmd_menu(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Во флуд-чате клавиатура недоступна.")
        return

    await message.answer(
        "⌨️ <b>Клавиатура восстановлена!</b>",
        parse_mode="HTML",
        reply_markup=get_main_keyboard(user_id, message.chat.id)
    )
    logger.info(f"👤 Пользователь {user_id} показал клавиатуру")


# ============================================================
# ✅ КОМАНДЫ, ДОСТУПНЫЕ ВО ФЛУДЕ
# ============================================================

@router.message(Command('members'))
async def cmd_members(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    users = load_users()
    if not users:
        await message.answer("📭 В списке пока нет участников.")
        return

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(f"👥 Всего участников: {len(users)}")
        return

    is_admin_user = is_admin(user_id)
    if not is_admin_user:
        await message.answer(f"👥 Всего участников: {len(users)}")
        return

    text = f"👥 <b>Список участников</b>\n"
    text += f"📅 {datetime.date.today().strftime('%d.%m.%Y')}\n"
    text += f"👥 Всего: {len(users)}\n\n"

    for u in users:
        username = f"@{u['username']}" if u['username'] else "без юзернейма"
        role_index = u.get('role', '0')
        role_name = ROLE_NAMES.get(role_index, 'Неизвестно')
        character = get_user_role_from_roles(u['id']) or "Нет роли"
        text += f"• [{role_index}] {html.escape(u['full_name'])} ({username}) – {role_name} ({character}) (ID: <code>{u['id']}</code>)\n"

    if len(text) > 4000:
        await message.answer(text[:3900], parse_mode="HTML")
        await message.answer("\n... продолжение ...\n" + text[3900:], parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))


@router.message(Command('roles'))
async def cmd_roles(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    seasons = get_all_seasons()
    if not seasons:
        await message.answer("📭 Сезоны не найдены.")
        return

    # ✅ ВО ФЛУДЕ — БЕЗ КНОПОК
    if message.chat.id == GENERAL_CHAT_ID:
        text = "📋 <b>Список ролей по сезонам</b>\n\n"
        for season in sorted(seasons):
            roles = get_roles_by_season(season)
            text += f"📂 <b>{season}</b> ({len(roles)} ролей):\n"
            for role in roles:
                role_name = role.get('name', '?')
                status = role.get('status', 'свободна')
                if status == 'свободна':
                    status_text = "🟢 свободна"
                elif status == 'бронь':
                    status_text = "🟡 забронирована"
                elif status == 'рест':
                    extra = role.get('extra', '')
                    status_text = f"🔵 рест до {extra}" if extra else "🔵 рест"
                elif status == 'ожидает':
                    status_text = "⏳ ожидает"
                else:
                    status_text = "🔴 занята"
                text += f"  • {html.escape(role_name)} — {status_text}\n"
            text += "\n"
        await message.answer(text, parse_mode="HTML")
        return

    # В ЛС — с кнопками
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

    await message.answer(
        "📋 <b>Список ролей по сезонам</b>\n\n"
        "Выберите сезон для просмотра.\n\n"
        "🟢 свободна | 🟡 забронирована | 🔴 занята | 🔵 рест | ⏳ ожидает",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.message(Command('call'))
async def cmd_call(message: Message):
    """Кал (доступен во флуде для админов)"""
    pass


@router.message(Command('callfal'))
async def cmd_callfal(message: Message):
    """Непропускаемый кал"""
    pass


# ============================================================
# INLINE CALLBACK
# ============================================================

@router.callback_query(F.data == "back_to_menu_from_roles")
async def back_to_menu_from_roles(callback: CallbackQuery):
    await callback.answer()
    if callback.message.chat.id == GENERAL_CHAT_ID:
        await callback.message.delete()
        await callback.message.answer("🔙 Вы вернулись.")
        return

    user_id = callback.from_user.id
    await callback.message.delete()
    await callback.message.answer(
        "🔙 Вы вернулись в главное меню.",
        reply_markup=get_main_keyboard(user_id, callback.message.chat.id)
    )


@router.callback_query(F.data.startswith("roles_season_"))
async def show_roles_by_season(callback: CallbackQuery):
    await callback.answer()

    if callback.message.chat.id == GENERAL_CHAT_ID:
        await callback.answer("⛔ Во флуд-чате эта функция недоступна.")
        return

    season = callback.data.replace("roles_season_", "")
    roles = get_roles_by_season(season)

    if not roles:
        await callback.message.edit_text(
            f"📭 В сезоне <b>{html.escape(season)}</b> нет ролей.",
            parse_mode="HTML"
        )
        return

    text = f"📋 <b>Сезон: {html.escape(season)}</b>\n\n"
    for role in roles:
        role_name = role.get('name', '?')
        status = role.get('status', 'свободна')
        if status == 'свободна':
            status_text = "🟢 свободна"
        elif status == 'бронь':
            status_text = "🟡 забронирована"
        elif status == 'рест':
            extra = role.get('extra', '')
            status_text = f"🔵 рест до {extra}" if extra else "🔵 рест"
        elif status == 'ожидает':
            status_text = "⏳ ожидает"
        else:
            status_text = "🔴 занята"
        text += f"  • {html.escape(role_name)} — {status_text}\n"

    if len(text) > 4000:
        await callback.message.edit_text(text[:3900], parse_mode="HTML")
        await callback.message.answer(
            "\n... продолжение ...\n" + text[3900:],
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

    if callback.message.chat.id == GENERAL_CHAT_ID:
        await callback.message.delete()
        await callback.message.answer("🔙 Вы вернулись.")
        return

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

    await callback.message.edit_text(
        "📋 <b>Список ролей по сезонам</b>\n\n"
        "Выберите сезон.\n\n"
        "🟢 свободна | 🟡 забронирована | 🔴 занята | 🔵 рест | ⏳ ожидает",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )