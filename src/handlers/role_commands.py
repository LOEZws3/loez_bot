import html
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import GENERAL_CHAT_ID
from utils.admin_utils import is_admin
from utils.requests_utils import get_request_by_user_id, load_requests, save_requests, add_request
from utils.role_utils import (
    get_role_by_name, update_role_status, get_user_role as get_user_role_from_roles,
    get_role_status, occupy_role, free_role, load_roles_status, save_roles_status
)
from .keyboards import get_main_keyboard
import logging

logger = logging.getLogger(__name__)
router = Router()

class FreeRoleStates(StatesGroup):
    waiting_confirmation = State()

@router.message(Command('apply'))
async def cmd_apply(message: Message):
    """Подача заявки на роль"""
    user_id = message.from_user.id
    user = message.from_user
    
    # Проверяем, не закрыт ли набор
    from . import closed_mode
    if closed_mode:
        await message.answer("🔒 Набор на роли временно закрыт администрацией.")
        return
    
    # Проверяем, есть ли уже активная заявка
    request = get_request_by_user_id(user_id)
    if request and request.get('status') == 'pending':
        await message.answer("⏳ У вас уже есть активная заявка. Дождитесь ответа администрации.")
        return
    
    # Проверяем, не занята ли уже роль
    user_role = get_user_role_from_roles(user_id)
    if user_role:
        await message.answer(f"❌ У вас уже есть роль: <b>{html.escape(user_role)}</b>", parse_mode="HTML")
        return
    
    await message.answer(
        "📝 <b>Подача заявки на роль</b>\n\n"
        "Чтобы подать заявку, напишите команду в формате:\n"
        "<code>/apply [название роли] [ваша должность]</code>\n\n"
        "Пример: <code>/apply Ашра Повелительница теней</code>\n\n"
        "📌 <b>Важно:</b> Убедитесь, что роль свободна. Проверить можно через /roles",
        parse_mode="HTML"
    )

@router.message(Command('free'))
async def cmd_free(message: Message, state: FSMContext):
    """Освободить свою роль"""
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

@router.message(Command('cancel_request'))
async def cmd_cancel_request(message: Message):
    """Отмена заявки"""
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