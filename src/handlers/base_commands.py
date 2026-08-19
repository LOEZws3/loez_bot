import html
import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import GENERAL_CHAT_ID
from utils.admin_utils import get_admin_rank, is_admin
from utils.user_utils import load_users, get_users_count
from utils.requests_utils import get_request_by_user_id, get_pending_count
from utils.role_utils import get_taken_roles, count_taken_roles, get_user_role as get_user_role_from_roles, get_all_seasons, get_roles_by_season, load_roles_status
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

@router.message(Command('start'))
async def cmd_start(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    logger.info(f"👤 {message.from_user.full_name} нажал /start")

    request = get_request_by_user_id(user_id)
    status_text = ""
    if request:
        if request['status'] == 'pending':
            status_text = "\n\n📌 Ваша заявка рассматривается администрацией."
        elif request['status'] == 'approved':
            status_text = "\n\n✅ Ваша заявка одобрена!"
        elif request['status'] == 'rejected':
            status_text = "\n\n❌ Ваша заявка отклонена. Попробуйте подать новую."

    safe_name = html.escape(message.from_user.full_name)
    text = (
        f"👋 Добро пожаловать, <b>{safe_name}</b>!\n\n"
        f"Я бот для управления ролями и заявками.\n"
        f"Если у вас есть вопросы — напишите <b>@Sedrikai_bot</b> (бот-пересыльщик), "
        f"и ближайший освободившийся администратор ответит вам, как только сможет.\n\n"
        f"📌 Используйте /help для списка команд.{status_text}"
    )

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))

@router.message(Command('help'))
async def cmd_help(message: Message):
    user_id = message.from_user.id if message.from_user else None
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
    user_id = message.from_user.id if message.from_user else None
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
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id), disable_web_page_preview=False)

@router.message(Command('aboutme'))
async def cmd_aboutme(message: Message):
    user = message.from_user
    if user is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    rank = get_admin_rank(user.id)
    rank_name = {1: "👑 Владелец", 2: "🔐 Админ", 3: "🛡️ Модератор"}.get(rank, "👤 Нет")
    user_role = get_user_role_from_roles(user.id)
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
    user_id = message.from_user.id if message.from_user else None
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
    user_id = message.from_user.id if message.from_user else None
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
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён. Только для администраторов.")
        return
    stats = get_user_role_stats()
    total = get_users_count()
    text = f"📊 <b>Статистика по ролям</b>\n"
    text += f"📅 {datetime.date.today().strftime('%d.%m.%Y')}\n"
    text += f"👥 Всего: {total + 4}\n\n"
    role_order = ['4', '2', '0', '1', '3', '5']
    for role_key in role_order:
        if role_key in stats:
            role_name = ROLE_NAMES.get(role_key, role_key)
            text += f"• {role_name}: {stats[role_key]}\n"
    text += f"\n🤖 Боты: 4"
    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text, parse_mode="HTML")
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
        await callback.message.answer("🔙 Вы вернулись в главное меню.", reply_markup=get_main_keyboard(user_id, callback.message.chat.id))

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