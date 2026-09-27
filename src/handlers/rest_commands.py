import html
import time
import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import GENERAL_CHAT_ID, ADMIN_GROUP_ID
from utils.admin_utils import is_admin, get_admin_rank, load_admins
from utils.role_utils import (
    get_user_role as get_user_role_from_roles,
    get_role_by_name, update_role_status,
    load_roles_status, save_roles_status,
    get_all_seasons, get_roles_by_season,
)
from .keyboards import get_main_keyboard
from .utils import (
    generate_calendar_keyboard,
    load_rest_requests, save_rest_requests,
    get_rest_request, add_rest_request, remove_rest_request,
    update_rest_request, get_pending_rests,
)
import logging

logger = logging.getLogger(__name__)
router = Router()

REST_COOLDOWN = {}
REST_COOLDOWN_SECONDS = 15


class RestRequestStates(StatesGroup):
    waiting_for_date = State()
    waiting_for_reason = State()


class SetRestStates(StatesGroup):
    """FSM для /setrest — админ ставит рест вручную"""
    choosing_season = State()
    choosing_role = State()
    choosing_date = State()
    waiting_for_reason = State()


# ======================== ПОДАЧА ЗАЯВКИ ========================

@router.message(Command('rest'))
async def cmd_rest(message: Message, state: FSMContext):
    user_id = message.from_user.id

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда недоступна во флуд-чате.")
        return

    now = time.time()
    last = REST_COOLDOWN.get(user_id, 0)
    if now - last < REST_COOLDOWN_SECONDS:
        remaining = int(REST_COOLDOWN_SECONDS - (now - last))
        await message.answer(f"⏳ Подождите {remaining} сек.")
        return
    REST_COOLDOWN[user_id] = now

    user_role = get_user_role_from_roles(user_id)
    if not user_role:
        await message.answer("❌ У вас нет активной роли.")
        return

    role_data = get_role_by_name(user_role)
    if not role_data or role_data.get('status') != 'занята':
        await message.answer(f"❌ Ваша роль «{html.escape(user_role)}» неактивна или уже в ресте.")
        return

    existing = get_rest_request(user_id)
    if existing and existing.get('status') == 'pending':
        await message.answer("⏳ У вас уже есть активная заявка на рест.")
        return

    await state.update_data(role_name=user_role)
    await state.set_state(RestRequestStates.waiting_for_date)

    today = datetime.date.today()
    keyboard = generate_calendar_keyboard(today.year, today.month)

    await message.answer(
        f"📅 <b>Выберите дату окончания реста</b>\n\n"
        f"🎭 Роль: <b>{html.escape(user_role)}</b>\n"
        f"📌 Рест начинается сегодня.\n\n"
        f"Выберите дату, когда вы сможете вернуться:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "cancel_rest_request")
async def cancel_rest_request(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    try:
        await callback.message.edit_text("❌ Отменено.")
    except Exception:
        pass


@router.callback_query(F.data.startswith("rest_cal_"))
async def rest_calendar_handler(callback: CallbackQuery, state: FSMContext):
    data = callback.data

    if data == "rest_cal_ignore":
        await callback.answer()
        return

    if data == "rest_cal_past":
        await callback.answer("❌ Нельзя подать заявку на прошедшую дату", show_alert=True)
        return

    parts = data.split("_")
    if len(parts) < 3:
        await callback.answer()
        return

    action = parts[2]

    if action in ("prev", "next"):
        try:
            year = int(parts[3])
            month = int(parts[4])
        except (IndexError, ValueError):
            await callback.answer("❌ Ошибка навигации.", show_alert=True)
            return
        await callback.answer()
        keyboard = generate_calendar_keyboard(year, month)
        try:
            await callback.message.edit_reply_markup(reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Ошибка навигации: {e}")
        return

    if action == "day":
        try:
            year = int(parts[3])
            month = int(parts[4])
            day = int(parts[5])
            selected_date = datetime.date(year, month, day)
        except (IndexError, ValueError):
            await callback.answer("❌ Ошибка даты.", show_alert=True)
            return

        today = datetime.date.today()
        if selected_date <= today:
            await callback.answer("❌ Дата должна быть в будущем.", show_alert=True)
            return

        # Проверяем — это /rest или /setrest?
        state_data = await state.get_data()
        is_setrest = state_data.get('setrest_mode', False)

        if is_setrest:
            # Режим /setrest
            await state.update_data(rest_days=(selected_date - today).days, rest_until=selected_date.isoformat())
            await state.set_state(SetRestStates.waiting_for_reason)
            await callback.answer()
            await callback.message.edit_text(
                f"📝 <b>Причина реста (необязательно)</b>\n\n"
                f"📅 До: <b>{selected_date.strftime('%d.%m.%Y')}</b>\n\n"
                f"Напишите причину или /skip чтобы пропустить:",
                parse_mode="HTML"
            )
            return
        else:
            # Режим /rest (обычная подача)
            days = (selected_date - today).days
            await state.update_data(rest_days=days, rest_until=selected_date.isoformat())
            await state.set_state(RestRequestStates.waiting_for_reason)

            role_name = state_data.get('role_name', '?')

            await callback.answer()
            await callback.message.edit_text(
                f"📝 <b>Причина реста</b>\n\n"
                f"🎭 Роль: <b>{html.escape(role_name)}</b>\n"
                f"📅 До: <b>{selected_date.strftime('%d.%m.%Y')}</b>\n"
                f"📊 Дней: <b>{days}</b>\n\n"
                f"Напишите причину реста одним сообщением:",
                parse_mode="HTML"
            )
            return

    await callback.answer()


@router.message(RestRequestStates.waiting_for_reason)
async def rest_reason_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    reason = (message.text or "")[:200]

    data = await state.get_data()
    role_name = data.get('role_name')
    days = data.get('rest_days')
    rest_until = data.get('rest_until')

    if not role_name or not days or not rest_until:
        await message.answer("❌ Данные потеряны. Попробуйте /rest заново.")
        await state.clear()
        return

    await state.clear()

    add_rest_request(user_id, {
        'user_id': user_id,
        'username': message.from_user.username or '',
        'full_name': message.from_user.full_name,
        'role_name': role_name,
        'days': days,
        'rest_until': rest_until,
        'reason': reason,
        'status': 'pending',
        'created_at': datetime.datetime.now().isoformat()
    })

    await message.answer(
        f"✅ <b>Заявка на рест отправлена!</b>\n\n"
        f"🎭 Роль: <b>{html.escape(role_name)}</b>\n"
        f"📅 До: <b>{datetime.date.fromisoformat(rest_until).strftime('%d.%m.%Y')}</b>\n"
        f"📊 Дней: <b>{days}</b>\n"
        f"📝 Причина: {html.escape(reason)}\n\n"
        f"⏳ Ожидайте одобрения администратора.",
        parse_mode="HTML"
    )

    text = (
        f"🆕 <b>Новая заявка на рест!</b>\n\n"
        f"👤 {html.escape(message.from_user.full_name)}\n"
        f"🔖 @{message.from_user.username or 'без юзернейма'}\n"
        f"🆔 <code>{user_id}</code>\n"
        f"🎭 Роль: <b>{html.escape(role_name)}</b>\n"
        f"📅 До: <b>{datetime.date.fromisoformat(rest_until).strftime('%d.%m.%Y')}</b>\n"
        f"📊 Дней: <b>{days}</b>\n"
        f"📝 Причина: {html.escape(reason)}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"rest_approve_{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rest_reject_{user_id}")
        ]
    ])

    sent = False
    if ADMIN_GROUP_ID:
        try:
            await message.bot.send_message(ADMIN_GROUP_ID, text, parse_mode="HTML", reply_markup=keyboard)
            sent = True
        except Exception as e:
            logger.error(f"❌ Не удалось отправить в админ-группу: {e}")

    if not sent:
        admins = load_admins()
        for admin in admins:
            if admin.get('rank') not in [1, 2]:
                continue
            try:
                await message.bot.send_message(admin['id'], text, parse_mode="HTML", reply_markup=keyboard)
            except Exception as e:
                logger.error(f"❌ Не удалось уведомить админа {admin['id']}: {e}")


# ======================== ОДОБРЕНИЕ / ОТКЛОНЕНИЕ ========================

@router.callback_query(F.data.startswith("rest_approve_"))
async def rest_approve(callback: CallbackQuery):
    await callback.answer()
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    try:
        user_id = int(callback.data.replace("rest_approve_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка.", show_alert=True)
        return

    req = get_rest_request(user_id)
    if not req or req.get('status') != 'pending':
        await callback.message.edit_text("❌ Заявка уже обработана.")
        return

    role_name = req.get('role_name')
    rest_until = req.get('rest_until')

    status_data = load_roles_status()
    if role_name in status_data:
        status_data[role_name]['status'] = 'рест'
        status_data[role_name]['extra'] = rest_until
        save_roles_status(status_data)

    update_rest_request(user_id, 'status', 'approved')

    try:
        await callback.bot.send_message(
            user_id,
            f"✅ <b>Рест одобрен!</b>\n\n"
            f"🎭 Роль: <b>{html.escape(role_name)}</b>\n"
            f"📅 До: <b>{datetime.date.fromisoformat(rest_until).strftime('%d.%m.%Y')}</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"❌ Уведомление {user_id}: {e}")

    await callback.message.edit_text(
        f"✅ <b>Заявка на рест одобрена</b>\n\n"
        f"👤 <code>{user_id}</code>\n"
        f"🎭 {html.escape(role_name)}\n"
        f"📅 До: {datetime.date.fromisoformat(rest_until).strftime('%d.%m.%Y')}",
        parse_mode="HTML"
    )
    logger.info(f"Админ {admin_id} одобрил рест для {user_id}")


@router.callback_query(F.data.startswith("rest_reject_"))
async def rest_reject(callback: CallbackQuery):
    await callback.answer()
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    try:
        user_id = int(callback.data.replace("rest_reject_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка.", show_alert=True)
        return

    req = get_rest_request(user_id)
    if not req or req.get('status') != 'pending':
        await callback.message.edit_text("❌ Заявка уже обработана.")
        return

    role_name = req.get('role_name')
    update_rest_request(user_id, 'status', 'rejected')

    try:
        await callback.bot.send_message(
            user_id,
            f"❌ <b>Заявка на рест отклонена.</b>\n\n🎭 Роль: <b>{html.escape(role_name or '?')}</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"❌ Уведомление {user_id}: {e}")

    await callback.message.edit_text(
        f"❌ <b>Заявка на рест отклонена</b>\n\n"
        f"👤 <code>{user_id}</code>\n"
        f"🎭 {html.escape(role_name or '?')}",
        parse_mode="HTML"
    )
    logger.info(f"Админ {admin_id} отклонил рест для {user_id}")


# ======================== /SETREST — АДМИН СТАВИТ РЕСТ ========================

@router.message(Command('setrest'))
async def cmd_setrest(message: Message, state: FSMContext):
    """Админ вручную ставит рест на роль"""
    user_id = message.from_user.id

    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return

    if get_admin_rank(user_id) not in [1, 2]:
        await message.answer("⛔ Только владелец и админ.")
        return

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда недоступна во флуд-чате.")
        return

    # Показываем сезоны
    seasons = get_all_seasons()
    if not seasons:
        await message.answer("📭 Сезоны не найдены.")
        return

    buttons = []
    for season in sorted(seasons):
        roles = get_roles_by_season(season)
        occupied = sum(1 for r in roles if r.get('status') == 'занята')
        buttons.append([InlineKeyboardButton(
            text=f"📁 {season} ({occupied} занятых)",
            callback_data=f"setrest_season_{season}"
        )])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="setrest_cancel")])

    await state.set_state(SetRestStates.choosing_season)
    await message.answer(
        "🎯 <b>Кому ставим рест?</b>\n\n"
        "Выберите сезон:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data == "setrest_cancel")
async def setrest_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    try:
        await callback.message.edit_text("❌ Отменено.")
    except Exception:
        pass


@router.callback_query(F.data.startswith("setrest_season_"))
async def setrest_season(callback: CallbackQuery, state: FSMContext):
    """Выбор сезона → показываем роли"""
    await callback.answer()

    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    season = callback.data.replace("setrest_season_", "")
    roles = get_roles_by_season(season)

    # Показываем только занятые
    occupied = [r for r in roles if r.get('status') == 'занята']

    if not occupied:
        await callback.message.edit_text(
            f"❌ В сезоне «{html.escape(season)}» нет занятых ролей.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К сезонам", callback_data="setrest_back_to_seasons")]
            ])
        )
        return

    buttons = []
    for role in occupied:
        role_name = role.get('name', '?')
        owner_id = role.get('owner_id', '?')
        buttons.append([InlineKeyboardButton(
            text=f"🎭 {role_name} (ID: {owner_id})",
            callback_data=f"setrest_role_{role_name}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 К сезонам", callback_data="setrest_back_to_seasons")])

    await state.set_state(SetRestStates.choosing_role)
    await callback.message.edit_text(
        f"📁 <b>Сезон: {html.escape(season)}</b>\n\n"
        f"Выберите роль (только занятые):",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data == "setrest_back_to_seasons")
async def setrest_back_to_seasons(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    seasons = get_all_seasons()
    if not seasons:
        await callback.message.edit_text("📭 Сезоны не найдены.")
        return

    buttons = []
    for season in sorted(seasons):
        roles = get_roles_by_season(season)
        occupied = sum(1 for r in roles if r.get('status') == 'занята')
        buttons.append([InlineKeyboardButton(
            text=f"📁 {season} ({occupied} занятых)",
            callback_data=f"setrest_season_{season}"
        )])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="setrest_cancel")])

    await state.set_state(SetRestStates.choosing_season)
    await callback.message.edit_text(
        "🎯 <b>Кому ставим рест?</b>\n\nВыберите сезон:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("setrest_role_"))
async def setrest_role(callback: CallbackQuery, state: FSMContext):
    """Роль выбрана → календарь"""
    await callback.answer()

    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    role_name = callback.data.replace("setrest_role_", "")

    role_data = get_role_by_name(role_name)
    if not role_data:
        await callback.answer("❌ Роль не найдена.", show_alert=True)
        return

    if role_data.get('status') != 'занята':
        await callback.answer("❌ Роль не занята или уже в ресте.", show_alert=True)
        return

    owner_id = role_data.get('owner_id')

    await state.update_data(
        setrest_mode=True,
        setrest_role=role_name,
        setrest_owner=owner_id,
    )
    await state.set_state(SetRestStates.choosing_date)

    today = datetime.date.today()
    keyboard = generate_calendar_keyboard(today.year, today.month)

    await callback.message.edit_text(
        f"📅 <b>Дата окончания реста</b>\n\n"
        f"🎭 Роль: <b>{html.escape(role_name)}</b>\n"
        f"👤 Владелец: <code>{owner_id}</code>\n\n"
        f"Выберите дату:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.message(SetRestStates.waiting_for_reason)
async def setrest_reason_handler(message: Message, state: FSMContext):
    """Причина реста для /setrest"""
    user_id = message.from_user.id

    if not is_admin(user_id):
        await state.clear()
        return

    text = (message.text or "").strip()
    reason = "" if text == "/skip" else text[:200]

    data = await state.get_data()
    role_name = data.get('setrest_role')
    owner_id = data.get('setrest_owner')
    rest_until = data.get('rest_until')

    if not role_name or not owner_id or not rest_until:
        await message.answer("❌ Данные потеряны. Попробуйте /setrest заново.")
        await state.clear()
        return

    await state.clear()

    # Ставим рест
    status_data = load_roles_status()
    if role_name not in status_data:
        await message.answer(f"❌ Роль «{html.escape(role_name)}» не найдена.")
        return

    status_data[role_name]['status'] = 'рест'
    status_data[role_name]['extra'] = rest_until
    save_roles_status(status_data)

    # Сохраняем в rest_requests.json
    add_rest_request(int(owner_id), {
        'user_id': int(owner_id),
        'role_name': role_name,
        'days': (datetime.date.fromisoformat(rest_until) - datetime.date.today()).days,
        'rest_until': rest_until,
        'reason': reason,
        'status': 'approved',
        'set_by_admin': user_id,
        'created_at': datetime.datetime.now().isoformat()
    })

    # Уведомляем владельца
    try:
        await message.bot.send_message(
            int(owner_id),
            f"🔔 <b>Вам поставлен рест</b>\n\n"
            f"🎭 Роль: <b>{html.escape(role_name)}</b>\n"
            f"📅 До: <b>{datetime.date.fromisoformat(rest_until).strftime('%d.%m.%Y')}</b>"
            + (f"\n📝 Причина: {html.escape(reason)}" if reason else ""),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"❌ Не удалось уведомить {owner_id}: {e}")

    await message.answer(
        f"✅ <b>Рест поставлен</b>\n\n"
        f"🎭 Роль: <b>{html.escape(role_name)}</b>\n"
        f"👤 Владелец: <code>{owner_id}</code>\n"
        f"📅 До: <b>{datetime.date.fromisoformat(rest_until).strftime('%d.%m.%Y')}</b>"
        + (f"\n📝 Причина: {html.escape(reason)}" if reason else ""),
        parse_mode="HTML"
    )
    logger.info(f"Админ {user_id} поставил рест на роль {role_name} до {rest_until}")


@router.message(Command('skip'), SetRestStates.waiting_for_reason)
async def setrest_skip_reason(message: Message, state: FSMContext):
    """Пропустить ввод причины"""
    await setrest_reason_handler(message, state)


# ======================== /RESTLIST ========================

@router.message(Command('restlist'))
async def cmd_restlist(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён. Только для администраторов.")
        return

    roles = load_roles_status()
    active_rests = []
    for role_name, data in roles.items():
        if isinstance(data, dict) and data.get('status') == 'рест':
            owner_id = data.get('owner_id')
            rest_until = data.get('extra', '')
            active_rests.append((role_name, rest_until, owner_id))

    if not active_rests:
        await message.answer("📭 Нет активных рестов.")
        return

    text = f"⏳ <b>Активные ресты</b> ({len(active_rests)})\n\n"
    for role_name, rest_until, owner_id in active_rests:
        text += f"• <b>{html.escape(role_name)}</b> — до {html.escape(rest_until or '?')}\n"
        if owner_id:
            text += f"  👤 <code>{owner_id}</code>\n"

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))


# ======================== /UNREST ========================

@router.message(Command('unrest'))
async def cmd_unrest(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён. Только для администраторов.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /unrest [имя роли]")
        return

    role_name = parts[1].strip()
    role_data = get_role_by_name(role_name)

    if not role_data:
        await message.answer(f"❌ Роль «{html.escape(role_name)}» не найдена.")
        return

    if role_data.get('status') != 'рест':
        await message.answer(f"❌ Роль «{html.escape(role_name)}» не в ресте.")
        return

    status_data = load_roles_status()
    status_data[role_name]['status'] = 'занята'
    status_data[role_name]['extra'] = ''

    if save_roles_status(status_data):
        owner_id = role_data.get('owner_id')
        if owner_id:
            try:
                await message.bot.send_message(
                    owner_id,
                    f"🔔 <b>Рест снят!</b>\n\n"
                    f"🎭 Роль: <b>{html.escape(role_name)}</b>\n"
                    f"Администратор {html.escape(message.from_user.full_name)} снял рест.",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"❌ Не удалось уведомить владельца: {e}")

            remove_rest_request(int(owner_id))

        await message.answer(f"✅ Рест с роли «{html.escape(role_name)}» снят.")
        logger.info(f"Админ {user_id} снял рест с {role_name}")
    else:
        await message.answer("❌ Ошибка при снятии реста.")


# ======================== /RESTEXTEND ========================

@router.message(Command('restextend'))
async def cmd_restextend(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён. Только для администраторов.")
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("❌ Используйте: /restextend [имя роли] [дни]")
        return

    role_name = parts[1].strip()
    try:
        days = int(parts[2])
    except ValueError:
        await message.answer("❌ Неверное количество дней.")
        return

    if days <= 0:
        await message.answer("❌ Количество дней должно быть положительным.")
        return

    role_data = get_role_by_name(role_name)
    if not role_data:
        await message.answer(f"❌ Роль «{html.escape(role_name)}» не найдена.")
        return

    if role_data.get('status') != 'рест':
        await message.answer(f"❌ Роль «{html.escape(role_name)}» не в ресте.")
        return

    current_extra = role_data.get('extra', '')

    try:
        current_date = datetime.date.fromisoformat(current_extra)
    except (ValueError, TypeError):
        current_date = datetime.date.today()

    new_date = current_date + datetime.timedelta(days=days)
    new_extra = new_date.isoformat()

    status_data = load_roles_status()
    status_data[role_name]['extra'] = new_extra

    if save_roles_status(status_data):
        owner_id = role_data.get('owner_id')
        if owner_id:
            try:
                await message.bot.send_message(
                    owner_id,
                    f"📅 <b>Рест продлён!</b>\n\n"
                    f"🎭 Роль: <b>{html.escape(role_name)}</b>\n"
                    f"📅 Новая дата: <b>{new_date.strftime('%d.%m.%Y')}</b>\n"
                    f"Добавлено дней: <b>{days}</b>",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"❌ Не удалось уведомить владельца: {e}")

            update_rest_request(int(owner_id), 'rest_until', new_extra)

        await message.answer(
            f"✅ Рест роли «{html.escape(role_name)}» продлён до {new_date.strftime('%d.%m.%Y')}."
        )
        logger.info(f"Админ {user_id} продлил рест {role_name} на {days} дней")
    else:
        await message.answer("❌ Ошибка при продлении.")