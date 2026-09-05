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

# Файл для хранения состояния пересылки
FORWARD_SETTINGS_FILE = "data/system/forward_settings.json"


def load_forward_settings():
    """Загружает настройки пересылки"""
    os.makedirs(os.path.dirname(FORWARD_SETTINGS_FILE), exist_ok=True)
    try:
        with open(FORWARD_SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"forward_enabled": True, "anonymous_mode": False}


def save_forward_settings(settings):
    """Сохраняет настройки пересылки"""
    os.makedirs(os.path.dirname(FORWARD_SETTINGS_FILE), exist_ok=True)
    with open(FORWARD_SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4)


def get_main_keyboard(user_id: int, chat_id: int = None):
    """Главная клавиатура для бота"""
    # Проверяем, является ли пользователь админом
    admin = is_admin(user_id)
    
    # Проверяем, находимся ли во флуд-чате
    is_flood = (chat_id == GENERAL_CHAT_ID)
    
    # Получаем настройки пересылки
    settings = load_forward_settings()
    forward_status = "✅ Включена" if settings.get("forward_enabled", True) else "❌ Отключена"
    anonymous_status = "✅ Вкл" if settings.get("anonymous_mode", False) else "❌ Выкл"
    
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
            KeyboardButton(text="⏳ Список рестов (/restlist)"),
            KeyboardButton(text="🔧 Настройки пересылки (/forward_settings)")
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
# НАСТРОЙКИ ПЕРЕСЫЛКИ (КОМАНДЫ И КНОПКИ)
# ============================================================

@router.message(Command("forward_settings"))
async def cmd_forward_settings(message: Message):
    """Настройки пересылки сообщений (только для админов)"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён. Только для администраторов.")
        return
    
    settings = load_forward_settings()
    forward_enabled = settings.get("forward_enabled", True)
    anonymous_mode = settings.get("anonymous_mode", False)
    
    status_emoji = "✅" if forward_enabled else "❌"
    anonymous_emoji = "✅" if anonymous_mode else "❌"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{status_emoji} Пересылка сообщений",
                callback_data="toggle_forward"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{anonymous_emoji} Анонимный режим (для админов)",
                callback_data="toggle_anonymous"
            )
        ],
        [
            InlineKeyboardButton(text="🔙 Закрыть", callback_data="close_forward_settings")
        ]
    ])
    
    await message.answer(
        f"⚙️ <b>Настройки пересылки сообщений</b>\n\n"
        f"📨 Пересылка: <b>{'Включена' if forward_enabled else 'Отключена'}</b>\n"
        f"🕵️ Анонимный режим: <b>{'Включён' if anonymous_mode else 'Отключён'}</b>\n\n"
        f"🔹 <b>Пересылка</b> — включает/отключает пересылку сообщений в админ-группу\n"
        f"🔹 <b>Анонимный режим</b> — скрывает имя отправителя для админов",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "toggle_forward")
async def toggle_forward(callback: CallbackQuery):
    """Вкл/Выкл пересылки сообщений"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    settings = load_forward_settings()
    settings["forward_enabled"] = not settings.get("forward_enabled", True)
    save_forward_settings(settings)
    
    status = "включена" if settings["forward_enabled"] else "отключена"
    await callback.answer(f"✅ Пересылка {status}")
    await cmd_forward_settings(callback.message)
    await callback.message.delete()
    await cmd_forward_settings(callback.message)


@router.callback_query(F.data == "toggle_anonymous")
async def toggle_anonymous(callback: CallbackQuery):
    """Вкл/Выкл анонимного режима"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    settings = load_forward_settings()
    settings["anonymous_mode"] = not settings.get("anonymous_mode", False)
    save_forward_settings(settings)
    
    status = "включён" if settings["anonymous_mode"] else "отключён"
    await callback.answer(f"✅ Анонимный режим {status}")
    await cmd_forward_settings(callback.message)
    await callback.message.delete()
    await cmd_forward_settings(callback.message)


@router.callback_query(F.data == "close_forward_settings")
async def close_forward_settings(callback: CallbackQuery):
    """Закрывает настройки"""
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer("🔙 Настройки закрыты.")


# ============================================================
# ИСПРАВЛЕННЫЕ ОБРАБОТЧИКИ КНОПОК (ДЛЯ ВСЕХ КОМАНД)
# ============================================================

@router.message(F.text == "📋 Помощь (/help)")
async def button_help(message: Message):
    """Кнопка Помощь"""
    from .base_commands import cmd_help
    await cmd_help(message)


@router.message(F.text == "📝 Информация (/about)")
async def button_about(message: Message):
    """Кнопка Информация"""
    from .base_commands import cmd_about
    await cmd_about(message)


@router.message(F.text == "📌 Мои данные (/aboutme)")
async def button_aboutme(message: Message):
    """Кнопка Мои данные"""
    from .base_commands import cmd_aboutme
    await cmd_aboutme(message)


@router.message(F.text == "📜 Список ролей (/roles)")
async def button_roles(message: Message):
    """Кнопка Список ролей"""
    from .base_commands import cmd_roles
    await cmd_roles(message)


@router.message(F.text == "✅ Подать заявку (/apply)")
async def button_apply(message: Message):
    """Кнопка Подать заявку"""
    from .role_commands import cmd_apply
    await cmd_apply(message)


@router.message(F.text == "🔓 Освободить роль (/free)")
async def button_free(message: Message, state):
    """Кнопка Освободить роль"""
    from .role_commands import cmd_free
    await cmd_free(message, state)


@router.message(F.text == "⏳ Рест (/rest)")
async def button_rest(message: Message, state):
    """Кнопка Рест"""
    from .rest_commands import cmd_rest
    await cmd_rest(message, state)


@router.message(F.text == "📋 Список участников (/members)")
async def button_members(message: Message):
    """Кнопка Список участников"""
    from .base_commands import cmd_members
    await cmd_members(message)


@router.message(F.text == "👥 Список админов (/admins)")
async def button_admins(message: Message):
    """Кнопка Список админов"""
    from .admin_commands import cmd_admins
    await cmd_admins(message)


@router.message(F.text == "👤 Список участников (/users)")
async def button_users(message: Message):
    """Кнопка Список участников"""
    from .admin_commands import cmd_users
    await cmd_users(message)


@router.message(F.text == "📋 Заявки (/requests)")
async def button_requests(message: Message):
    """Кнопка Заявки"""
    from .request_commands import cmd_requests
    await cmd_requests(message)


@router.message(F.text == "📊 Статистика (/stats)")
async def button_stats(message: Message):
    """Кнопка Статистика"""
    from .base_commands import cmd_stats
    await cmd_stats(message)


@router.message(F.text == "📢 Кал (/call)")
async def button_call(message: Message):
    """Кнопка Кал"""
    from .call_commands import cmd_call
    await cmd_call(message)


@router.message(F.text == "🔊 Кал-фал (/callfal)")
async def button_callfal(message: Message):
    """Кнопка Кал-фал"""
    from .call_commands import cmd_callfal
    await cmd_callfal(message)


@router.message(F.text == "⏳ Список рестов (/restlist)")
async def button_restlist(message: Message):
    """Кнопка Список рестов"""
    from .rest_commands import cmd_restlist
    await cmd_restlist(message)


@router.message(F.text == "🔧 Настройки пересылки (/forward_settings)")
async def button_forward_settings(message: Message):
    """Кнопка Настройки пересылки"""
    await cmd_forward_settings(message)


@router.message(F.text == "🔕 Отписаться от калов (/unregc)")
async def button_unregc(message: Message):
    """Кнопка Отписаться от калов"""
    from .call_commands import cmd_unregc
    await cmd_unregc(message)


@router.message(F.text == "🔔 Подписаться на калы (/regc)")
async def button_regc(message: Message):
    """Кнопка Подписаться на калы"""
    from .call_commands import cmd_regc
    await cmd_regc(message)