import html
import time
import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import GENERAL_CHAT_ID, ADMIN_GROUP_ID
from utils.admin_utils import is_admin, load_admins
from utils.role_utils import (
    get_user_role as get_user_role_from_roles,
    get_role_by_name, update_role_status,
    load_roles_status, save_roles_status
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

REST_COOLDOWN = {}  # {user_id: last_request_time}
REST_COOLDOWN_SECONDS = 15


class RestRequestStates(StatesGroup):
    waiting_for_date = State()
    waiting_for_reason = State()


# ======================== ПОДАЧА ЗАЯВКИ НА РЕСТ ========================

@router.message(Command('rest'))
async def cmd_rest(message: Message, state: FSMContext):
    """Подача заявки на рест"""
    user_id = message.from_user.id

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда недоступна во флуд-чате.")
        return

    # Кулдаун 15 сек (общий антиспам)
    now = time.time()
    last = REST_COOLDOWN.get(user_id, 0)
    if now - last < REST_COOLDOWN_SECONDS:
        remaining = int(REST_COOLDOWN_SECONDS - (now - last))
        await message.answer(f"⏳ Подождите {remaining} сек перед новой заявкой.")
        return
    REST_COOLDOWN[user_id] = now

    user_role = get_user_role_from_roles(user_id)
    if not user_role:
        await message.answer("❌ У вас нет активной роли.")
        return

    role_data = get_role_by_name(user_role)
    if not role_data or role_data.get('status') != 'занята':
        await message.answer(
            f"❌ Ваша роль «{html.escape(user_role)}» неактивна или уже в ресте."
        )
        return

    # Проверяем, есть ли активная заявка
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
        await callback.message.edit_text("❌ Заявка на рест отменена.")
    except Exception:
        pass


@router.callback_query(F.data.startswith("rest_cal_prev_"))
async def rest_cal_prev(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split("_")
    try:
        year = int(parts[3])
        month = int(parts[4])
    except (IndexError, ValueError):
        return
    keyboard = generate_calendar_keyboard(year, month)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
        pass


@router.callback_query(F.data.startswith("rest_cal_next_"))
async def rest_cal_next(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split("_")
    try:
        year = int(parts[3])
        month = int(parts[4])
    except (IndexError, ValueError):
        return
    keyboard = generate_calendar_keyboard(year, month)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
        pass


@router.callback_query(F.data.startswith("rest_cal_day_"))
async def rest_cal_day(callback: CallbackQuery, state: FSMContext):
    """Выбор даты в календаре"""
    await callback.answer()

    parts = callback.data.split("_")
    # rest_cal_day_YYYY_M_D
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

    days = (selected_date - today).days
    await state.update_data(rest_days=days, rest_until=selected_date.isoformat())

    await state.set_state(RestRequestStates.waiting_for_reason)

    data = await state.get_data()
    role_name = data.get('role_name', '?')

    await callback.message.edit_text(
        f"📝 <b>Причина реста</b>\n\n"
        f"🎭 Роль: <b>{html.escape(role_name)}</b>\n"
        f"📅 До: <b>{selected_date.strftime('%d.%m.%Y')}</b>\n"
        f"📊 Дней: <b>{days}</b>\n\n"
        f"Напишите причину реста одним сообщением:",
        parse_mode="HTML"
    )


@router.message(RestRequestStates.waiting_for_reason)
async def rest_reason_handler(message: Message, state: FSMContext):
    """Обработка причины реста + отправка админам"""
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

    # Сохраняем заявку
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

    # Уведомляем админов
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
            logger.info(f"📨 Уведомление о ресте отправлено в админ-группу")
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
    """Одобрить заявку на рест"""
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

    # Ставим статус "рест" в roles_status.json
    status_data = load_roles_status()
    if role_name in status_data:
        status_data[role_name]['status'] = 'рест'
        status_data[role_name]['extra'] = rest_until
        save_roles_status(status_data)
        logger.info(f"✅ Роль {role_name} в рест до {rest_until}")

    # Обновляем заявку
    update_rest_request(user_id, 'status', 'approved')

    # Уведомляем юзера
    try:
        await callback.bot.send_message(
            user_id,
            f"✅ <b>Рест одобрен!</b>\n\n"
            f"🎭 Роль: <b>{html.escape(role_name)}</b>\n"
            f"📅 До: <b>{datetime.date.fromisoformat(rest_until).strftime('%d.%m.%Y')}</b>\n\n"
            f"Ваша роль остаётся за вами.",
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
    """Отклонить заявку на рест"""
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
            f"❌ <b>Заявка на рест отклонена.</b>\n\n"
            f"🎭 Роль: <b>{html.escape(role_name or '?')}</b>",
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


# ======================== /RESTLIST ========================

@router.message(Command('restlist'))
async def cmd_restlist(message: Message):
    """Список активных рестов"""
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
    """Снять рест с роли (только админ)"""
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

    # Снимаем рест
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

        # Удаляем заявку из JSON если есть
        if owner_id:
            remove_rest_request(int(owner_id))

        await message.answer(f"✅ Рест с роли «{html.escape(role_name)}» снят.")
        logger.info(f"Админ {user_id} снял рест с {role_name}")
    else:
        await message.answer("❌ Ошибка при снятии реста.")


# ======================== /RESTEXTEND ========================

@router.message(Command('restextend'))
async def cmd_restextend(message: Message):
    """Продлить рест (только админ)"""
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

            # Обновляем заявку
            update_rest_request(int(owner_id), 'rest_until', new_extra)

        await message.answer(
            f"✅ Рест роли «{html.escape(role_name)}» продлён до {new_date.strftime('%d.%m.%Y')}."
        )
        logger.info(f"Админ {user_id} продлил рест {role_name} на {days} дней")
    else:
        await message.answer("❌ Ошибка при продлении.")