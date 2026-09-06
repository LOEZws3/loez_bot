import logging
from aiogram import Router, F
from aiogram.types import Message, ChatMemberUpdated
from config import GENERAL_CHAT_ID
from utils.user_utils import load_users, get_user_by_id
from utils.role_utils import get_user_role as get_user_role_from_roles

logger = logging.getLogger(__name__)
router = Router()

# Словарь для хранения счётчика сообщений незарегистрированных пользователей
user_message_counter = {}


@router.message(F.chat.id == GENERAL_CHAT_ID)
async def check_user_registration(message: Message):
    """
    Проверяет, зарегистрирован ли пользователь.
    Если нет — каждое 5-е сообщение напоминает о регистрации.
    """
    user = message.from_user
    if user is None or user.is_bot:
        return
    
    user_id = user.id
    
    # Проверяем, есть ли пользователь в базе
    user_data = get_user_by_id(user_id)
    user_role = get_user_role_from_roles(user_id)
    
    # Если пользователь зарегистрирован — сбрасываем счётчик и выходим
    if user_data is not None:
        # Если был в списке ожидания — удаляем
        if user_id in user_message_counter:
            del user_message_counter[user_id]
        return
    
    # Увеличиваем счётчик сообщений
    if user_id not in user_message_counter:
        user_message_counter[user_id] = 0
    
    user_message_counter[user_id] += 1
    
    # Каждое 5-е сообщение — напоминаем
    if user_message_counter[user_id] % 5 == 0:
        # Проверяем, есть ли у пользователя роль (персонаж)
        if user_role:
            await message.answer(
                f"👤 {user.full_name}, я вижу вас в системе, но ваши данные не обновлены!\n\n"
                f"📌 Пожалуйста, обновите свои данные через бота:\n"
                f"👉 @REG_sf_BOT\n\n"
                f"Или зарегистрируйтесь через команду /apply в личных сообщениях с ботом.",
                parse_mode="HTML"
            )
            logger.info(f"📨 Напоминание об обновлении данных отправлено {user_id} (сообщение #{user_message_counter[user_id]})")
        else:
            # Если пользователь вообще не зарегистрирован
            await message.answer(
                f"👋 {user.full_name}, я не вижу вас в базе участников!\n\n"
                f"📌 Чтобы стать участником флуда, перейдите в бота:\n"
                f"👉 @REG_sf_BOT\n\n"
                f"И подайте заявку через команду /apply в личных сообщениях с ботом.",
                parse_mode="HTML"
            )
            logger.info(f"📨 Напоминание о регистрации отправлено {user_id} (сообщение #{user_message_counter[user_id]})")
        
        # Сбрасываем счётчик, чтобы цикл повторялся
        user_message_counter[user_id] = 0


@router.chat_member()
async def on_user_join(event: ChatMemberUpdated):
    """
    Когда пользователь заходит в чат — проверяем его регистрацию
    """
    if event.chat.id != GENERAL_CHAT_ID:
        return
    
    new_status = event.new_chat_member.status
    user = event.new_chat_member.user
    
    # Если пользователь только что зашёл в чат
    if new_status in ['member', 'administrator', 'creator'] and not user.is_bot:
        # Проверяем, зарегистрирован ли он
        user_data = get_user_by_id(user.id)
        
        if user_data is None:
            # Отправляем приветственное сообщение
            try:
                await event.bot.send_message(
                    user.id,
                    f"👋 Добро пожаловать в флуд, {user.full_name}!\n\n"
                    f"📌 Чтобы стать полноценным участником, пожалуйста, зарегистрируйтесь:\n"
                    f"1. Перейдите в бота: @REG_sf_BOT\n"
                    f"2. Подайте заявку через команду /apply в личных сообщениях с ботом.\n\n"
                    f"После одобрения заявки вы получите роль и сможете полноценно участвовать в жизни флуда! 🎉"
                )
                logger.info(f"📨 Приветственное сообщение отправлено новому пользователю {user.id}")
            except Exception as e:
                logger.error(f"❌ Не удалось отправить приветствие {user.id}: {e}")