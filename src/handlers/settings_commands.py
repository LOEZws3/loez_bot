import os
import json
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import GENERAL_CHAT_ID
from utils.admin_utils import is_owner
from utils.role_utils import get_closed_mode, set_closed_mode
import asyncio

logger = logging.getLogger(__name__)
router = Router()

SETTINGS_FILE = "data/system_settings.json"


def load_settings():
    """Загружает настройки"""
    if not os.path.exists(SETTINGS_FILE):
        return {
            "closed_mode": False,
            "reminder_enabled": True,
            "max_rest_days": 14,
            "call_cooldown": 15,
            "callfal_cooldown": 30,
            "welcome_enabled": True,
            "auto_rest_removal": True,
            "forward_enabled": False,
            "anonymous_mode": False
        }
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "closed_mode": False,
            "reminder_enabled": True,
            "max_rest_days": 14,
            "call_cooldown": 15,
            "callfal_cooldown": 30,
            "welcome_enabled": True,
            "auto_rest_removal": True,
            "forward_enabled": False,
            "anonymous_mode": False
        }


def save_settings(settings):
    """Сохраняет настройки"""
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4)


@router.message(Command('settings'))
async def cmd_settings(message: Message):
    """Главное меню настроек (только для владельца)"""
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.answer("⛔ Доступ запрещён. Только для владельца.")
        return
    
    settings = load_settings()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{'✅' if not settings['closed_mode'] else '❌'} Набор ролей",
                callback_data="settings_toggle_closed"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅' if settings['reminder_enabled'] else '❌'} Напоминалка",
                callback_data="settings_toggle_reminder"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅' if settings['welcome_enabled'] else '❌'} Приветствие",
                callback_data="settings_toggle_welcome"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅' if settings['auto_rest_removal'] else '❌'} Авто-снятие реста",
                callback_data="settings_toggle_auto_rest"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"⏱️ Кулдаун кала: {settings['call_cooldown']}с",
                callback_data="settings_call_cooldown"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"⏱️ Кулдаун кал-фал: {settings['callfal_cooldown']}с",
                callback_data="settings_callfal_cooldown"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"📅 Макс. рест: {settings['max_rest_days']} дн.",
                callback_data="settings_max_rest"
            )
        ],
        [
            InlineKeyboardButton(text="📊 Показать все настройки", callback_data="settings_show_all")
        ],
        [
            InlineKeyboardButton(text="🔄 Сбросить настройки", callback_data="settings_reset"),
            InlineKeyboardButton(text="🔙 Закрыть", callback_data="settings_close")
        ]
    ])
    
    await message.answer(
        "⚙️ <b>Главное меню настроек</b>\n\n"
        "Нажмите на кнопку для изменения параметра.\n"
        "✅ — включено | ❌ — выключено",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("settings_"))
async def settings_callback(callback: CallbackQuery):
    """Обработка настроек"""
    await callback.answer()
    user_id = callback.from_user.id
    
    if not is_owner(user_id):
        await callback.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    settings = load_settings()
    action = callback.data.replace("settings_", "")
    
    if action == "toggle_closed":
        settings['closed_mode'] = not settings['closed_mode']
        save_settings(settings)
        # ✅ Используем функцию из role_utils
        set_closed_mode(settings['closed_mode'])
        await callback.answer(f"Набор ролей: {'открыт ✅' if not settings['closed_mode'] else 'закрыт ❌'}")
    
    elif action == "toggle_reminder":
        settings['reminder_enabled'] = not settings['reminder_enabled']
        save_settings(settings)
        await callback.answer(f"Напоминалка: {'включена ✅' if settings['reminder_enabled'] else 'выключена ❌'}")
    
    elif action == "toggle_welcome":
        settings['welcome_enabled'] = not settings['welcome_enabled']
        save_settings(settings)
        await callback.answer(f"Приветствие: {'включено ✅' if settings['welcome_enabled'] else 'выключено ❌'}")
    
    elif action == "toggle_auto_rest":
        settings['auto_rest_removal'] = not settings['auto_rest_removal']
        save_settings(settings)
        await callback.answer(f"Авто-снятие реста: {'включено ✅' if settings['auto_rest_removal'] else 'выключено ❌'}")
    
    elif action == "call_cooldown":
        await callback.message.answer(
            "⏱️ <b>Изменить кулдаун кала</b>\n\n"
            "Введите новое значение в секундах (от 5 до 120):",
            parse_mode="HTML"
        )
        await callback.message.delete()
        return
    
    elif action == "callfal_cooldown":
        await callback.message.answer(
            "⏱️ <b>Изменить кулдаун кал-фал</b>\n\n"
            "Введите новое значение в секундах (от 10 до 300):",
            parse_mode="HTML"
        )
        await callback.message.delete()
        return
    
    elif action == "max_rest":
        await callback.message.answer(
            "📅 <b>Изменить максимальную длительность реста</b>\n\n"
            "Введите новое значение в днях (от 1 до 30):",
            parse_mode="HTML"
        )
        await callback.message.delete()
        return
    
    elif action == "show_all":
        text = (
            "📊 <b>Текущие настройки</b>\n\n"
            f"🔒 Набор ролей: {'✅ Открыт' if not settings['closed_mode'] else '❌ Закрыт'}\n"
            f"📢 Напоминалка: {'✅ Включена' if settings['reminder_enabled'] else '❌ Выключена'}\n"
            f"👋 Приветствие: {'✅ Включено' if settings['welcome_enabled'] else '❌ Выключено'}\n"
            f"⏳ Авто-снятие реста: {'✅ Включено' if settings['auto_rest_removal'] else '❌ Выключено'}\n"
            f"⏱️ Кулдаун кала: {settings['call_cooldown']} сек\n"
            f"⏱️ Кулдаун кал-фал: {settings['callfal_cooldown']} сек\n"
            f"📅 Макс. рест: {settings['max_rest_days']} дн."
        )
        await callback.message.answer(text, parse_mode="HTML")
        return
    
    elif action == "reset":
        default_settings = {
            "closed_mode": False,
            "reminder_enabled": True,
            "max_rest_days": 14,
            "call_cooldown": 15,
            "callfal_cooldown": 30,
            "welcome_enabled": True,
            "auto_rest_removal": True,
            "forward_enabled": False,
            "anonymous_mode": False
        }
        save_settings(default_settings)
        set_closed_mode(False)
        await callback.answer("✅ Настройки сброшены!")
    
    elif action == "close":
        await callback.message.delete()
        await callback.message.answer("🔙 Настройки закрыты.")
        return
    
    # Обновляем меню
    await cmd_settings(callback.message)


@router.message(F.text.regexp(r'^\d+$'))
async def settings_value_input(message: Message):
    """Обработка ввода числовых значений для настроек"""
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        return
    
    value = int(message.text)
    settings = load_settings()
    
    if 5 <= value <= 120:
        settings['call_cooldown'] = value
        save_settings(settings)
        await message.answer(f"✅ Кулдаун кала изменён на {value} сек.")
    elif 10 <= value <= 300:
        settings['callfal_cooldown'] = value
        save_settings(settings)
        await message.answer(f"✅ Кулдаун кал-фал изменён на {value} сек.")
    elif 1 <= value <= 30:
        settings['max_rest_days'] = value
        save_settings(settings)
        await message.answer(f"✅ Макс. рест изменён на {value} дн.")
    else:
        await message.answer("❌ Значение вне допустимого диапазона.")