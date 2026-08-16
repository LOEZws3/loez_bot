from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ChatType
import logging
from config import ADMIN_GROUP_ID
from utils.admin_utils import is_admin
from utils.file_utils import load_forward_map, save_forward_map

logger = logging.getLogger(__name__)
router = Router()

forward_map = load_forward_map()


@router.message(F.chat.type == ChatType.PRIVATE)
async def forward_to_admin_group(message: Message):
    user_id = message.from_user.id

    if is_admin(user_id):
        logger.info(f"👤 Админ {user_id} пишет боту — пересылка отключена")
        return

    if ADMIN_GROUP_ID is None or ADMIN_GROUP_ID == -1001234567890:
        logger.warning("⚠️ ADMIN_GROUP_ID не задан в config.py! Пересылка отключена.")
        return

    try:
        forwarded = await message.forward(chat_id=ADMIN_GROUP_ID)
        forward_map[forwarded.message_id] = user_id
        save_forward_map(forward_map)

        await message.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=f"👤 От: {message.from_user.full_name} (@{message.from_user.username})\n🆔 ID: {message.from_user.id}",
            parse_mode="HTML"
        )

        await message.answer("📩 Ваше сообщение отправлено администрации. Ожидайте ответа.")
        logger.info(f"📨 Переслано сообщение от {user_id} в группу админов")

    except Exception as e:
        logger.error(f"❌ Ошибка пересылки в группу: {e}")
        await message.answer("❌ Произошла ошибка при отправке сообщения. Попробуйте позже.")


@router.message(F.chat.id == ADMIN_GROUP_ID, F.reply_to_message)
async def reply_from_admin_group(message: Message):
    original = message.reply_to_message
    if not original:
        return

    user_id = forward_map.get(original.message_id)

    if user_id:
        try:
            await message.bot.send_message(
                chat_id=user_id,
                text=f"👤 <b>Ответ администратора:</b>\n\n{message.text}",
                parse_mode="HTML"
            )
            await message.reply("✅ Ответ отправлен пользователю.")
            logger.info(f"Админ ответил пользователю {user_id} в группе")

            del forward_map[original.message_id]
            save_forward_map(forward_map)

        except Exception as e:
            await message.reply(f"❌ Ошибка при отправке: {e}")
            logger.error(f"Ошибка ответа пользователю {user_id}: {e}")
    else:
        await message.reply(
            "⚠️ Не удалось найти пользователя для этого сообщения.\n"
            "Возможно, бот был перезапущен, и связь потерялась.\n"
            "Пожалуйста, попросите пользователя написать ещё раз."
        )