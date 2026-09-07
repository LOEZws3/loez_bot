import os
import logging
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import ChatMemberUpdated

from config import DATA_DIR, GENERAL_CHAT_ID

logger = logging.getLogger(__name__)
router = Router()

# Счетчик сообщений для незарегистрированных пользователей
message_counter = {}

def get_message_count(user_id: int) -> int:
    return message_counter.get(user_id, 0)

def set_message_count(user_id: int, count: int):
    message_counter[user_id] = count

def check_user_registration(user_id: int) -> bool:
    """
    Проверяет, есть ли пользователь в data/users/users.txt
    Использует абсолютный путь для точности
    """
    try:
        # Получаем абсолютный путь к корню проекта
        # BASE_DIR = C:\Users\olika\PyCharmMiscProject\LoEZF_Bot
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Абсолютный путь к файлу users.txt
        users_file = os.path.join(base_dir, 'data', 'users', 'users.txt')
        
        # Для отладки выводим путь в лог
        logger.info(f"🔍 Поиск пользователя в файле: {users_file}")
        
        if not os.path.exists(users_file):
            logger.error(f"❌ Файл {users_file} не найден!")
            return False
        
        with open(users_file, 'r', encoding='utf-8') as f:
            for line in f:
                # Ищем ID в начале строки (формат: ID|username|...)
                if line.startswith(str(user_id) + '|'):
                    logger.info(f"✅ Пользователь {user_id} найден в файле")
                    return True
        
        logger.info(f"❌ Пользователь {user_id} НЕ найден в файле")
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке пользователя {user_id}: {e}")
        return False

@router.message()
async def handle_message(message: types.Message):
    """Обработчик всех сообщений"""
    # Игнорируем сообщения из групп, кроме основного чата
    if message.chat.type in ['group', 'supergroup']:
        if message.chat.id != GENERAL_CHAT_ID:
            return
    
    user_id = message.from_user.id
    
    # Проверяем, зарегистрирован ли пользователь
    if not check_user_registration(user_id):
        # Увеличиваем счетчик сообщений для незарегистрированного пользователя
        count = get_message_count(user_id) + 1
        set_message_count(user_id, count)
        
        # Если каждое 5-е сообщение, отправляем напоминание
        if count % 5 == 0:
            try:
                await message.reply(
                    "👤  Я не вижу вас в системе, вы не зарегестрированы или ваши данные не обновлены!\n\n"
                    "📌 Пожалуйста, обновите свои данные через бота и команду /update :\n"
                    "👉 @REG_sf_BOT\n\n"
                    "Или зарегистрируйтесь через команду /apply в личных сообщениях с ботом.",
                    disable_notification=True
                )
                logger.info(f"📨 Напоминание отправлено пользователю {user_id} (сообщение #{count})")
            except Exception as e:
                logger.error(f"Ошибка отправки напоминания: {e}")
    else:
        # Если пользователь зарегистрирован, сбрасываем счетчик
        if user_id in message_counter:
            message_counter[user_id] = 0
            logger.debug(f"Сброшен счетчик для пользователя {user_id}")

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

@router.message(Command("reset_counter"))
async def reset_counter_command(message: types.Message):
    """Команда для сброса счетчика сообщений (только для админов)"""
    # Простая проверка на владельца
    if message.from_user.id == 8076284478:  # Ваш ID
        user_id = int(message.text.split()[1]) if len(message.text.split()) > 1 else message.from_user.id
        if user_id in message_counter:
            message_counter[user_id] = 0
            await message.reply(f"✅ Счетчик для пользователя {user_id} сброшен.")
        else:
            await message.reply(f"⚠️ Пользователь {user_id} не найден в счетчике.")
    else:
        await message.reply("⛔ У вас нет прав для использования этой команды.")

__all__ = ['router']