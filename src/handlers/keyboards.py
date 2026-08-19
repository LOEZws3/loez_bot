from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from utils.admin_utils import is_admin, is_owner
from config import GENERAL_CHAT_ID
from aiogram import Router

router = Router()

def get_main_keyboard(user_id: int, chat_id: int = None):
    """Возвращает клавиатуру, если чат не является флуд-чатом"""
    # Если это флуд-чат — возвращаем None (клавиатура не показывается)
    if chat_id is not None and chat_id == GENERAL_CHAT_ID:
        return None

    buttons = [
        [KeyboardButton(text="📚 Помощь"), KeyboardButton(text="ℹ️ О чате")],
        [KeyboardButton(text="👤 Мои данные")],
        [KeyboardButton(text="📝 Подать заявку")],
        [KeyboardButton(text="🔄 Освободить роль")],
        [KeyboardButton(text="❌ Отменить заявку")]
    ]

    if is_admin(user_id):
        buttons.append([KeyboardButton(text="👥 Список админов")])
        buttons.append([KeyboardButton(text="👥 Список участников")])
        buttons.append([KeyboardButton(text="📢 Рассылка")])
        buttons.append([KeyboardButton(text="🔊 Сделать кал")])

        if is_owner(user_id):
            buttons.append([KeyboardButton(text="🔒 Закрыть набор"), KeyboardButton(text="🔓 Открыть набор")])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )


def get_inline_menu(user_id: int, chat_id: int = None):
    """Возвращает инлайн-меню, если чат не является флуд-чатом"""
    if chat_id is not None and chat_id == GENERAL_CHAT_ID:
        return None

    buttons = [
        [InlineKeyboardButton(text="📚 Помощь", callback_data="help")],
        [InlineKeyboardButton(text="ℹ️ О чате", callback_data="about")],
        [InlineKeyboardButton(text="👤 Мои данные", callback_data="aboutme")],
    ]

    if is_admin(user_id):
        buttons.append([InlineKeyboardButton(text="👥 Список админов", callback_data="admins")])
        buttons.append([InlineKeyboardButton(text="👥 Список участников", callback_data="users")])
        buttons.append([InlineKeyboardButton(text="📢 Рассылка", callback_data="broadcast")])

        if is_owner(user_id):
            buttons.append([
                InlineKeyboardButton(text="🔒 Закрыть набор", callback_data="close"),
                InlineKeyboardButton(text="🔓 Открыть набор", callback_data="open")
            ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)