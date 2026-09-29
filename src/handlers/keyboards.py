# ============================================================
# ⚠️ ВАЖНОЕ ПРАВИЛО ДЛЯ КЛАВИАТУРЫ
# ============================================================
# 
# Во флуд-чате (GENERAL_CHAT_ID) клавиатура НЕ ПОКАЗЫВАЕТСЯ!
# Все кнопки и меню должны быть доступны ТОЛЬКО в личных сообщениях.
# ============================================================

import os
import json
import logging
from aiogram import Router, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from config import GENERAL_CHAT_ID
from utils.admin_utils import is_admin
from utils.user_utils import get_user_by_id

logger = logging.getLogger(__name__)
router = Router()


# ============================================================
# ПРОВЕРКА РЕГИСТРАЦИИ (для кнопок)
# ============================================================

async def _check_registration(message: Message) -> bool:
    """Проверяет что юзер зарегистрирован (есть в users.json)."""
    user_id = message.from_user.id

    if is_admin(user_id):
        return True

    user_data = get_user_by_id(user_id)
    if user_data:
        return True

    await message.answer(
        "⛔ <b>Вы не зарегистрированы в системе.</b>\n\n"
        "📌 Чтобы получить доступ ко всем кнопкам, подайте заявку через /apply",
        parse_mode="HTML"
    )
    logger.info(f"⛔ [КНОПКА] {user_id} не зарегистрирован — доступ заблокирован")
    return False


# ============================================================
# INLINE-КЛАВИАТУРЫ (для /apply)
# ============================================================

def create_seasons_keyboard(seasons: list, callback_prefix: str = "apply_season") -> InlineKeyboardMarkup:
    keyboard = []
    row = []
    for i, season in enumerate(seasons):
        row.append(InlineKeyboardButton(text=f"📂 {season}", callback_data=f"{callback_prefix}_{season}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="❌ Отменить", callback_data="apply_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def create_roles_keyboard(roles: list, season: str, callback_prefix: str = "apply_role") -> InlineKeyboardMarkup:
    keyboard = []
    for role in roles:
        status_emoji = "✅" if role.get('status') == 'free' else "❌" if role.get('status') == 'occupied' else "⏳"
        button_text = f"{status_emoji} {role['name']}"
        if role.get('status') == 'free':
            keyboard.append([InlineKeyboardButton(
                text=button_text,
                callback_data=f"{callback_prefix}_{season}_{role['name']}"
            )])
        else:
            keyboard.append([InlineKeyboardButton(
                text=f"{button_text} 🔒",
                callback_data="role_occupied"
            )])
    keyboard.append([InlineKeyboardButton(text="🔙 Назад к сезонам", callback_data="apply_back_to_seasons")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ============================================================
# INLINE CALLBACK-ОБРАБОТЧИКИ
# ============================================================

@router.callback_query(F.data == "apply_cancel")
async def cancel_apply(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "❌ Подача заявки отменена.\n\n"
        "Вы можете подать новую заявку через /apply"
    )


@router.callback_query(F.data == "apply_back_to_seasons")
async def back_to_seasons(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from .apply_handlers import cmd_apply
    await cmd_apply(callback.message, state)


@router.callback_query(F.data == "role_occupied")
async def role_occupied(callback: CallbackQuery):
    await callback.answer("❌ Эта роль уже занята или находится в обработке", show_alert=True)


# ============================================================
# REPLY-КЛАВИАТУРА
# ============================================================

def get_main_keyboard(user_id: int, chat_id: int = None):
    """Главная клавиатура. Для незарегистрированных — урезанная."""
    if chat_id == GENERAL_CHAT_ID:
        return None

    admin = is_admin(user_id)

    # Стартовый режим
    if not admin:
        user_data = get_user_by_id(user_id)
        if not user_data:
            return ReplyKeyboardMarkup(
                keyboard=[
                    [
                        KeyboardButton(text="📋 Помощь (/help)"),
                        KeyboardButton(text="📝 Информация (/about)")
                    ],
                    [
                        KeyboardButton(text="📌 Мои данные (/aboutme)"),
                        KeyboardButton(text="✅ Подать заявку (/apply)")
                    ],
                ],
                resize_keyboard=True,
                row_width=2
            )

    buttons = []

    buttons.append([
        KeyboardButton(text="📋 Помощь (/help)"),
        KeyboardButton(text="📝 Информация (/about)")
    ])
    buttons.append([
        KeyboardButton(text="📌 Мои данные (/aboutme)"),
        KeyboardButton(text="📜 Список ролей (/roles)")
    ])
    buttons.append([
        KeyboardButton(text="✅ Подать заявку (/apply)"),
        KeyboardButton(text="🔓 Освободить роль (/free)")
    ])
    buttons.append([
        KeyboardButton(text="⏳ Рест (/rest)"),
        KeyboardButton(text="📋 Список участников (/members)")
    ])

    if admin:
        buttons.append([
            KeyboardButton(text="👥 Список админов (/admins)"),
            KeyboardButton(text="👤 Список участников (/users)")
        ])
        buttons.append([
            KeyboardButton(text="📋 Заявки (/requests)"),
            KeyboardButton(text="📊 Статистика (/stats)")
        ])
        buttons.append([
            KeyboardButton(text="📢 Кал (/call)"),
            KeyboardButton(text="🔊 Кал-фал (/callfal)")
        ])
        buttons.append([
            KeyboardButton(text="👑 Кал-стафф (/callstaff)"),
            KeyboardButton(text="⏳ Список рестов (/restlist)")
        ])
        buttons.append([
            KeyboardButton(text="🔍 Проверка нормы (/checknorm)")
        ])

    buttons.append([
        KeyboardButton(text="🔕 Отписаться от калов (/unregc)"),
        KeyboardButton(text="🔔 Подписаться на калы (/regc)")
    ])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        row_width=2
    )


# ============================================================
# ОБРАБОТЧИКИ REPLY-КНОПОК
# ============================================================

@router.message(F.text == "📋 Помощь (/help)")
async def button_help(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    if not await _check_registration(message):
        return
    try:
        from .base_commands import cmd_help
        await cmd_help(message)
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Помощь: {e}")
        await message.answer("❌ Произошла ошибка.")


@router.message(F.text == "📝 Информация (/about)")
async def button_about(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    if not await _check_registration(message):
        return
    try:
        from .base_commands import cmd_about
        await cmd_about(message)
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Информация: {e}")
        await message.answer("❌ Произошла ошибка.")


@router.message(F.text == "📌 Мои данные (/aboutme)")
async def button_aboutme(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    if not await _check_registration(message):
        return
    try:
        from .base_commands import cmd_aboutme
        await cmd_aboutme(message)
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Мои данные: {e}")
        await message.answer("❌ Произошла ошибка.")


@router.message(F.text == "📜 Список ролей (/roles)")
async def button_roles(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    if not await _check_registration(message):
        return
    try:
        from .base_commands import cmd_roles
        await cmd_roles(message)
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Список ролей: {e}")
        await message.answer("❌ Произошла ошибка.")


@router.message(F.text == "✅ Подать заявку (/apply)")
async def button_apply(message: Message, state: FSMContext):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    try:
        from .apply_handlers import cmd_apply
        await cmd_apply(message, state)
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Подать заявку: {e}")
        await message.answer("❌ Произошла ошибка.")


@router.message(F.text == "🔓 Освободить роль (/free)")
async def button_free(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    if not await _check_registration(message):
        return
    try:
        from .apply_handlers import cmd_free
        await cmd_free(message)
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Освободить роль: {e}")
        await message.answer("❌ Произошла ошибка.")


@router.message(F.text == "⏳ Рест (/rest)")
async def button_rest(message: Message, state: FSMContext):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    if not await _check_registration(message):
        return
    try:
        from .rest_commands import cmd_rest
        await cmd_rest(message, state)
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Рест: {e}")
        await message.answer("❌ Произошла ошибка.")


@router.message(F.text == "📋 Список участников (/members)")
async def button_members(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    if not await _check_registration(message):
        return
    try:
        from .base_commands import cmd_members
        await cmd_members(message)
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Список участников: {e}")
        await message.answer("❌ Произошла ошибка.")


@router.message(F.text == "👥 Список админов (/admins)")
async def button_admins(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    if not await _check_registration(message):
        return
    try:
        from .admin_commands import cmd_admins
        await cmd_admins(message)
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Список админов: {e}")
        await message.answer("❌ Произошла ошибка.")


@router.message(F.text == "👤 Список участников (/users)")
async def button_users(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    if not await _check_registration(message):
        return
    try:
        from .admin_commands import cmd_users
        await cmd_users(message)
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Список участников: {e}")
        await message.answer("❌ Произошла ошибка.")


@router.message(F.text == "📋 Заявки (/requests)")
async def button_requests(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    if not await _check_registration(message):
        return
    try:
        from .request_commands import cmd_requests
        await cmd_requests(message)
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Заявки: {e}")
        await message.answer("❌ Произошла ошибка.")


@router.message(F.text == "📊 Статистика (/stats)")
async def button_stats(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    if not await _check_registration(message):
        return
    try:
        from .base_commands import cmd_stats
        await cmd_stats(message)
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Статистика: {e}")
        await message.answer("❌ Произошла ошибка.")


@router.message(F.text == "📢 Кал (/call)")
async def button_call(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    if not await _check_registration(message):
        return
    try:
        from .call_commands import cmd_call
        await cmd_call(message)
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Кал: {e}")
        await message.answer("❌ Произошла ошибка.")


@router.message(F.text == "🔊 Кал-фал (/callfal)")
async def button_callfal(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    if not await _check_registration(message):
        return
    try:
        from .call_commands import cmd_callfal
        await cmd_callfal(message)
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Кал-фал: {e}")
        await message.answer("❌ Произошла ошибка.")


@router.message(F.text == "👑 Кал-стафф (/callstaff)")
async def button_callstaff(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    if not await _check_registration(message):
        return
    try:
        from .call_commands import cmd_callstaff
        await cmd_callstaff(message)
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Кал-стафф: {e}")
        await message.answer("❌ Произошла ошибка.")


@router.message(F.text == "⏳ Список рестов (/restlist)")
async def button_restlist(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    if not await _check_registration(message):
        return
    try:
        from .rest_commands import cmd_restlist
        await cmd_restlist(message)
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Список рестов: {e}")
        await message.answer("❌ Произошла ошибка.")





@router.message(F.text == "🔕 Отписаться от калов (/unregc)")
async def button_unregc(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    if not await _check_registration(message):
        return
    try:
        from .call_commands import cmd_unregc
        await cmd_unregc(message)
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Отписаться: {e}")
        await message.answer("❌ Произошла ошибка.")


@router.message(F.text == "🔔 Подписаться на калы (/regc)")
async def button_regc(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    if not await _check_registration(message):
        return
    try:
        from .call_commands import cmd_regc
        await cmd_regc(message)
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Подписаться: {e}")
        await message.answer("❌ Произошла ошибка.")

@router.message(F.text == "🔍 Проверка нормы (/checknorm)")
async def button_checknorm(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    if not await _check_registration(message):
        return

    user_id = message.from_user.id
    logger.info(f"🔄 [КНОПКА] Проверка нормы от {user_id}")
    try:
        from .admin_commands import cmd_checknorm
        await cmd_checknorm(message)
        logger.info(f"✅ [КНОПКА] Проверка нормы выполнена для {user_id}")
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Ошибка в Проверка нормы от {user_id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")       