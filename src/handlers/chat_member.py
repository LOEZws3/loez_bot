import os
import logging
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import ChatMemberUpdated

from config import GENERAL_CHAT_ID
from utils.admin_utils import is_owner
from utils.user_utils import get_user_by_id

logger = logging.getLogger(__name__)
router = Router()

message_counter = {}


def get_message_count(user_id: int) -> int:
    return message_counter.get(user_id, 0)


def set_message_count(user_id: int, count: int):
    message_counter[user_id] = count


def check_user_registration(user_id: int) -> bool:
    """Проверяет, есть ли пользователь в users.json"""
    try:
        user = get_user_by_id(user_id)
        if user:
            logger.info(f"✅ Пользователь {user_id} найден в users.json")
            return True
        logger.info(f"❌ Пользователь {user_id} НЕ найден в users.json")
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке пользователя {user_id}: {e}")
        return False


@router.message()
async def handle_message(message: types.Message):
    """Обработчик всех сообщений"""
    # ✅ ПРОПУСКАЕМ КОМАНДЫ (не перехватываем /stats, /diag, /apply и т.д.)
    if message.text and message.text.startswith('/'):
        return

    # Игнорируем сообщения из групп, кроме основного чата
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
                    "👤 Я не вижу вас в системе, вы не зарегистрированы или ваши данные не обновлены!\n\n"
                    "📌 Пожалуйста, обновите свои данные через бота и команду /update:\n"
                    "👉 @REG_sf_BOT\n\n"
                    "Или зарегистрируйтесь через команду /apply в личных сообщениях с ботом.",
                    disable_notification=True
                )
                logger.info(f"📨 Напоминание отправлено пользователю {user_id} (сообщение #{count})")
            except Exception as e:
                logger.error(f"Ошибка отправки напоминания: {e}")
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


@router.message(Command("reset_counter"))
async def reset_counter_command(message: types.Message):
    """Команда для сброса счетчика сообщений (только для владельца)"""
    if not is_owner(message.from_user.id):
        await message.reply("⛔ У вас нет прав для использования этой команды.")
        return

    parts = message.text.split()
    user_id = int(parts[1]) if len(parts) > 1 else message.from_user.id

    if user_id in message_counter:
        message_counter[user_id] = 0
        await message.reply(f"✅ Счетчик для пользователя {user_id} сброшен.")
    else:
        await message.reply(f"⚠️ Пользователь {user_id} не найден в счетчике.")


__all__ = ['router']