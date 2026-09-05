import html
import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import GENERAL_CHAT_ID
from utils.admin_utils import is_admin, load_admins
from utils.role_utils import (
    get_user_role as get_user_role_from_roles,
    get_role_by_name, update_role_status,
    load_roles_status, save_roles_status
)
from .keyboards import get_main_keyboard
from .utils import generate_calendar_keyboard, load_rest_requests, save_rest_requests
import logging

logger = logging.getLogger(__name__)
router = Router()

class RestRequestStates(StatesGroup):
    waiting_for_date = State()
    waiting_for_reason = State()

@router.message(Command('rest'))
async def cmd_rest(message: Message, state: FSMContext):
    """Подача заявки на рест"""
    user_id = message.from_user.id
    user_role = get_user_role_from_roles(user_id)
    
    if not user_role:
        await message.answer("❌ У вас нет активной роли.")
        return
    
    role_data = get_role_by_name(user_role)
    if not role_data or role_data.get('status') != 'занята':
        await message.answer(f"❌ Ваша роль '{html.escape(user_role)}' не активна или уже в ресте.")
        return
    
    # Проверяем, есть ли уже заявка
    requests = load_rest_requests()
    for req in requests:
        if req.get('user_id') == user_id and req.get('status') == 'pending':
            await message.answer("⏳ У вас уже есть активная заявка на рест.")
            return
    
    await state.update_data(role_name=user_role)
    await state.set_state(RestRequestStates.waiting_for_date)
    
    # Показываем календарь для выбора даты
    today = datetime.date.today()
    keyboard = generate_calendar_keyboard(today.year, today.month)
    
    await message.answer(
        f"📅 <b>Выберите дату окончания реста</b>\n\n"
        f"Роль: <b>{html.escape(user_role)}</b>\n"
        f"Рест начинается сегодня.\n\n"
        f"Выберите дату, когда вы сможете вернуться:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("rest_cal_"))
async def rest_calendar_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора даты в календаре"""
    await callback.answer()
    
    parts = callback.data.split("_")
    if len(parts) < 5:
        return
    
    try:
        year = int(parts[2])
        month = int(parts[3])
        day = int(parts[4])
        selected_date = datetime.date(year, month, day)
    except (IndexError, ValueError):
        await callback.message.edit_text("❌ Ошибка при выборе даты.")
        return
    
    today = datetime.date.today()
    if selected_date < today:
        await callback.answer("❌ Нельзя выбрать прошедшую дату.")
        return
    
    # Сохраняем дату
    days = (selected_date - today).days
    await state.update_data(rest_days=days, rest_date=selected_date)
    
    # Запрашиваем причину
    await state.set_state(RestRequestStates.waiting_for_reason)
    await callback.message.edit_text(
        f"📝 <b>Укажите причину реста</b>\n\n"
        f"Роль: <b>{html.escape(callback.data)}</b>\n"
        f"Дата окончания: <b>{selected_date.strftime('%d.%m.%Y')}</b>\n"
        f"Дней: <b>{days}</b>\n\n"
        f"Напишите причину реста одним сообщением:",
        parse_mode="HTML"
    )

@router.message(RestRequestStates.waiting_for_reason)
async def rest_reason_handler(message: Message, state: FSMContext):
    """Обработка причины реста"""
    user_id = message.from_user.id
    reason = message.text[:200]
    
    data = await state.get_data()
    role_name = data.get('role_name')
    days = data.get('rest_days')
    rest_date = data.get('rest_date')
    
    if not role_name or not days:
        await message.answer("❌ Ошибка: данные потеряны. Попробуйте снова /rest.")
        await state.clear()
        return
    
    # Создаём заявку
    requests = load_rest_requests()
    requests.append({
        'user_id': user_id,
        'role_name': role_name,
        'days': days,
        'rest_date': rest_date.strftime('%Y-%m-%d') if rest_date else None,
        'reason': reason,
        'status': 'pending',
        'created_at': datetime.datetime.now().isoformat()
    })
    save_rest_requests(requests)
    
    await state.clear()
    await message.answer(
        f"✅ <b>Заявка на рест отправлена!</b>\n\n"
        f"📌 Роль: <b>{html.escape(role_name)}</b>\n"
        f"📅 Дата окончания: <b>{rest_date.strftime('%d.%m.%Y') if rest_date else 'не указана'}</b>\n"
        f"📊 Дней: <b>{days}</b>\n"
        f"📝 Причина: {html.escape(reason)}\n\n"
        f"⏳ Ожидайте одобрения администратора.",
        parse_mode="HTML"
    )
    
    # Уведомляем админов
    admins = load_admins()
    for admin in admins:
        try:
            await message.bot.send_message(
                admin['id'],
                f"🆕 <b>Новая заявка на рест!</b>\n\n"
                f"👤 Пользователь: {html.escape(message.from_user.full_name)} (@{message.from_user.username})\n"
                f"📌 Роль: <b>{html.escape(role_name)}</b>\n"
                f"📅 Дата окончания: <b>{rest_date.strftime('%d.%m.%Y') if rest_date else 'не указана'}</b>\n"
                f"📝 Причина: {html.escape(reason)}\n\n"
                f"Используйте команды:\n"
                f"/approve_rest {user_id} – одобрить\n"
                f"/reject_rest {user_id} – отклонить",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"❌ Не удалось уведомить админа {admin['id']}: {e}")

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
        if data.get('status') == 'рест':
            rest_until = data.get('extra')
            active_rests.append((role_name, rest_until))
    
    if not active_rests:
        await message.answer("📭 Нет активных рестов.")
        return
    
    text = "⏳ <b>Активные ресты</b>\n\n"
    for role_name, rest_until in active_rests:
        text += f"• {html.escape(role_name)} – до {html.escape(rest_until or 'не указано')}\n"
    
    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))

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
        await message.answer(f"❌ Роль '{html.escape(role_name)}' не найдена.")
        return
    
    if role_data.get('status') != 'рест':
        await message.answer(f"❌ Роль '{html.escape(role_name)}' не в ресте.")
        return
    
    # Снимаем рест
    if update_role_status(role_name, 'занята', role_data.get('owner_id'), role_data.get('username'), ""):
        # Уведомляем владельца
        owner_id = role_data.get('owner_id')
        if owner_id:
            try:
                await message.bot.send_message(
                    owner_id,
                    f"🔔 <b>Рест снят!</b>\n\n"
                    f"📌 Роль: <b>{html.escape(role_name)}</b>\n"
                    f"Администратор {html.escape(message.from_user.full_name)} снял рест.\n"
                    f"Теперь вы снова активны.",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"❌ Не удалось уведомить владельца: {e}")
        
        await message.answer(f"✅ Рест с роли '{html.escape(role_name)}' снят.")
        logger.info(f"Админ {user_id} снял рест с роли {role_name}")
    else:
        await message.answer("❌ Ошибка при снятии реста.")

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
        await message.answer("❌ Неверное количество дней. Введите число.")
        return
    
    if days <= 0:
        await message.answer("❌ Количество дней должно быть положительным.")
        return
    
    role_data = get_role_by_name(role_name)
    if not role_data:
        await message.answer(f"❌ Роль '{html.escape(role_name)}' не найдена.")
        return
    
    if role_data.get('status') != 'рест':
        await message.answer(f"❌ Роль '{html.escape(role_name)}' не в ресте.")
        return
    
    # Продлеваем рест
    current_extra = role_data.get('extra', '')
    try:
        # Парсим текущую дату
        current_date = datetime.datetime.strptime(current_extra, "%Y-%m-%d").date()
        new_date = current_date + datetime.timedelta(days=days)
        new_extra = new_date.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        # Если дата невалидна, устанавливаем с сегодня + days
        new_date = datetime.date.today() + datetime.timedelta(days=days)
        new_extra = new_date.strftime("%Y-%m-%d")
    
    if update_role_status(role_name, 'рест', role_data.get('owner_id'), role_data.get('username'), new_extra):
        owner_id = role_data.get('owner_id')
        if owner_id:
            try:
                await message.bot.send_message(
                    owner_id,
                    f"📅 <b>Рест продлён!</b>\n\n"
                    f"📌 Роль: <b>{html.escape(role_name)}</b>\n"
                    f"📅 Новая дата окончания: <b>{new_extra}</b>\n"
                    f"Добавлено дней: <b>{days}</b>\n"
                    f"Администратор: {html.escape(message.from_user.full_name)}",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"❌ Не удалось уведомить владельца: {e}")
        
        await message.answer(f"✅ Рест роли '{html.escape(role_name)}' продлён до {new_extra}.")
        logger.info(f"Админ {user_id} продлил рест роли {role_name} на {days} дней")
    else:
        await message.answer("❌ Ошибка при продлении реста.")