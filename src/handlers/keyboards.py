# ============================================================
# ⚠️ ВАЖНОЕ ПРАВИЛО ДЛЯ КЛАВИАТУРЫ
# ============================================================
# 
# Во флуд-чате (GENERAL_CHAT_ID) клавиатура НЕ ПОКАЗЫВАЕТСЯ!
# Все кнопки и меню должны быть доступны ТОЛЬКО в личных сообщениях с ботом.
# 
# Причина: во флуде бот должен отвечать только текстом,
# без интерактивных элементов, чтобы не засорять чат.
# ============================================================

import os
import json
import logging
from aiogram import Router, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from config import GENERAL_CHAT_ID
from utils.admin_utils import is_admin
from utils.user_utils import get_user_by_id

logger = logging.getLogger(__name__)
router = Router()

def create_seasons_keyboard(seasons: list, callback_prefix: str = "apply_season") -> InlineKeyboardMarkup:
    """Создает клавиатуру с сезонами"""
    keyboard = []
    row = []
    
    for i, season in enumerate(seasons):
        row.append(InlineKeyboardButton(text=f"📂 {season}", callback_data=f"{callback_prefix}_{season}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    # Кнопка "Назад" или "Отмена"
    keyboard.append([
        InlineKeyboardButton(text="❌ Отменить", callback_data="apply_cancel")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_roles_keyboard(roles: list, season: str, callback_prefix: str = "apply_role") -> InlineKeyboardMarkup:
    """Создает клавиатуру с ролями для выбранного сезона"""
    keyboard = []
    
    for role in roles:
        status_emoji = "✅" if role.get('status') == 'free' else "❌" if role.get('status') == 'occupied' else "⏳"
        button_text = f"{status_emoji} {role['name']}"
        
        if role.get('status') == 'free':
            keyboard.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"{callback_prefix}_{season}_{role['name']}"
                )
            ])
        else:
            # Занятые роли показываем, но они неактивны
            keyboard.append([
                InlineKeyboardButton(
                    text=f"{button_text} 🔒",
                    callback_data="role_occupied"
                )
            ])
    
    # Кнопка "Назад"
    keyboard.append([
        InlineKeyboardButton(text="🔙 Назад к сезонам", callback_data="apply_back_to_seasons")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.callback_query(F.data == "apply_cancel")
async def cancel_apply(callback: CallbackQuery):
    """Отмена подачи заявки"""
    await callback.answer()
    await callback.message.edit_text(
        "❌ Подача заявки отменена.\n\n"
        "Вы можете подать новую заявку через /apply"
    )

@router.callback_query(F.data == "apply_back_to_seasons")
async def back_to_seasons(callback: CallbackQuery):
    """Возврат к списку сезонов"""
    await callback.answer()
    await cmd_apply(callback.message)

@router.callback_query(F.data == "role_occupied")
async def role_occupied(callback: CallbackQuery):
    """Ответ на нажатие занятой роли"""
    await callback.answer("❌ Эта роль уже занята или находится в обработке", show_alert=True)

def get_main_keyboard(user_id: int, chat_id: int = None):
    """
    Главная клавиатура для бота.
    
    ⚠️ ВО ФЛУД-ЧАТЕ (GENERAL_CHAT_ID) ВОЗВРАЩАЕТ None
    Клавиатура показывается ТОЛЬКО в личных сообщениях!
    """
    # ✅ Если это флуд-чат — НЕ ПОКАЗЫВАЕМ клавиатуру
    if chat_id == GENERAL_CHAT_ID:
        return None
    
    admin = is_admin(user_id)
    
    buttons = []
    
    # Кнопки для всех
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
    
    # Админские кнопки
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
            KeyboardButton(text="⏳ Список рестов (/restlist)")
        ])
    
    # Кнопка отписки/подписки на калы (для всех)
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
# ОБРАБОТЧИКИ КНОПОК (ИГНОРИРУЮТСЯ ВО ФЛУДЕ)
# ============================================================

@router.message(F.text == "📋 Помощь (/help)")
async def button_help(message: Message):
    # ✅ Если во флуде — игнорируем
    if message.chat.id == GENERAL_CHAT_ID:
        return
    
    user_id = message.from_user.id
    logger.info(f"🔄 [КНОПКА] Помощь от {user_id}")
    try:
        from .base_commands import cmd_help
        await cmd_help(message)
        logger.info(f"✅ [КНОПКА] Помощь выполнена для {user_id}")
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Ошибка в Помощь от {user_id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(F.text == "📝 Информация (/about)")
async def button_about(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    
    user_id = message.from_user.id
    logger.info(f"🔄 [КНОПКА] Информация от {user_id}")
    try:
        from .base_commands import cmd_about
        await cmd_about(message)
        logger.info(f"✅ [КНОПКА] Информация выполнена для {user_id}")
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Ошибка в Информация от {user_id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(F.text == "📌 Мои данные (/aboutme)")
async def button_aboutme(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    
    user_id = message.from_user.id
    logger.info(f"🔄 [КНОПКА] Мои данные от {user_id}")
    try:
        from .base_commands import cmd_aboutme
        await cmd_aboutme(message)
        logger.info(f"✅ [КНОПКА] Мои данные выполнены для {user_id}")
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Ошибка в Мои данные от {user_id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(F.text == "📜 Список ролей (/roles)")
async def button_roles(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    
    user_id = message.from_user.id
    logger.info(f"🔄 [КНОПКА] Список ролей от {user_id}")
    try:
        from .base_commands import cmd_roles
        await cmd_roles(message)
        logger.info(f"✅ [КНОПКА] Список ролей выполнена для {user_id}")
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Ошибка в Список ролей от {user_id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(F.text == "✅ Подать заявку (/apply)")
async def button_apply(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    
    user_id = message.from_user.id
    logger.info(f"🔄 [КНОПКА] Подать заявку от {user_id}")
    try:
        from .role_commands import cmd_apply
        await cmd_apply(message)
        logger.info(f"✅ [КНОПКА] Подать заявку выполнена для {user_id}")
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Ошибка в Подать заявку от {user_id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(F.text == "🔓 Освободить роль (/free)")
async def button_free(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    
    user_id = message.from_user.id
    logger.info(f"🔄 [КНОПКА] Освободить роль от {user_id}")
    try:
        from .role_commands import cmd_free
        await cmd_free(message, None)
        logger.info(f"✅ [КНОПКА] Освободить роль выполнена для {user_id}")
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Ошибка в Освободить роль от {user_id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(F.text == "⏳ Рест (/rest)")
async def button_rest(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    
    user_id = message.from_user.id
    logger.info(f"🔄 [КНОПКА] Рест от {user_id}")
    try:
        from .rest_commands import cmd_rest
        await cmd_rest(message, None)
        logger.info(f"✅ [КНОПКА] Рест выполнена для {user_id}")
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Ошибка в Рест от {user_id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(F.text == "📋 Список участников (/members)")
async def button_members(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    
    user_id = message.from_user.id
    logger.info(f"🔄 [КНОПКА] Список участников от {user_id}")
    try:
        from .base_commands import cmd_members
        await cmd_members(message)
        logger.info(f"✅ [КНОПКА] Список участников выполнена для {user_id}")
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Ошибка в Список участников от {user_id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(F.text == "👥 Список админов (/admins)")
async def button_admins(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    
    user_id = message.from_user.id
    logger.info(f"🔄 [КНОПКА] Список админов от {user_id}")
    try:
        from .admin_commands import cmd_admins
        await cmd_admins(message)
        logger.info(f"✅ [КНОПКА] Список админов выполнена для {user_id}")
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Ошибка в Список админов от {user_id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(F.text == "👤 Список участников (/users)")
async def button_users(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    
    user_id = message.from_user.id
    logger.info(f"🔄 [КНОПКА] Список участников от {user_id}")
    try:
        from .admin_commands import cmd_users
        await cmd_users(message)
        logger.info(f"✅ [КНОПКА] Список участников выполнена для {user_id}")
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Ошибка в Список участников от {user_id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(F.text == "📋 Заявки (/requests)")
async def button_requests(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    
    user_id = message.from_user.id
    logger.info(f"🔄 [КНОПКА] Заявки от {user_id}")
    try:
        from .request_commands import cmd_requests
        await cmd_requests(message)
        logger.info(f"✅ [КНОПКА] Заявки выполнена для {user_id}")
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Ошибка в Заявки от {user_id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(F.text == "📊 Статистика (/stats)")
async def button_stats(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    
    user_id = message.from_user.id
    logger.info(f"🔄 [КНОПКА] Статистика от {user_id}")
    try:
        from .base_commands import cmd_stats
        await cmd_stats(message)
        logger.info(f"✅ [КНОПКА] Статистика выполнена для {user_id}")
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Ошибка в Статистика от {user_id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(F.text == "📢 Кал (/call)")
async def button_call(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    
    user_id = message.from_user.id
    logger.info(f"🔄 [КНОПКА] Кал от {user_id}")
    try:
        from .call_commands import cmd_call
        await cmd_call(message)
        logger.info(f"✅ [КНОПКА] Кал выполнена для {user_id}")
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Ошибка в Кал от {user_id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(F.text == "🔊 Кал-фал (/callfal)")
async def button_callfal(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    
    user_id = message.from_user.id
    logger.info(f"🔄 [КНОПКА] Кал-фал от {user_id}")
    try:
        from .call_commands import cmd_callfal
        await cmd_callfal(message)
        logger.info(f"✅ [КНОПКА] Кал-фал выполнена для {user_id}")
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Ошибка в Кал-фал от {user_id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(F.text == "⏳ Список рестов (/restlist)")
async def button_restlist(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    
    user_id = message.from_user.id
    logger.info(f"🔄 [КНОПКА] Список рестов от {user_id}")
    try:
        from .rest_commands import cmd_restlist
        await cmd_restlist(message)
        logger.info(f"✅ [КНОПКА] Список рестов выполнена для {user_id}")
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Ошибка в Список рестов от {user_id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(F.text == "🔕 Отписаться от калов (/unregc)")
async def button_unregc(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    
    user_id = message.from_user.id
    logger.info(f"🔄 [КНОПКА] Отписаться от калов от {user_id}")
    try:
        from .call_commands import cmd_unregc
        await cmd_unregc(message)
        logger.info(f"✅ [КНОПКА] Отписаться от калов выполнена для {user_id}")
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Ошибка в Отписаться от калов от {user_id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(F.text == "🔔 Подписаться на калы (/regc)")
async def button_regc(message: Message):
    if message.chat.id == GENERAL_CHAT_ID:
        return
    
    user_id = message.from_user.id
    logger.info(f"🔄 [КНОПКА] Подписаться на калы от {user_id}")
    try:
        from .call_commands import cmd_regc
        await cmd_regc(message)
        logger.info(f"✅ [КНОПКА] Подписаться на калы выполнена для {user_id}")
    except Exception as e:
        logger.error(f"❌ [КНОПКА] Ошибка в Подписаться на калы от {user_id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")