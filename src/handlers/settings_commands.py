import os
import json
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import GENERAL_CHAT_ID, DATA_DIR
from utils.admin_utils import is_owner
from utils.role_utils import get_closed_mode, set_closed_mode
from utils.settings_utils import (
    load_settings, save_settings, reset_settings,
    DEFAULT_SETTINGS,
)

logger = logging.getLogger(__name__)
router = Router()


class WaitingForSetting(StatesGroup):
    value = State()


# ======================== МЕНЮ ========================

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
            InlineKeyboardButton(
                text=f"🔄 Макс. смен роли: {settings.get('max_role_changes', 1)}",
                callback_data="settings_max_role_changes"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"📊 Норма сообщений: {settings.get('messages_norm', 70)}",
                callback_data="settings_messages_norm"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"📉 НПНДБ: {settings.get('messages_norm_low', 10)}",
                callback_data="settings_messages_norm_low"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅' if settings.get('warns_accumulate', False) else '❌'} Накопление варнов",
                callback_data="settings_toggle_warns_accumulate"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🔢 Варнов до бана: {settings.get('warns_to_ban', 3)}",
                callback_data="settings_warns_to_ban"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅' if settings.get('warn_notify_admin', True) else '❌'} Уведомлять о 3-м варне",
                callback_data="settings_toggle_warn_notify"
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


# ======================== ОБРАБОТКА НАЖАТИЙ ========================

@router.callback_query(F.data.startswith("settings_"))
async def settings_callback(callback: CallbackQuery, state: FSMContext):
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

    elif action == "toggle_warns_accumulate":
        settings['warns_accumulate'] = not settings.get('warns_accumulate', False)
        save_settings(settings)
        await callback.answer(f"Накопление варнов: {'включено ✅' if settings['warns_accumulate'] else 'выключено ❌'}")

    elif action == "toggle_warn_notify":
        settings['warn_notify_admin'] = not settings.get('warn_notify_admin', True)
        save_settings(settings)
        await callback.answer(f"Уведомлять о 3-м варне: {'вкл ✅' if settings['warn_notify_admin'] else 'выкл ❌'}")

    elif action == "call_cooldown":
        await state.set_state(WaitingForSetting.value)
        await state.update_data(setting_name='call_cooldown')
        await callback.message.answer(
            "⏱️ <b>Изменить кулдаун кала</b>\n\n"
            "Введите новое значение в секундах (от 5 до 120):",
            parse_mode="HTML"
        )
        await callback.message.delete()
        return

    elif action == "callfal_cooldown":
        await state.set_state(WaitingForSetting.value)
        await state.update_data(setting_name='callfal_cooldown')
        await callback.message.answer(
            "⏱️ <b>Изменить кулдаун кал-фал</b>\n\n"
            "Введите новое значение в секундах (от 10 до 300):",
            parse_mode="HTML"
        )
        await callback.message.delete()
        return

    elif action == "max_rest":
        await state.set_state(WaitingForSetting.value)
        await state.update_data(setting_name='max_rest_days')
        await callback.message.answer(
            "📅 <b>Изменить максимальную длительность реста</b>\n\n"
            "Введите новое значение в днях (от 1 до 30):",
            parse_mode="HTML"
        )
        await callback.message.delete()
        return

    elif action == "max_role_changes":
        await state.set_state(WaitingForSetting.value)
        await state.update_data(setting_name='max_role_changes')
        await callback.message.answer(
            "🔄 <b>Изменить максимальное количество смен роли</b>\n\n"
            "Введите новое значение (от 0 до 20):\n"
            "0 — смены роли запрещены",
            parse_mode="HTML"
        )
        await callback.message.delete()
        return

    elif action == "messages_norm":
        await state.set_state(WaitingForSetting.value)
        await state.update_data(setting_name='messages_norm')
        await callback.message.answer(
            "📊 <b>Изменить норму сообщений в неделю</b>\n\n"
            "Введите новое значение (от 1 до 1000):",
            parse_mode="HTML"
        )
        await callback.message.delete()
        return

    elif action == "messages_norm_low":
        await state.set_state(WaitingForSetting.value)
        await state.update_data(setting_name='messages_norm_low')
        await callback.message.answer(
            "📉 <b>Изменить НПНДБ</b>\n\n"
            "Нижний порог для бана.\n"
            "Введите новое значение (от 1 до 1000):",
            parse_mode="HTML"
        )
        await callback.message.delete()
        return

    elif action == "warns_to_ban":
        await state.set_state(WaitingForSetting.value)
        await state.update_data(setting_name='warns_to_ban')
        await callback.message.answer(
            "🔢 <b>Изменить количество варнов до бана</b>\n\n"
            "Введите новое значение (от 1 до 10):",
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
            f"📅 Макс. рест: {settings['max_rest_days']} дн.\n"
            f"🔄 Макс. смен роли: {settings.get('max_role_changes', 1)}\n\n"
            f"📊 <b>НОРМА И ЧИСТКА:</b>\n"
            f"📊 Норма сообщений: {settings.get('messages_norm', 70)}\n"
            f"📉 НПНДБ: {settings.get('messages_norm_low', 10)}\n"
            f"{'✅' if settings.get('warns_accumulate', False) else '❌'} Накопление варнов\n"
            f"🔢 Варнов до бана: {settings.get('warns_to_ban', 3)}\n"
            f"{'✅' if settings.get('warn_notify_admin', True) else '❌'} Уведомлять о 3-м варне"
        )
        await callback.message.answer(text, parse_mode="HTML")
        return

    elif action == "reset":
        reset_settings()
        set_closed_mode(False)
        await callback.answer("✅ Настройки сброшены!")

    elif action == "close":
        await state.clear()
        await callback.message.delete()
        await callback.message.answer("🔙 Настройки закрыты.")
        return

    await cmd_settings(callback.message)


# ======================== ВВОД ЧИСЛА ========================

@router.message(WaitingForSetting.value, F.text.regexp(r'^\d+$'))
async def settings_value_input(message: Message, state: FSMContext):
    user_id = message.from_user.id

    if not is_owner(user_id):
        await state.clear()
        return

    data = await state.get_data()
    setting_name = data.get('setting_name')

    if not setting_name:
        await state.clear()
        return

    value = int(message.text)
    settings = load_settings()

    if setting_name == 'call_cooldown':
        if 5 <= value <= 120:
            settings['call_cooldown'] = value
            save_settings(settings)
            await message.answer(f"✅ Кулдаун кала изменён на {value} сек.")
        else:
            await message.answer("❌ Значение вне диапазона (5-120).")

    elif setting_name == 'callfal_cooldown':
        if 10 <= value <= 300:
            settings['callfal_cooldown'] = value
            save_settings(settings)
            await message.answer(f"✅ Кулдаун кал-фал изменён на {value} сек.")
        else:
            await message.answer("❌ Значение вне диапазона (10-300).")

    elif setting_name == 'max_rest_days':
        if 1 <= value <= 30:
            settings['max_rest_days'] = value
            save_settings(settings)
            await message.answer(f"✅ Макс. рест изменён на {value} дн.")
        else:
            await message.answer("❌ Значение вне диапазона (1-30).")

    elif setting_name == 'max_role_changes':
        if 0 <= value <= 20:
            settings['max_role_changes'] = value
            save_settings(settings)
            await message.answer(f"✅ Макс. смен роли изменён на {value}.")
        else:
            await message.answer("❌ Значение вне диапазона (0-20).")

    elif setting_name == 'messages_norm':
        if 1 <= value <= 1000:
            settings['messages_norm'] = value
            save_settings(settings)
            await message.answer(f"✅ Норма сообщений изменена на {value}.")
        else:
            await message.answer("❌ Значение вне диапазона (1-1000).")

    elif setting_name == 'messages_norm_low':
        if 1 <= value <= 1000:
            settings['messages_norm_low'] = value
            save_settings(settings)
            await message.answer(f"✅ НПНДБ изменён на {value}.")
        else:
            await message.answer("❌ Значение вне диапазона (1-1000).")

    elif setting_name == 'warns_to_ban':
        if 1 <= value <= 10:
            settings['warns_to_ban'] = value
            save_settings(settings)
            await message.answer(f"✅ Варнов до бана: {value}.")
        else:
            await message.answer("❌ Значение вне диапазона (1-10).")

    await state.clear()


@router.message(WaitingForSetting.value, Command('cancel'))
async def cancel_setting(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Ввод настройки отменён.")