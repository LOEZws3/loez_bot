import html
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from config import GENERAL_CHAT_ID
from utils.admin_utils import is_admin, is_owner, load_admins, save_admins, get_admin_rank, set_rank
from utils.user_utils import load_users, add_user, remove_user, get_users_count
from utils.role_utils import free_role, get_user_role as get_user_role_from_roles
from utils.requests_utils import get_request_by_user_id
from .keyboards import get_main_keyboard
import logging

logger = logging.getLogger(__name__)
router = Router()

ROLE_NAMES = {
    '0': 'Участник',
    '1': 'Небезопасный клиент',
    '2': 'Неприемлемый ник',
    '3': 'Временный статус (рест/нью)',
    '4': 'Администрация',
    '5': 'Администрация в ресте'
}

closed_mode = False

@router.message(Command('register_admin'))
async def cmd_register_admin(message: Message):
    """Регистрация администратора"""
    user = message.from_user
    if user is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /register_admin [пароль]")
        return
    
    password = parts[1]
    from config import ADMIN_PASSWORD
    if password != ADMIN_PASSWORD:
        await message.answer("❌ Неверный пароль для регистрации администратора.")
        logger.warning(f"⚠️ Неудачная попытка регистрации админа от {user.full_name}")
        return
    
    if is_admin(user.id):
        await message.answer("ℹ️ Вы уже администратор.")
        return
    
    success = add_admin(user.id, user.username, user.full_name)
    if success:
        rank = get_admin_rank(user.id)
        rank_name = "Владелец" if rank == 1 else "Админ"
        text = f"✅ Вы стали администратором!\nВаш ранг: {rank_name}\nТеперь вам доступны админ-команды."
        if message.chat.id == GENERAL_CHAT_ID:
            await message.answer(text)
        else:
            await message.answer(text, reply_markup=get_main_keyboard(user.id, message.chat.id))
        logger.info(f"✅ НОВЫЙ АДМИН: {user.full_name} (@{user.username}) ID: {user.id}")
    else:
        await message.answer("❌ Ошибка регистрации. Попробуйте позже.")

@router.message(Command('register_user'))
async def cmd_register_user(message: Message):
    """Регистрация участника"""
    user = message.from_user
    if user is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /register_user [пароль]")
        return
    
    password = parts[1]
    from config import USER_PASSWORD
    if password != USER_PASSWORD:
        await message.answer("❌ Неверный пароль для регистрации участника.")
        logger.warning(f"⚠️ Неудачная попытка регистрации участника от {user.full_name}")
        return
    
    if user.id in [u['id'] for u in load_users()]:
        await message.answer("ℹ️ Вы уже зарегистрированы как участник.")
        return
    
    success = add_user(user.id, user.username, user.full_name)
    if success:
        text = "✅ Вы успешно зарегистрированы как участник!"
        if message.chat.id == GENERAL_CHAT_ID:
            await message.answer(text)
        else:
            await message.answer(text, reply_markup=get_main_keyboard(user.id, message.chat.id))
        logger.info(f"✅ НОВЫЙ УЧАСТНИК: {user.full_name} (@{user.username}) ID: {user.id}")
    else:
        await message.answer("❌ Ошибка регистрации. Попробуйте позже.")

@router.message(Command('admins'))
async def cmd_admins(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return
    
    admins = load_admins()
    if not admins:
        await message.answer("📭 Нет администраторов.")
        return
    
    text = "👥 <b>Список администраторов:</b>\n\n"
    for a in admins:
        rank_name = {1: "👑 Владелец", 2: "🔐 Админ", 3: "🛡️ Модератор"}.get(a['rank'], "Неизвестно")
        username = f"@{a['username']}" if a['username'] else "без юзернейма"
        text += f"• {html.escape(a['full_name'])} ({username}) – {rank_name} (ID: <code>{a['id']}</code>)\n"
    
    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))

@router.message(Command('users'))
async def cmd_users(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return
    
    users = load_users()
    if not users:
        await message.answer("📭 Нет участников.")
        return
    
    text = "👥 <b>Список участников (полный):</b>\n\n"
    for u in users:
        username = f"@{u['username']}" if u['username'] else "без юзернейма"
        role_name = ROLE_NAMES.get(u.get('role', '0'), 'Неизвестно')
        character = get_user_role_from_roles(u['id']) or "Нет роли"
        text += f"• {html.escape(u['full_name'])} ({username}) – {role_name} ({character}) (ID: <code>{u['id']}</code>)\n"
    
    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))

@router.message(Command('adduser'))
async def cmd_adduser(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /adduser [ID]")
        return
    
    try:
        new_user_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID. Введите число.")
        return
    
    users = load_users()
    for u in users:
        if u['id'] == new_user_id:
            await message.answer(f"ℹ️ Пользователь с ID {new_user_id} уже есть.")
            return
    
    if add_user(new_user_id, None, f"User {new_user_id}"):
        text = f"✅ Пользователь с ID {new_user_id} добавлен."
        if message.chat.id == GENERAL_CHAT_ID:
            await message.answer(text)
        else:
            await message.answer(text, reply_markup=get_main_keyboard(user_id, message.chat.id))
        logger.info(f"Админ {user_id} добавил участника {new_user_id}")
    else:
        await message.answer("❌ Ошибка при добавлении.")

@router.message(Command('removeuser'))
async def cmd_removeuser(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /removeuser [ID]")
        return
    
    try:
        remove_user_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID. Введите число.")
        return
    
    if remove_user(remove_user_id):
        text = f"✅ Пользователь с ID {remove_user_id} удалён."
        if message.chat.id == GENERAL_CHAT_ID:
            await message.answer(text)
        else:
            await message.answer(text, reply_markup=get_main_keyboard(user_id, message.chat.id))
        logger.info(f"Админ {user_id} удалил участника {remove_user_id}")
    else:
        await message.answer(f"❌ Пользователь с ID {remove_user_id} не найден.")

@router.message(Command('resetuser'))
async def cmd_resetuser(message: Message):
    admin_id = message.from_user.id
    if not is_admin(admin_id):
        await message.answer("⛔ Доступ запрещён. Только для администраторов.")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /resetuser [ID]")
        return
    
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID. Введите число.")
        return
    
    if is_admin(target_id):
        await message.answer("⛔ Нельзя сбросить администратора.")
        return
    
    try:
        await message.bot.set_chat_member_tag(chat_id=GENERAL_CHAT_ID, user_id=target_id, tag="")
        logger.info(f"🏷️ Удалён тег у пользователя {target_id}")
    except Exception as e:
        logger.error(f"❌ Не удалось удалить тег: {e}")
    
    freed_role = free_role(target_id)
    removed = remove_user(target_id)
    
    if freed_role or removed:
        response = "✅ Пользователь сброшен:\n"
        if freed_role:
            response += f"📌 Освобождена роль: {html.escape(freed_role)}\n"
        if removed:
            response += f"👤 Удалён из списка участников.\n"
        
        if message.chat.id == GENERAL_CHAT_ID:
            await message.answer(response)
        else:
            await message.answer(response, reply_markup=get_main_keyboard(admin_id, message.chat.id))
        logger.info(f"Админ {admin_id} сбросил пользователя {target_id}")
    else:
        await message.answer(f"ℹ️ Пользователь {target_id} не найден в списке участников и не имеет роли.")

@router.message(Command('refresh'))
async def cmd_refresh(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return
    
    count = get_users_count()
    text = f"🔄 Список участников обновлён. Всего: {count} человек."
    
    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text)
    else:
        await message.answer(text, reply_markup=get_main_keyboard(user_id, message.chat.id))

@router.message(Command('find'))
async def cmd_find(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /find [ID]")
        return
    
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID. Введите число.")
        return
    
    users = load_users()
    user_data = None
    for u in users:
        if u['id'] == target_id:
            user_data = u
            break
    
    request = get_request_by_user_id(target_id)
    role = get_user_role_from_roles(target_id)
    
    text = f"🔍 <b>Информация о пользователе</b>\n\n"
    text += f"🆔 ID: <code>{target_id}</code>\n"
    text += f"🔗 <a href='tg://user?id={target_id}'>Открыть профиль</a>\n"
    
    if user_data:
        safe_name = html.escape(user_data['full_name'])
        text += f"👤 Имя: {safe_name}\n"
        text += f"🔖 Юзернейм: @{user_data['username'] if user_data['username'] else 'не указан'}\n"
    else:
        text += f"👤 Пользователь не найден в списке участников.\n"
    
    if role:
        text += f"📌 Текущая роль: {html.escape(role)}\n"
    else:
        text += f"📌 Роль: не занята\n"
    
    if request and request['status'] == 'pending':
        text += f"\n📝 <b>Есть активная заявка!</b>\n"
        text += f"📌 Роль в заявке: {html.escape(request['role'])}\n"
        text += f"🏷️ Должность: {html.escape(request['position'])}\n"
    
    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))

@router.message(Command('finduser'))
async def cmd_finduser(message: Message):
    admin_id = message.from_user.id
    if not is_admin(admin_id):
        await message.answer("⛔ Доступ запрещён.")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /finduser [юзернейм]")
        return
    
    username = parts[1].replace('@', '').strip()
    users = load_users()
    found = None
    for u in users:
        if u.get('username') and u['username'].lower() == username.lower():
            found = u
            break
    
    if not found:
        await message.answer(f"❌ Пользователь @{username} не найден в списке участников.")
        return
    
    safe_name = html.escape(found['full_name'])
    text = f"🔍 <b>Информация о пользователе</b>\n\n"
    text += f"👤 Имя: {safe_name}\n"
    text += f"🔖 Юзернейм: @{found['username']}\n"
    text += f"🆔 ID: <code>{found['id']}</code>\n"
    text += f"🔗 <a href='tg://user?id={found['id']}'>Открыть профиль</a>\n"
    
    role = get_user_role_from_roles(found['id'])
    if role:
        text += f"📌 Текущая роль: {html.escape(role)}\n"
    else:
        text += f"📌 Роль: не занята\n"
    
    request = get_request_by_user_id(found['id'])
    if request and request['status'] == 'pending':
        text += f"\n📝 <b>Есть активная заявка!</b>\n"
        text += f"📌 Роль в заявке: {html.escape(request['role'])}\n"
        text += f"🏷️ Должность: {html.escape(request['position'])}\n"
    
    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(admin_id, message.chat.id))

@router.message(Command('setrank'))
async def cmd_setrank(message: Message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        await message.answer("⛔ Доступ запрещён. Только для владельца.")
        return
    
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("❌ Используйте: /setrank [ID] [ранг]\nРанги: 1 - Владелец, 2 - Админ, 3 - Модератор")
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
    
    if set_rank(target_id, rank):
        rank_name = {1: "Владелец", 2: "Админ", 3: "Модератор"}.get(rank)
        await message.answer(f"✅ Ранг пользователя обновлён: {rank_name}")
        logger.info(f"Владелец {user_id} назначил ранг {rank} пользователю {target_id}")
    else:
        await message.answer("❌ Пользователь не найден в списке администраторов.")

@router.message(Command('close'))
async def cmd_close(message: Message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        await message.answer("⛔ Доступ запрещён. Только для владельца.")
        return
    
    global closed_mode
    closed_mode = True
    await message.answer("🔒 Набор закрыт. Новые заявки не принимаются.")

@router.message(Command('open'))
async def cmd_open(message: Message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        await message.answer("⛔ Доступ запрещён. Только для владельца.")
        return
    
    global closed_mode
    closed_mode = False
    await message.answer("🔓 Набор открыт. Заявки принимаются.")

@router.message(Command('unregister_admin'))
async def cmd_unregister_admin(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ Вы не администратор.")
        return
    
    if is_owner(user_id):
        await message.answer("⛔ Владелец не может удалить себя. Передайте права другому.")
        return
    
    admins = load_admins()
    new_admins = [a for a in admins if a['id'] != user_id]
    save_admins(new_admins)
    
    text = "✅ Вы удалены из списка администраторов."
    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text)
    else:
        await message.answer(text, reply_markup=get_main_keyboard(user_id, message.chat.id))
    logger.info(f"🔄 АДМИН {message.from_user.full_name} удалил себя")

@router.message(Command('unregister_user'))
async def cmd_unregister_user(message: Message):
    user_id = message.from_user.id
    if not remove_user(user_id):
        await message.answer("⛔ Вы не зарегистрированы как участник.")
        return
    
    text = "✅ Вы удалены из списка участников."
    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(text)
    else:
        await message.answer(text, reply_markup=get_main_keyboard(user_id, message.chat.id))
    logger.info(f"🔄 УЧАСТНИК {message.from_user.full_name} удалил себя")