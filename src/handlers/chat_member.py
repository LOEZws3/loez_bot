import os
import logging
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import ChatMemberUpdated

from config import DATA_PATH, GENERAL_CHAT_ID

logger = logging.getLogger(__name__)
router = Router()

# Счетчик сообщений для незарегистрированных пользователей
message_counter = {}

def get_message_count(user_id: int) -> int:
    return message_counter.get(user_id, 0)

def set_message_count(user_id: int, count: int):
    message_counter[user_id] = count

def check_user_registration(user_id: int) -> bool:
    """Проверяет, есть ли пользователь в data/users/users.txt"""
    try:
        users_file = os.path.join(DATA_PATH, 'users', 'users.txt')
        if not os.path.exists(users_file):
            logger.error(f"Файл {users_file} не найден!")
            return False
        
        with open(users_file, 'r', encoding='utf-8') as f:
            for line in f:
                if str(user_id) in line:
                    return True
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке пользователя {user_id}: {e}")
        return False

@router.message()
async def handle_message(message: types.Message):
    """Обработчик всех сообщений"""
    if message.chat.type in ['group', 'supergroup']:
        if message.chat.id != GENERAL_CHAT_ID:
            return
    
    user_id = message.from_user.id
    
    if not check_user_registration(user_id):
        count = get_message_count(user_id) + 1
        set_message_count(user_id, count)
        
        if count % 5 == 0:
            try:
                await message.reply(
                    "👤 Chedrik SSL, я вижу вас в системе, но ваши данные не обновлены!\n\n"
                    "📌 Пожалуйста, обновите свои данные через бота:\n"
                    "👉 @REG_sf_BOT\n\n"
                    "Или зарегистрируйтесь через команду /apply в личных сообщениях с ботом.",
                    disable_notification=True
                )
                logger.info(f"📨 Напоминание отправлено пользователю {user_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки: {e}")
    else:
        if user_id in message_counter:
            message_counter[user_id] = 0

@router.my_chat_member()
async def on_user_join(update: ChatMemberUpdated):
    """Приветствие новых пользователей"""
    if update.chat.id != GENERAL_CHAT_ID:
        return
    
    if update.new_chat_member.status not in ['member', 'administrator', 'creator']:
        return
    
    if update.old_chat_member.status in ['member', 'administrator', 'creator']:
        return
    
    user = update.new_chat_member.user
    user_id = user.id
    
    if not check_user_registration(user_id):
        try:
            await update.bot.send_message(
                chat_id=update.chat.id,
                text=f"👋 Привет, {user.first_name}!\n\n"
                     f"❗ Для полного доступа зарегистрируйтесь:\n"
                     f"1. Напишите @loez_bot в личку\n"
                     f"2. Используйте команду /apply",
                disable_notification=True
            )
            logger.info(f"📨 Приветствие отправлено {user_id}")
        except Exception as e:
            logger.error(f"Ошибка приветствия: {e}")

__all__ = ['router']