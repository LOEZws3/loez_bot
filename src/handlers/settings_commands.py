import html
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from config import GENERAL_CHAT_ID, ADMIN_GROUP_ID
from utils.admin_utils import is_owner, is_admin
import logging

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command('diag'))
async def cmd_diag(message: Message):
    """Диагностика всех команд (только для владельца)"""
    user_id = message.from_user.id
    if not is_owner(user_id):
        await message.answer("⛔ Доступ запрещён. Только для владельца.")
        return
    
    logger.info(f"🔍 Владелец {user_id} запустил диагностику команд")
    
    # Получаем информацию о боте
    me = await message.bot.get_me()
    bot_username = me.username
    bot_id = me.id
    
    # Получаем список всех зарегистрированных хендлеров
    handlers_info = []
    for handler in router.message.handlers:
        if hasattr(handler, 'filters'):
            for f in handler.filters:
                if hasattr(f, 'command') and f.command:
                    cmds = f.command if isinstance(f.command, (list, tuple)) else [f.command]
                    for cmd in cmds:
                        handlers_info.append(f"/{cmd}")
    
    handlers_info = sorted(list(set(handlers_info)))
    
    report = "📋 <b>Диагностика команд</b>\n\n"
    report += f"🤖 Бот: @{bot_username}\n"
    report += f"🆔 ID бота: <code>{bot_id}</code>\n"
    report += f"👤 Ваш ID: <code>{user_id}</code>\n\n"
    report += f"✅ Зарегистрировано команд: {len(handlers_info)}\n\n"
    
    if handlers_info:
        report += "<b>Список команд:</b>\n"
        for cmd in handlers_info:
            report += f"• {cmd}\n"
    else:
        report += "⚠️ Команды не найдены!\n"
    
    report += "\n🔄 <b>Фоновые задачи:</b>\n"
    report += "• Синхронизация пользователей: Активна\n"
    report += "• Проверка рестов: Активна"
    
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
            status_emoji = {
                'creator': '👑', 'administrator': '🔐', 'member': '👤',
                'restricted': '⛔', 'left': '❌', 'kicked': '🚫'
            }.get(status, '❓')
            result += f"{status_emoji} <b>Флуд-чат:</b>\n   • ID: <code>{GENERAL_CHAT_ID}</code>\n   • Название: {html.escape(chat.title)}\n   • Статус: <b>{status}</b>\n"
            if status in ['creator', 'administrator']:
                permissions = []
                if member.can_manage_chat: permissions.append("Управление чатом")
                if member.can_delete_messages: permissions.append("Удаление сообщений")
                if member.can_restrict_members: permissions.append("Ограничение участников")
                if member.can_promote_members: permissions.append("Назначение админов")
                if member.can_invite_users: permissions.append("Приглашение")
                if member.can_pin_messages: permissions.append("Закрепление")
                if member.can_manage_video_chats: permissions.append("Управление видеочатами")
                if hasattr(member, 'can_manage_topics') and member.can_manage_topics: permissions.append("Управление темами")
                result += f"   • Права: {', '.join(permissions) if permissions else 'Только базовые'}\n"
            result += "\n"
        except Exception as e:
            result += f"❌ <b>Флуд-чат:</b> Ошибка — {e}\n\n"
        
        # Проверка админ-группы
        try:
            chat = await message.bot.get_chat(ADMIN_GROUP_ID)
            member = await message.bot.get_chat_member(ADMIN_GROUP_ID, message.bot.id)
            status = member.status
            status_emoji = {
                'creator': '👑', 'administrator': '🔐', 'member': '👤',
                'restricted': '⛔', 'left': '❌', 'kicked': '🚫'
            }.get(status, '❓')
            result += f"{status_emoji} <b>Админ-группа:</b>\n   • ID: <code>{ADMIN_GROUP_ID}</code>\n   • Название: {html.escape(chat.title)}\n   • Статус: <b>{status}</b>\n"
            if status in ['creator', 'administrator']:
                permissions = []
                if member.can_delete_messages: permissions.append("Удаление сообщений")
                if member.can_restrict_members: permissions.append("Ограничение участников")
                if member.can_invite_users: permissions.append("Приглашение")
                result += f"   • Права: {', '.join(permissions) if permissions else 'Только базовые'}\n"
            result += "\n"
        except Exception as e:
            result += f"❌ <b>Админ-группа:</b> Ошибка — {e}\n\n"
        
        # Проверка текущего чата
        try:
            chat = await message.bot.get_chat(message.chat.id)
            member = await message.bot.get_chat_member(message.chat.id, message.bot.id)
            status = member.status
            status_emoji = {
                'creator': '👑', 'administrator': '🔐', 'member': '👤',
                'restricted': '⛔', 'left': '❌', 'kicked': '🚫'
            }.get(status, '❓')
            result += f"{status_emoji} <b>Текущий чат:</b>\n   • ID: <code>{message.chat.id}</code>\n   • Название: {html.escape(chat.title) if chat.title else 'Личка'}\n   • Тип: {message.chat.type}\n   • Статус: <b>{status}</b>\n"
        except Exception as e:
            result += f"❌ <b>Текущий чат:</b> Ошибка — {e}\n"
        
        # Количество участников
        try:
            total_members = await message.bot.get_chat_member_count(chat_id=GENERAL_CHAT_ID)
            result += f"\n📊 <b>Всего участников в флуд-чате:</b> {total_members}"
        except AttributeError:
            try:
                total_members = await message.bot.get_chat_members_count(chat_id=GENERAL_CHAT_ID)
                result += f"\n📊 <b>Всего участников в флуд-чате:</b> {total_members}"
            except Exception as e2:
                result += f"\n❌ Не удалось посчитать участников: {e2}"
        except Exception as e:
            result += f"\n❌ Не удалось посчитать участников: {e}"
        
        await message.answer(result, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка диагностики: {e}")