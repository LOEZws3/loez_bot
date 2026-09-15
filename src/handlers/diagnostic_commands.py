import os
import sys
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from config import BOT_TOKEN, GENERAL_CHAT_ID, ADMIN_GROUP_ID, DATA_DIR
from utils.admin_utils import is_owner
from database import db
import aiohttp

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command('diag'))
async def cmd_diag(message: Message):
    """Диагностика всех команд (только для владельца)"""
    user_id = message.from_user.id

    if not is_owner(user_id):
        await message.answer("⛔ Доступ запрещён. Только для владельца.")
        return

    logger.info(f"🔍 Владелец {user_id} запустил диагностику")

    report = "📋 <b>Диагностика системы</b>\n\n"

    # 1. Информация о боте
    try:
        me = await message.bot.get_me()
        report += f"🤖 Бот: @{me.username}\n"
        report += f"🆔 ID бота: <code>{me.id}</code>\n"
        report += f"👤 Ваш ID: <code>{user_id}</code>\n\n"
    except Exception as e:
        report += f"❌ Ошибка получения данных бота: {e}\n\n"

    # 2. Проверка файлов (АБСОЛЮТНЫЕ ПУТИ)
    report += "📁 <b>Файлы:</b>\n"
    files = [
        (os.path.join(DATA_DIR, 'users', 'users.json'), "Пользователи (JSON)"),
        (os.path.join(DATA_DIR, 'users', 'users.txt'), "Пользователи (TXT legacy)"),
        (os.path.join(DATA_DIR, 'admins', 'admins.json'), "Администраторы (JSON)"),
        (os.path.join(DATA_DIR, 'admins', 'admins.txt'), "Администраторы (TXT legacy)"),
        (os.path.join(DATA_DIR, 'roles_status.json'), "Статусы ролей"),
        (os.path.join(DATA_DIR, 'system_settings.json'), "Настройки"),
        (os.path.join(DATA_DIR, 'system', 'requests.json'), "Заявки"),
        (os.path.join(DATA_DIR, '..', 'src', 'bot.db'), "База данных"),
    ]
    for path, name in files:
        exists = os.path.exists(path)
        report += f"  • {name}: {'✅' if exists else '❌'}\n"

    # 3. Проверка БД
    try:
        await db.get_all_roles()
        report += "\n🗄️ База данных: ✅ Подключена\n"
    except Exception as e:
        report += f"\n❌ Ошибка БД: {e}\n"

    # 4. Проверка токена
    report += f"\n🔑 Токен бота: {'✅ Установлен' if BOT_TOKEN else '❌ Не установлен'}\n"

    # 5. Проверка чатов
    report += f"\n📊 ID чатов:\n"
    report += f"  • Флуд: <code>{GENERAL_CHAT_ID}</code>\n"
    report += f"  • Админ-группа: <code>{ADMIN_GROUP_ID}</code>\n"

    # 6. Проверка прокси
    try:
        from config import USE_PROXY
        from proxy_manager import proxy_manager
        report += f"\n🌐 Прокси: {'✅ Включён' if USE_PROXY else '❌ Отключён'}\n"
        if USE_PROXY:
            current = proxy_manager.get_current_proxy()
            report += f"  • Текущий: <code>{current or 'не выбран'}</code>\n"
            report += f"  • Всего прокси: {proxy_manager.get_proxy_count()}\n"
    except Exception as e:
        report += f"\n⚠️ Ошибка проверки прокси: {e}\n"

    await message.answer(report, parse_mode="HTML")


@router.message(Command('check_chats'))
async def cmd_check_chats(message: Message):
    """Диагностика чатов (только для владельца)"""
    user_id = message.from_user.id

    if not is_owner(user_id):
        await message.answer("⛔ Доступ запрещён. Только для владельца.")
        return

    if message.chat.id != GENERAL_CHAT_ID:
        await message.answer("🔍 Проверка чатов доступна только во флуд-чате для владельца.")
        return

    await message.answer("🔍 Проверяю чаты, где есть бот...")

    try:
        result = "📋 <b>Статус бота в чатах:</b>\n\n"

        # Проверка флуд-чата
        try:
            chat = await message.bot.get_chat(GENERAL_CHAT_ID)
            member = await message.bot.get_chat_member(GENERAL_CHAT_ID, message.bot.id)
            status = member.status
            status_emoji = {'creator': '👑', 'administrator': '🔐', 'member': '👤',
                            'restricted': '⛔', 'left': '❌', 'kicked': '🚫'}.get(status, '❓')
            result += f"{status_emoji} <b>Флуд-чат:</b>\n"
            result += f"   • ID: <code>{GENERAL_CHAT_ID}</code>\n"
            result += f"   • Название: {chat.title}\n"
            result += f"   • Статус: <b>{status}</b>\n"
        except Exception as e:
            result += f"❌ <b>Флуд-чат:</b> Ошибка — {e}\n"

        # Проверка админ-группы
        try:
            chat = await message.bot.get_chat(ADMIN_GROUP_ID)
            member = await message.bot.get_chat_member(ADMIN_GROUP_ID, message.bot.id)
            status = member.status
            status_emoji = {'creator': '👑', 'administrator': '🔐', 'member': '👤',
                            'restricted': '⛔', 'left': '❌', 'kicked': '🚫'}.get(status, '❓')
            result += f"\n{status_emoji} <b>Админ-группа:</b>\n"
            result += f"   • ID: <code>{ADMIN_GROUP_ID}</code>\n"
            result += f"   • Название: {chat.title}\n"
            result += f"   • Статус: <b>{status}</b>\n"
        except Exception as e:
            result += f"\n❌ <b>Админ-группа:</b> Ошибка — {e}\n"

        await message.answer(result, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка диагностики: {e}")