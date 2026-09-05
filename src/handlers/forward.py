import logging
from aiogram import Router, F
from aiogram.types import Message
from config import ADMIN_GROUP_ID, GENERAL_CHAT_ID
from utils.admin_utils import is_admin

logger = logging.getLogger(__name__)
router = Router()

@router.message(F.chat.type == "private")
async def forward_to_admin_group(message: Message):
    """Пересылка сообщений от пользователей в админ-группу"""
    user_id = message.from_user.id
    
    # Если это админ — не пересылаем
    if is_admin(user_id):
        logger.info(f"👤 Админ {user_id} пишет боту — пересылка отключена")
        return
    
    # Пропускаем команды
    if message.text and message.text.startswith('/'):
        logger.info(f"ℹ️ Команда {message.text} от {user_id} — не пересылаем")
        return
    
    # Пропускаем пустые сообщения
    if not message.text or message.text.strip() == "":
        logger.info(f"ℹ️ Пустое сообщение от {user_id} — не пересылаем")
        return
    
    # Пропускаем служебные сообщения с эмодзи-префиксами
    if message.text.startswith(('✅', '❌', '📝', '⚠️', 'ℹ️', '⏳', '🔒', '🔓')):
        logger.info(f"ℹ️ Служебное сообщение от {user_id} — не пересылаем")
        return
    
    # Пропускаем ответы на сообщения бота
    bot_id = (await message.bot.get_me()).id
    if message.reply_to_message and message.reply_to_message.from_user.id == bot_id:
        logger.info(f"ℹ️ Ответ на сообщение бота от {user_id} — не пересылаем")
        return
    
    try:
        await message.forward(chat_id=ADMIN_GROUP_ID)
        await message.answer("✅ Ваше сообщение отправлено администраторам!")
        logger.info(f"📨 Сообщение от {user_id} переслано в админ-группу")
    except Exception as e:
        logger.error(f"❌ Ошибка пересылки сообщения от {user_id}: {e}")
        
        if "Chat not found" in str(e):
            try:
                await message.answer(
                    "❌ К сожалению, администраторы временно недоступны.\n"
                    "Попробуйте позже или свяжитесь с @Sedrikai_bot"
                )
            except Exception as inner_e:
                logger.error(f"❌ Не удалось уведомить о проблеме: {inner_e}")
        else:
            await message.answer("❌ Произошла ошибка при отправке сообщения. Попробуйте позже.")

# Исправленный синтаксис для групп
@router.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_group_messages(message: Message):
    """Логирование сообщений в группах"""
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else None
    
    if message.from_user and message.from_user.is_bot:
        return
    
    if chat_id == GENERAL_CHAT_ID:
        logger.debug(f"💬 Сообщение в флуде от {user_id}: {message.text}")