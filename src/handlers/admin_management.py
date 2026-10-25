import html
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from config import GENERAL_CHAT_ID
from utils.admin_utils import (
    is_admin, is_owner, get_admin_rank, load_admins, add_admin, remove_admin, set_rank, get_admin_info
)
from .keyboards import get_main_keyboard

logger = logging.getLogger(__name__)
admin_logger = logging.getLogger('admin_actions')  # ⚠️ Логгер для действий админов
router = Router()

@router.message(Command('promote'))
async def cmd_promote(message: Message):
    """Повысить пользователя до администратора (только владелец)"""
    user_id = message.from_user.id
    if not is_owner(user_id):
        await message.answer("⛔ Доступ запрещён. Только для владельца.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /promote [ID]\nПример: /promote 123456789")
        return

    try:
        target_id = int(parts[1].strip())
    except ValueError:
        await message.answer("❌ Неверный формат. Введите ID.")
        return

    if is_admin(target_id):
        await message.answer("ℹ️ Пользователь уже является администратором.")
        return

    if add_admin(target_id, "", f"User {target_id}", 2):
        await message.answer(f"✅ Пользователь <code>{target_id}</code> повышен до администратора!", parse_mode="HTML")
        admin_logger.info(f"👑 Владелец {user_id} повысил {target_id} до администратора (ранг 2)")
        logger.info(f"👑 Владелец {user_id} повысил {target_id} до администратора")
    else:
        await message.answer("❌ Ошибка при добавлении администратора.")

@router.message(Command('demote'))
async def cmd_demote(message: Message):
    """Понизить администратора (только владелец)"""
    user_id = message.from_user.id
    if not is_owner(user_id):
        await message.answer("⛔ Доступ запрещён. Только для владельца.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /demote [ID]\nПример: /demote 123456789")
        return

    try:
        target_id = int(parts[1].strip())
    except ValueError:
        await message.answer("❌ Неверный формат. Введите ID.")
        return

    if not is_admin(target_id):
        await message.answer("ℹ️ Пользователь не является администратором.")
        return

    if target_id == user_id:
        await message.answer("⛔ Вы не можете понизить себя.")
        return

    if remove_admin(target_id):
        await message.answer(f"✅ Пользователь <code>{target_id}</code> понижен из администраторов.", parse_mode="HTML")
        admin_logger.info(f"👑 Владелец {user_id} понизил {target_id}")
        logger.info(f"👑 Владелец {user_id} понизил {target_id}")
    else:
        await message.answer("❌ Ошибка при понижении администратора.")

@router.message(Command('setrank'))
async def cmd_setrank(message: Message):
    """Назначить ранг (только владелец). Работает и для новых юзеров."""
    user_id = message.from_user.id

    if not is_owner(user_id):
        await message.answer("⛔ Доступ запрещён. Только для владельца.")
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "❌ Используйте: /setrank [ID] [ранг]\n"
            "Ранги: 1 - Владелец, 2 - Админ, 3 - Модератор"
        )
        return

    try:
        target_id = int(parts[1])
        rank = int(parts[2])
    except ValueError:
        await message.answer("❌ Неверный ID или ранг. Введите числа.")
        return

    if rank not in [1, 2, 3]:
        await message.answer("❌ Ранг должен быть 1 (Владелец), 2 (Админ) или 3 (Модератор).")
        return

    if target_id == message.from_user.id and rank != 1:
        await message.answer("⛔ Вы не можете понизить себя (вы владелец).")
        return

    # Если юзера нет в админах — добавляем
    if not is_admin(target_id):
        if add_admin(target_id, "", f"User {target_id}", rank):
            rank_names = {1: "Владелец", 2: "Админ", 3: "Модератор"}
            await message.answer(
                f"✅ Пользователь <code>{target_id}</code> добавлен с рангом <b>{rank_names.get(rank)}</b>",
                parse_mode="HTML"
            )
            admin_logger.info(f"👑 Владелец {user_id} назначил ранг {rank} новому пользователю {target_id}")
            logger.info(f"👑 Владелец {user_id} назначил ранг {rank} новому пользователю {target_id}")
        else:
            await message.answer("❌ Ошибка при добавлении ранга.")
        return

    # Если уже админ — меняем ранг
    if set_rank(target_id, rank):
        rank_names = {1: "Владелец", 2: "Админ", 3: "Модератор"}
        await message.answer(
            f"✅ Ранг пользователя <code>{target_id}</code> изменён на <b>{rank_names.get(rank)}</b>",
            parse_mode="HTML"
        )
        admin_logger.info(f"👑 Владелец {user_id} назначил ранг {rank} пользователю {target_id}")
        logger.info(f"👑 Владелец {user_id} назначил ранг {rank} пользователю {target_id}")
    else:
        await message.answer("❌ Ошибка при назначении ранга.")

@router.message(Command('admins'))
async def cmd_admins(message: Message):
    """Список администраторов"""
    user_id = message.from_user.id

    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён. Только для администраторов.")
        return

    admins = load_admins()
    if not admins:
        await message.answer("📭 Нет администраторов.")
        return

    text = "👥 <b>Список администраторов:</b>\n\n"
    for admin in admins:
        rank_name = {1: "👑 Владелец", 2: "🔐 Админ", 3: "🛡️ Модератор"}.get(admin.get('rank', 2), "Неизвестно")
        username = f"@{admin['username']}" if admin.get('username') else "без юзернейма"
        text += f"• {html.escape(admin.get('full_name', 'Неизвестный'))} ({username}) – {rank_name} (ID: <code>{admin['id']}</code>)\n"

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))