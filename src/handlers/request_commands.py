import html
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import GENERAL_CHAT_ID
from utils.admin_utils import is_admin
from utils.requests_utils import (
    get_pending_requests, approve_request, reject_request,
    get_request_by_user_id, load_requests, save_requests
)
from utils.role_utils import get_role_by_name, update_role_status, get_user_role as get_user_role_from_roles
from .keyboards import get_main_keyboard
import logging

logger = logging.getLogger(__name__)
router = Router()

class RejectReason(StatesGroup):
    waiting_for_reason = State()

@router.message(Command('requests'))
async def cmd_requests(message: Message):
    user_id = message.from_user.id
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
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"view_req_{req['user_id']}")])
    
    buttons.append([InlineKeyboardButton(text="🔄 Обновить список", callback_data="refresh_requests")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(
        f"📝 <b>Заявки в ожидании ({len(pending)})</b>\n\nНажмите на заявку, чтобы управлять ею:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@router.message(Command('approve'))
async def cmd_approve(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /approve [ID заявки]")
        return
    
    try:
        request_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID. Введите число.")
        return
    
    if approve_request(request_id):
        await message.answer(f"✅ Заявка #{request_id} одобрена!")
    else:
        await message.answer(f"❌ Заявка #{request_id} не найдена или уже обработана.")

@router.message(Command('reject'))
async def cmd_reject(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /reject [ID заявки]")
        return
    
    try:
        request_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID. Введите число.")
        return
    
    # Сохраняем ID заявки в состояние
    await state.update_data(request_id=request_id)
    await state.set_state(RejectReason.waiting_for_reason)
    
    await message.answer("📝 Напишите причину отклонения заявки:")

@router.message(RejectReason.waiting_for_reason)
async def reject_with_reason(message: Message, state: FSMContext):
    user_id = message.from_user.id
    reason = message.text[:500]
    
    data = await state.get_data()
    request_id = data.get('request_id')
    
    if not request_id:
        await message.answer("❌ Ошибка: ID заявки потерян. Попробуйте снова /reject.")
        await state.clear()
        return
    
    if reject_request(request_id):
        await message.answer(f"✅ Заявка #{request_id} отклонена.\nПричина: {html.escape(reason)}")
        logger.info(f"Админ {user_id} отклонил заявку #{request_id} с причиной: {reason}")
    else:
        await message.answer(f"❌ Заявка #{request_id} не найдена или уже обработана.")
    
    await state.clear()

@router.callback_query(F.data == "refresh_requests")
async def refresh_requests(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.message.edit_text("⛔ Доступ запрещён.")
        return
    
    pending = get_pending_requests()
    if not pending:
        await callback.message.edit_text("📭 Нет заявок в ожидании.")
        return
    
    buttons = []
    for req in pending:
        safe_name = html.escape(req['full_name'])
        safe_role = html.escape(req['role'])
        button_text = f"{safe_name} (@{req['username']}) - {safe_role}"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"view_req_{req['user_id']}")])
    
    buttons.append([InlineKeyboardButton(text="🔄 Обновить список", callback_data="refresh_requests")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(
        f"📝 <b>Заявки в ожидании ({len(pending)})</b>\n\nНажмите на заявку, чтобы управлять ею:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("view_req_"))
async def view_request(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("⛔ Доступ запрещён.")
        return
    
    try:
        parts = callback.data.split("_")
        if len(parts) < 3:
            await callback.answer("❌ Неверный формат")
            return
        target_user_id = int(parts[2])
    except (IndexError, ValueError) as e:
        logger.error(f"Ошибка парсинга callback: {e}")
        await callback.answer("❌ Ошибка")
        return
    
    request = get_request_by_user_id(target_user_id)
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
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_req_{target_user_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_req_{target_user_id}")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_requests")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)

@router.callback_query(F.data.startswith("approve_req_"))
async def approve_request_callback(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("⛔ Доступ запрещён.")
        return
    
    try:
        target_user_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка")
        return
    
    request = get_request_by_user_id(target_user_id)
    if not request or request.get('status') != 'pending':
        await callback.message.edit_text("❌ Заявка уже обработана.")
        return
    
    role_name = request.get('role')
    if not role_name:
        await callback.message.edit_text("❌ Ошибка: роль не указана.")
        return
    
    # Проверяем, свободна ли роль
    role_data = get_role_by_name(role_name)
    if not role_data:
        await callback.message.edit_text(f"❌ Роль '{html.escape(role_name)}' не найдена.")
        return
    
    if role_data.get('status') != 'свободна':
        await callback.message.edit_text(f"❌ Роль '{html.escape(role_name)}' уже занята.")
        return
    
    # Занимаем роль
    if occupy_role(role_name, target_user_id, request.get('username')):
        # Создаём заявку
        requests = load_requests()
        for req in requests:
            if req.get('user_id') == target_user_id and req.get('status') == 'pending':
                req['status'] = 'approved'
                break
        save_requests(requests)
        
        await callback.message.edit_text(
            f"✅ <b>Заявка одобрена!</b>\n\n"
            f"📌 Роль: <b>{html.escape(role_name)}</b>\n"
            f"👤 Пользователь: <b>{html.escape(request['full_name'])}</b>\n"
            f"🏷️ Должность: <b>{html.escape(request['position'])}</b>"
        )
        
        # Уведомляем пользователя
        try:
            await callback.bot.send_message(
                target_user_id,
                f"✅ <b>Ваша заявка на роль '{html.escape(role_name)}' одобрена!</b>\n\n"
                f"📌 Роль: <b>{html.escape(role_name)}</b>\n"
                f"🏷️ Должность: <b>{html.escape(request['position'])}</b>\n\n"
                f"Теперь вы участник флуда! 🎉",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"❌ Не удалось уведомить пользователя: {e}")
        
        logger.info(f"Админ {user_id} одобрил заявку на роль {role_name} для пользователя {target_user_id}")
    else:
        await callback.message.edit_text("❌ Ошибка при выдаче роли.")

@router.callback_query(F.data.startswith("reject_req_"))
async def reject_request_callback(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("⛔ Доступ запрещён.")
        return
    
    try:
        target_user_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка")
        return
    
    request = get_request_by_user_id(target_user_id)
    if not request or request.get('status') != 'pending':
        await callback.message.edit_text("❌ Заявка уже обработана.")
        return
    
    # Отклоняем заявку
    requests = load_requests()
    for req in requests:
        if req.get('user_id') == target_user_id and req.get('status') == 'pending':
            req['status'] = 'rejected'
            break
    save_requests(requests)
    
    role_name = request.get('role', 'неизвестная')
    await callback.message.edit_text(
        f"❌ <b>Заявка отклонена.</b>\n\n"
        f"📌 Роль: <b>{html.escape(role_name)}</b>\n"
        f"👤 Пользователь: <b>{html.escape(request['full_name'])}</b>"
    )
    
    # Уведомляем пользователя
    try:
        await callback.bot.send_message(
            target_user_id,
            f"❌ <b>Ваша заявка на роль '{html.escape(role_name)}' отклонена.</b>\n\n"
            f"Вы можете подать новую заявку через /apply.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"❌ Не удалось уведомить пользователя: {e}")
    
    logger.info(f"Админ {user_id} отклонил заявку на роль {role_name} для пользователя {target_user_id}")

@router.callback_query(F.data == "back_to_requests")
async def back_to_requests(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.message.edit_text("⛔ Доступ запрещён.")
        return
    
    pending = get_pending_requests()
    if not pending:
        await callback.message.edit_text("📭 Нет заявок в ожидании.")
        return
    
    buttons = []
    for req in pending:
        safe_name = html.escape(req['full_name'])
        safe_role = html.escape(req['role'])
        button_text = f"{safe_name} (@{req['username']}) - {safe_role}"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"view_req_{req['user_id']}")])
    
    buttons.append([InlineKeyboardButton(text="🔄 Обновить список", callback_data="refresh_requests")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(
        f"📝 <b>Заявки в ожидании ({len(pending)})</b>\n\nНажмите на заявку, чтобы управлять ею:",
        parse_mode="HTML",
        reply_markup=keyboard
    )