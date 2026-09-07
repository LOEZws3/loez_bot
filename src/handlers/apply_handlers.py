import html
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import logging
from config import CHAT_INVITE_LINK, ADMIN_GROUP_ID, ROLES_PER_PAGE
from utils.role_utils import (
    get_all_seasons, get_roles_by_season, get_role_by_name,
    get_role_status, update_role_status, load_roles_status
)
from utils.requests_utils import add_request, get_request_by_user_id, get_pending_count
from utils.user_history import load_user_history
from utils.user_utils import get_user_role as get_user_role_name
from utils.role_utils import get_user_role as get_user_role_from_roles
from utils.admin_utils import is_admin
from .apply_states import ApplyStates
from .keyboards import get_main_keyboard

# Исправлено: __name__ вместо name
logger = logging.getLogger(__name__)
router = Router()
logger.info("🔥 apply_handlers.py загружен!")


def get_seasons_keyboard():
    seasons = get_all_seasons()
    buttons = []
    for season in sorted(seasons):
        buttons.append([InlineKeyboardButton(
            text=f"📂 {season}",
            callback_data=f"season_{season}"
        )])
    buttons.append([InlineKeyboardButton(
        text="🔙 Назад в меню",
        callback_data="apply_back_to_menu"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_roles_keyboard(season, page=0):
    roles = get_roles_by_season(season)
    status_data = load_roles_status()
    free_roles = [
        role for role in roles
        if status_data.get(role, {}).get('status', 'свободна') == 'свободна'
    ]
    if not free_roles:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📭 Нет свободных ролей", callback_data="noop")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="apply_back_to_seasons")]
        ])

    total_pages = (len(free_roles) + ROLES_PER_PAGE - 1) // ROLES_PER_PAGE
    start_idx = page * ROLES_PER_PAGE
    end_idx = min(start_idx + ROLES_PER_PAGE, len(free_roles))
    page_roles = free_roles[start_idx:end_idx]

    buttons = []
    for role in page_roles:
        buttons.append([InlineKeyboardButton(
            text=f"🎭 {role}",
            callback_data=f"select_role_{role}"
        )])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"role_page_{page - 1}"
        ))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(
            text="Вперед ➡️",
            callback_data=f"role_page_{page + 1}"
        ))

    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([InlineKeyboardButton(
        text="🔄 Обновить список",
        callback_data="apply_show_free_roles"
    )])
    buttons.append([InlineKeyboardButton(
        text="🔙 Назад к сезонам",
        callback_data="apply_back_to_seasons"
    )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_position_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Участник", callback_data="position_Участник")],
        [InlineKeyboardButton(text="🛡️ Модератор", callback_data="position_Модер")],
        [InlineKeyboardButton(text="👑 Администратор", callback_data="position_Админ")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="apply_back_to_role")]
    ])


def get_confirmation_keyboard(role, season, position):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, все верно", callback_data="confirm_yes")],
        [InlineKeyboardButton(text="❌ Нет, изменить", callback_data="confirm_no")],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="apply_back_to_menu")]
    ])


# ============================================================
# КОМАНДА /APPLY
# ============================================================
@router.message(Command('apply'))
async def cmd_apply(message: Message, state: FSMContext):
    logger.info("🔥 Команда /apply вызвана!")
    user = message.from_user
    if user is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    history = load_user_history(user.id)
    if history.get('left_reason') == 'banned':
        await message.answer(
            f"❌ Вы не можете подать заявку, так как были забанены.\n"
            f"⚠️ Подсказка: посмотрите причину по дате: {history.get('last_left', 'неизвестно')}"
        )
        return

    user_role = get_user_role_from_roles(user.id)
    if user_role:
        await message.answer(
            f"ℹ️ Вы уже занимаете роль '{html.escape(user_role)}'.\n"
            f"Если хотите сменить роль, сначала освободите её командой /free.",
            parse_mode="HTML"
        )
        return

    existing = get_request_by_user_id(user.id)
    if existing and existing['status'] == 'pending':
        await message.answer(
            f"⏳ У вас уже есть активная заявка на роль '{html.escape(existing['role'])}'.\n"
            f"Дождитесь её обработки или отмените через /cancel_request."
        )
        return

    await state.clear()
    await message.answer(
        "📋 <b>Подача заявки на роль</b>\n\n"
        "Чтобы подать заявку, следуйте инструкции:\n"
        "1. Выберите сезон\n"
        "2. Выберите свободную роль\n"
        "3. Укажите желаемую должность\n"
        "4. Подтвердите заявку\n\n"
        "💡 <b>Совет:</b> Используйте кнопку «Списки ролей», чтобы посмотреть все свободные роли.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Списки ролей", callback_data="apply_show_seasons")],
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="apply_back_to_menu")]
        ])
    )
    logger.info(f"📝 Пользователь {user.id} начал подачу заявки")


# ============================================================
# КОМАНДА /FREEROLE (перенаправляет на /apply)
# ============================================================
@router.message(Command('freerole'))
async def cmd_freerole(message: Message, state: FSMContext):
    await cmd_apply(message, state)


# ============================================================
# ОБРАБОТЧИКИ КНОПОК
# ============================================================
@router.callback_query(F.data == "apply_back_to_menu")
async def apply_back_to_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    user_id = callback.from_user.id
    await callback.message.delete()
    await callback.message.answer(
        "🔙 Вы вернулись в главное меню.",
        reply_markup=get_main_keyboard(user_id, callback.message.chat.id)
    )


@router.callback_query(F.data == "apply_show_seasons")
async def apply_show_seasons(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    seasons = get_all_seasons()
    if not seasons:
        await callback.message.edit_text(
            "❌ Сезоны не найдены.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="apply_back_to_menu")]
            ])
        )
        return

    await state.set_state(ApplyStates.waiting_for_season)
    await callback.message.edit_text(
        "📂 <b>Выберите сезон:</b>\n\n"
        "Нажмите на нужный сезон, чтобы посмотреть доступные роли.",
        parse_mode="HTML",
        reply_markup=get_seasons_keyboard()
    )


@router.callback_query(F.data.startswith("season_"))
async def select_season(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    season = callback.data.replace("season_", "")
    await state.update_data(season=season)

    roles = get_roles_by_season(season)
    status_data = load_roles_status()
    free_roles = [
        role for role in roles
        if status_data.get(role, {}).get('status', 'свободна') == 'свободна'
    ]

    if not free_roles:
        await callback.message.edit_text(
            f"📭 В сезоне <b>{html.escape(season)}</b> нет свободных ролей.\n\n"
            f"Выберите другой сезон или вернитесь в меню.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 К сезонам", callback_data="apply_show_seasons")],
                [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="apply_back_to_menu")]
            ])
        )
        return

    await state.set_state(ApplyStates.waiting_for_role)
    await state.update_data(role_page=0)
    await callback.message.edit_text(
        f"📋 <b>Сезон: {html.escape(season)}</b>\n\n"
        f"Выберите свободную роль из списка ниже.\n"
        f"Всего свободных ролей: {len(free_roles)}",
        parse_mode="HTML",
        reply_markup=get_roles_keyboard(season, 0)
    )


@router.callback_query(F.data.startswith("role_page_"))
async def change_role_page(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    page = int(callback.data.replace("role_page_", ""))
    data = await state.get_data()
    season = data.get('season')
    if not season:
        await callback.answer("❌ Ошибка: сезон не выбран")
        return
    await state.update_data(role_page=page)
    await callback.message.edit_reply_markup(
        reply_markup=get_roles_keyboard(season, page)
    )


@router.callback_query(F.data == "apply_show_free_roles")
async def show_free_roles(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    season = data.get('season')
    page = data.get('role_page', 0)
    if not season:
        await callback.message.edit_text(
            "❌ Ошибка: сезон не выбран.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="apply_back_to_menu")]
            ])
        )
        return
    await callback.message.edit_reply_markup(
        reply_markup=get_roles_keyboard(season, page)
    )


@router.callback_query(F.data.startswith("select_role_"))
async def select_role(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    role_name = callback.data.replace("select_role_", "")
    role = get_role_by_name(role_name)
    if not role:
        await callback.message.edit_text(
            f"❌ Роли '{html.escape(role_name)}' больше не существует.\n\n"
            f"Вернитесь к списку ролей и выберите другую.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 К ролям", callback_data="apply_show_free_roles")],
                [InlineKeyboardButton(text="🔙 К сезонам", callback_data="apply_show_seasons")]
            ])
        )
        return

    if role['status'] != 'свободна':
        await callback.message.edit_text(
            f"❌ Роль '{html.escape(role_name)}' уже занята.\n\n"
            f"Выберите другую роль.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 К ролям", callback_data="apply_show_free_roles")],
                [InlineKeyboardButton(text="🔙 К сезонам", callback_data="apply_show_seasons")]
            ])
        )
        return

    data = await state.get_data()
    season = data.get('season', 'Неизвестно')
    await state.update_data(role=role_name, season=season)
    await state.set_state(ApplyStates.waiting_for_position)
    await callback.message.edit_text(
        f"📝 <b>Вы выбрали роль:</b> {html.escape(role_name)}\n"
        f"📂 <b>Сезон:</b> {html.escape(season)}\n\n"
        f"Теперь выберите желаемую должность:",
        parse_mode="HTML",
        reply_markup=get_position_keyboard()
    )


@router.callback_query(F.data == "apply_back_to_seasons")
async def apply_back_to_seasons(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ApplyStates.waiting_for_season)
    await callback.message.edit_text(
        "📂 <b>Выберите сезон:</b>\n\n"
        "Нажмите на нужный сезон, чтобы посмотреть доступные роли.",
        parse_mode="HTML",
        reply_markup=get_seasons_keyboard()
    )


@router.callback_query(F.data == "apply_back_to_role")
async def apply_back_to_role(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    season = data.get('season')
    page = data.get('role_page', 0)
    if not season:
        await callback.message.edit_text(
            "❌ Ошибка: сезон не выбран.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="apply_back_to_menu")]
            ])
        )
        return
    await state.set_state(ApplyStates.waiting_for_role)
    await callback.message.edit_text(
        f"📋 <b>Сезон: {html.escape(season)}</b>\n\n"
        f"Выберите свободную роль из списка ниже.",
        parse_mode="HTML",
        reply_markup=get_roles_keyboard(season, page)
    )


@router.callback_query(F.data.startswith("position_"))
async def select_position(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    position = callback.data.replace("position_", "")
    data = await state.get_data()
    role = data.get('role')
    season = data.get('season', 'Неизвестно')
    if not role:
        await callback.message.edit_text(
            "❌ Ошибка: роль не выбрана.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="apply_back_to_menu")]
            ])
        )
        return
    await state.update_data(position=position)
    await state.set_state(ApplyStates.waiting_for_confirmation)
    await callback.message.edit_text(
        f"✅ <b>Подтвердите заявку</b>\n\n"
        f"📌 <b>Роль:</b> {html.escape(role)}\n"
        f"📂 <b>Сезон:</b> {html.escape(season)}\n"
        f"🏷️ <b>Должность:</b> {html.escape(position)}\n\n"
        f"Все верно?",
        parse_mode="HTML",
        reply_markup=get_confirmation_keyboard(role, season, position)
    )


@router.callback_query(F.data == "confirm_yes")
async def confirm_apply(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user = callback.from_user
    data = await state.get_data()
    role = data.get('role')
    season = data.get('season', 'Неизвестно')
    position = data.get('position')

    if not all([role, position]):
        await callback.message.edit_text(
            "❌ Ошибка: недостаточно данных для создания заявки.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="apply_back_to_menu")]
            ])
        )
        return

    role_data = get_role_by_name(role)
    if not role_data or role_data['status'] != 'свободна':
        await callback.message.edit_text(
            f"❌ Роль '{html.escape(role)}' уже занята.\n\n"
            f"Пожалуйста, начните заявку заново.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Начать заново", callback_data="apply_show_seasons")],
                [InlineKeyboardButton(text="🔙 В меню", callback_data="apply_back_to_menu")]
            ])
        )
        return

    success = add_request(user.id, user.username, user.full_name, role, position)
    if success:
        update_role_status(role, 'бронь', user.id, user.username)
        await callback.message.edit_text(
            f"✅ <b>Ваша заявка подана!</b>\n\n"
            f"📌 Роль: <b>{html.escape(role)}</b>\n"
            f"📂 Сезон: {html.escape(season)}\n"
            f"🏷️ Должность: <b>{html.escape(position)}</b>\n\n"
            f"Роль '<b>{html.escape(role)}</b>' временно забронирована для вас.\n"
            f"Ожидайте ответа администрации.\n\n"
            f"💡 Статус заявки можно проверить через /aboutme",
            parse_mode="HTML"
        )
        logger.info(f"📝 Новая заявка от {user.full_name} на роль {role} ({position})")

        if ADMIN_GROUP_ID and ADMIN_GROUP_ID != -1001234567890:
            try:
                pending_count = get_pending_count()
                await callback.bot.send_message(
                    chat_id=ADMIN_GROUP_ID,
                    text=f"📝 <b>НОВАЯ ЗАЯВКА!</b>\n\n"
                         f"👤 Пользователь: {html.escape(user.full_name)}\n"
                         f"🔖 Юзернейм: @{user.username if user.username else 'не указан'}\n"
                         f"🆔 ID: <code>{user.id}</code>\n"
                         f"📌 Роль: <b>{html.escape(role)}</b>\n"
                         f"📂 Сезон: {html.escape(season)}\n"
                         f"🏷️ Должность: <b>{html.escape(position)}</b>\n\n"
                         f"📊 Всего заявок в ожидании: {pending_count}\n"
                         f"💡 /approve {user.id} — одобрить\n"
                         f"💡 /reject {user.id} — отклонить",
                    parse_mode="HTML"
                )
                logger.info(f"📨 Уведомление о заявке отправлено в админ-группу (ID: {ADMIN_GROUP_ID})")
            except Exception as e:
                logger.error(f"❌ Ошибка уведомления в группе: {e}")
        await state.clear()
    else:
        await callback.message.edit_text(
            "❌ Ошибка при подаче заявки. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 В меню", callback_data="apply_back_to_menu")]
            ])
        )


@router.callback_query(F.data == "confirm_no")
async def confirm_no(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ApplyStates.waiting_for_position)
    await callback.message.edit_text(
        f"📝 <b>Измените выбор</b>\n\n"
        f"Выберите желаемую должность:",
        parse_mode="HTML",
        reply_markup=get_position_keyboard()
    )


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer("ℹ️ Действие недоступно")