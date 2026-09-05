import logging
from aiogram import Router, F
from aiogram.types import Message
from config import ADMIN_GROUP_ID, GENERAL_CHAT_ID
from utils.admin_utils import is_admin
from proxy_manager import proxy_manager
from .keyboards import load_forward_settings

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.chat.type == "private")
async def forward_to_admin_group(message: Message):
    """Пересылка сообщений от пользователей в админ-группу (с учётом настроек)"""
    user_id = message.from_user.id
    
    # Получаем настройки
    settings = load_forward_settings()
    forward_enabled = settings.get("forward_enabled", True)
    anonymous_mode = settings.get("anonymous_mode", False)
    
    # Если пересылка отключена
    if not forward_enabled:
        await message.answer("ℹ️ Пересылка сообщений временно отключена администрацией.")
        logger.info(f"ℹ️ Пересылка отключена, сообщение от {user_id} не переслано")
        return
    
    # Если это админ — логируем
    if is_admin(user_id):
        logger.info(f"👤 Админ {user_id} пишет боту — пересылка отключена")
        return
    
    # Пропускаем команды
    if message.text and message.text.startswith('/'):
        logger.info(f"ℹ️ Команда от {user_id} — не пересылаем")
        return
    
    # Пропускаем пустые сообщения
    if not message.text or message.text.strip() == "":
        return
    
    # Пропускаем служебные сообщения
    if message.text and message.text.startswith(('✅', '❌', '📝', '⚠️', 'ℹ️', '⏳', '🔒', '🔓')):
        return
    
    # Отправляем уведомление пользователю
    await message.answer("📨 Ваше сообщение отправлено администраторам!")
    
    try:
        # Формируем текст для пересылки
        forward_text = f"📩 <b>Сообщение от игрока:</b>\n\n{message.text}"
        
        # Если включён анонимный режим — не показываем ID
        if anonymous_mode:
            forward_text += f"\n\n🕵️ <i>Анонимное сообщение</i>"
        else:
            user = message.from_user
            forward_text += f"\n\n👤 <b>От:</b> {user.full_name} (@{user.username if user.username else 'без юзернейма'})"
            forward_text += f"\n🆔 <b>ID:</b> <code>{user.id}</code>"
        
        # Пересылаем в админ-группу
        await message.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=forward_text,
            parse_mode="HTML"
        )
        
        logger.info(f"📨 Сообщение от {user_id} переслано в админ-группу (анонимно: {anonymous_mode})")
        
    except Exception as e:
        logger.error(f"❌ Ошибка пересылки: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_group_messages(message: Message):
    """Логирование сообщений в группах"""
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else None
    
    if message.from_user and message.from_user.is_bot:
        return
    
    if chat_id == GENERAL_CHAT_ID:
        logger.debug(f"💬 Сообщение в флуде от {user_id}: {message.text}")