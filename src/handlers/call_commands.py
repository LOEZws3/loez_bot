import asyncio
import time
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from config import GENERAL_CHAT_ID
from utils.admin_utils import is_admin, get_admin_rank
from utils.user_utils import load_users
from utils.emoji_utils import get_user_emoji
from .utils import load_unsubscribed, is_unsubscribed, add_unsubscribed, remove_unsubscribed
import logging

logger = logging.getLogger(__name__)
router = Router()

call_cooldowns = {}
callfal_cooldowns = {}

@router.message(Command('call'))
async def cmd_call(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if chat_id != GENERAL_CHAT_ID:
        return

    if not is_admin(user_id):
        try:
            chat_member = await message.bot.get_chat_member(chat_id, user_id)
            if chat_member.status not in ['creator', 'administrator']:
                await message.answer("⛔ Только модераторы и администраторы могут использовать эту команду.")
                return
        except Exception as e:
            logger.error(f"❌ Ошибка проверки прав во флуде: {e}")
            await message.answer("⛔ У вас недостаточно прав для использования этой команды.")
            return

    last_call = call_cooldowns.get(user_id, 0)
    current_time = time.time()
    if current_time - last_call < 15:
        remaining = int(15 - (current_time - last_call))
        await message.answer(f"⏳ Подождите {remaining} секунд перед следующим калом.")
        return

    parts = message.text.split(maxsplit=1)
    call_text = parts[1][:300] if len(parts) > 1 else ""

    status_msg = await message.answer("📡 Получаю список участников из локального хранилища...")

    users = load_users()
    unsubscribed = load_unsubscribed()

    members = []
    for u in users:
        u_id = u['id']
        if u_id in unsubscribed or u_id == user_id:
            continue
        members.append(u)

    if not members:
        await status_msg.edit_text("❌ В локальном списке нет участников для кала.")
        return

    await status_msg.delete()

    sent_count = 0
    batch_size = 5
    first_batch = True
    errors = 0

    for i in range(0, len(members), batch_size):
        batch = members[i:i + batch_size]
        mentions = []
        for user in batch:
            u_id = user['id']
            emoji = get_user_emoji(u_id)
            mentions.append(f'<a href="tg://user?id={u_id}">{emoji}</a>')

        if first_batch:
            message_text = f"{' '.join(mentions)} {call_text}" if call_text else f"{' '.join(mentions)}"
            first_batch = False
        else:
            message_text = f"{' '.join(mentions)}"

        try:
            await message.answer(message_text, parse_mode="HTML")
            sent_count += len(batch)
        except Exception as e:
            errors += 1
            logger.error(f"❌ Ошибка отправки кала: {e}")
        await asyncio.sleep(0.3)

    call_cooldowns[user_id] = current_time
    logger.info(f"📢 Кал отправлен. Упомянуто: {sent_count}, Ошибок: {errors}")
    
    result_text = f"✅ Кал отправлен! Упомянуто участников: {sent_count}"
    if errors > 0:
        result_text += f"\n⚠️ Ошибок при отправке: {errors}"
    await message.answer(result_text)

@router.message(Command('callfal'))
async def cmd_callfal(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if chat_id != GENERAL_CHAT_ID:
        return

    if not (is_admin(user_id) and get_admin_rank(user_id) in [1, 2]):
        await message.answer("⛔ Только владелец и администраторы могут использовать эту команду.")
        return

    last_call = callfal_cooldowns.get(user_id, 0)
    current_time = time.time()
    if current_time - last_call < 30:
        remaining = int(30 - (current_time - last_call))
        await message.answer(f"⏳ Подождите {remaining} секунд перед следующим непропускаемым калом.")
        return

    parts = message.text.split(maxsplit=1)
    call_text = parts[1][:300] if len(parts) > 1 else ""

    status_msg = await message.answer("📡 Получаю список участников...")

    users = load_users()
    unsubscribed = load_unsubscribed()

    members = []
    for u in users:
        u_id = u['id']
        if u_id in unsubscribed:
            continue
        members.append(u)

    if not members:
        await status_msg.edit_text("❌ В локальном списке нет участников.")
        return

    await status_msg.delete()

    sent_count = 0
    batch_size = 5
    first_batch = True
    errors = 0

    for i in range(0, len(members), batch_size):
        batch = members[i:i + batch_size]
        mentions = []
        for user in batch:
            u_id = user['id']
            emoji = get_user_emoji(u_id)
            mentions.append(f'<a href="tg://user?id={u_id}">{emoji}</a>')

        if first_batch:
            message_text = f"{' '.join(mentions)} {call_text}" if call_text else f"{' '.join(mentions)}"
            first_batch = False
        else:
            message_text = f"{' '.join(mentions)}"

        try:
            await message.answer(message_text, parse_mode="HTML")
            sent_count += len(batch)
        except Exception as e:
            errors += 1
            logger.error(f"❌ Ошибка /callfal: {e}")
        await asyncio.sleep(0.3)

    callfal_cooldowns[user_id] = current_time
    logger.info(f"📢 /callfal отправлен. Упомянуто: {sent_count}, Ошибок: {errors}")

    result_text = f"✅ Непропускаемый кал отправлен! Упомянуто участников: {sent_count}"
    if errors > 0:
        result_text += f"\n⚠️ Ошибок при отправке: {errors}"
    await message.answer(result_text)

@router.message(Command('regc'))
async def cmd_regc(message: Message):
    """Подписаться на калы"""
    user_id = message.from_user.id
    if is_unsubscribed(user_id):
        remove_unsubscribed(user_id)
        await message.answer("✅ Вы подписались на калы.")
    else:
        await message.answer("ℹ️ Вы уже подписаны на калы.")

@router.message(Command('unregc'))
async def cmd_unregc(message: Message):
    """Отписаться от калов"""
    user_id = message.from_user.id
    if not is_unsubscribed(user_id):
        add_unsubscribed(user_id)
        await message.answer("✅ Вы отписались от калов.")
    else:
        await message.answer("ℹ️ Вы уже отписаны от калов.")