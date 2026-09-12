import os
import json
import logging
from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from config import DATA_DIR
from utils.role_utils import get_roles_by_season, get_seasons_list, is_role_free, update_role_status
from utils.user_utils import get_user_info
from handlers.keyboards import create_seasons_keyboard, create_roles_keyboard

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("apply"))
async def cmd_apply(message: types.Message):
    """Команда /apply - открывает меню с сезонами"""
    user_id = message.from_user.id
    
    # Проверяем, есть ли пользователь в системе
    if not is_user_registered(user_id):
        await message.reply(
            "❌ Вы не зарегистрированы в системе!\n\n"
            "Пожалуйста, зарегистрируйтесь через команду /start."
        )
        return
    
    # Проверяем, есть ли у пользователя уже активная заявка
    if has_active_request(user_id):
        await message.reply(
            "⏳ У вас уже есть активная заявка!\n\n"
            "Пожалуйста, дождитесь решения администратора.\n"
            "Если хотите отменить заявку - используйте /cancel_request."
        )
        return
    
    # Получаем список сезонов
    seasons = get_seasons_list()
    if not seasons:
        await message.reply("❌ Нет доступных сезонов. Обратитесь к администратору.")
        return
    
    # Создаем клавиатуру с сезонами
    keyboard = create_seasons_keyboard(seasons, "apply_season")
    
    await message.reply(
        "🎭 **Выберите сезон для подачи заявки:**\n\n"
        "📌 Доступные сезоны:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("apply_season_"))
async def process_season_selection(callback: CallbackQuery):
    """Обработка выбора сезона"""
    await callback.answer()
    
    season = callback.data.replace("apply_season_", "")
    
    # Получаем роли для выбранного сезона
    roles = get_roles_by_season(season)
    
    if not roles:
        await callback.message.edit_text(
            f"❌ В сезоне **{season}** нет доступных ролей.\n\n"
            "Пожалуйста, выберите другой сезон.",
            reply_markup=create_seasons_keyboard(get_seasons_list(), "apply_season"),
            parse_mode="Markdown"
        )
        return
    
    # Создаем клавиатуру с ролями
    keyboard = create_roles_keyboard(roles, season, "apply_role")
    
    await callback.message.edit_text(
        f"🎭 **Сезон: {season}**\n\n"
        "📌 **Доступные роли:**\n"
        "✅ — свободна\n"
        "❌ — занята\n"
        "⏳ — ожидает заявку\n\n"
        "Выберите роль для подачи заявки:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("apply_role_"))
async def process_role_selection(callback: CallbackQuery):
    """Обработка выбора роли"""
    await callback.answer()
    
    try:
        # Разбираем данные: apply_role_сезон_роль
        data_parts = callback.data.replace("apply_role_", "").split("_", 1)
        if len(data_parts) != 2:
            await callback.message.edit_text("❌ Ошибка в данных. Попробуйте еще раз.")
            return
        
        season, role_name = data_parts
        user_id = callback.from_user.id
        
        # Проверяем, свободна ли роль
        if not is_role_free(role_name, season):
            await callback.message.edit_text(
                f"❌ Роль **{role_name}** уже занята или находится в обработке.\n\n"
                "Пожалуйста, выберите другую роль.",
                reply_markup=create_roles_keyboard(get_roles_by_season(season), season, "apply_role"),
                parse_mode="Markdown"
            )
            return
        
        # Создаем заявку
        request_id = create_request(user_id, role_name, season)
        
        if request_id:
            # Уведомляем админов
            await notify_admins(callback.bot, user_id, role_name, season, request_id)
            
            # Обновляем статус роли
            update_role_status(role_name, season, "pending")
            
            # Ответ пользователю
            await callback.message.edit_text(
                f"✅ **Заявка на роль «{role_name}» в сезоне «{season}» отправлена!**\n\n"
                f"📌 Номер заявки: #{request_id}\n\n"
                f"⏳ Пожалуйста, дождитесь решения администратора.\n"
                f"Вы получите уведомление, когда ваша заявка будет рассмотрена.\n\n"
                f"🗑️ Чтобы отменить заявку, используйте команду /cancel_request.",
                parse_mode="Markdown"
            )
        else:
            await callback.message.edit_text(
                "❌ Произошла ошибка при создании заявки.\n"
                "Пожалуйста, попробуйте позже или обратитесь к администратору."
            )
            
    except Exception as e:
        logger.error(f"Ошибка при обработке выбора роли: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка. Попробуйте снова через /apply"
        )

@router.message(Command("cancel_request"))
async def cmd_cancel_request(message: types.Message):
    """Команда для отмены заявки"""
    user_id = message.from_user.id
    
    # Проверяем, есть ли активная заявка
    request = get_active_request(user_id)
    if not request:
        await message.reply(
            "❌ У вас нет активных заявок.\n\n"
            "Чтобы подать новую заявку, используйте /apply"
        )
        return
    
    # Отменяем заявку
    if cancel_request(request['id']):
        # Возвращаем статус роли
        update_role_status(request['role'], request['season'], "free")
        
        await message.reply(
            f"✅ Заявка #{request['id']} на роль «{request['role']}» отменена.\n\n"
            "Вы можете подать новую заявку через /apply"
        )
    else:
        await message.reply(
            "❌ Ошибка при отмене заявки.\n"
            "Пожалуйста, попробуйте позже или обратитесь к администратору."
        )

# ======================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (используют ВАШИ данные) ========================

def is_user_registered(user_id: int) -> bool:
    """Проверяет, зарегистрирован ли пользователь"""
    try:
        users_file = os.path.join(DATA_DIR, 'users', 'users.txt')
        if not os.path.exists(users_file):
            return False
        
        with open(users_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith(str(user_id) + '|'):
                    return True
        return False
    except Exception as e:
        logger.error(f"Ошибка проверки регистрации: {e}")
        return False

def has_active_request(user_id: int) -> bool:
    """Проверяет, есть ли у пользователя активная заявка"""
    try:
        requests_file = os.path.join(DATA_DIR, 'system', 'requests.json')
        if not os.path.exists(requests_file):
            return False
        
        with open(requests_file, 'r', encoding='utf-8') as f:
            requests = json.load(f)
        
        for req_id, req_data in requests.items():
            if req_data.get('user_id') == user_id and req_data.get('status') == 'pending':
                return True
        return False
    except Exception as e:
        logger.error(f"Ошибка проверки заявок: {e}")
        return False

def get_active_request(user_id: int):
    """Получает активную заявку пользователя"""
    try:
        requests_file = os.path.join(DATA_DIR, 'system', 'requests.json')
        if not os.path.exists(requests_file):
            return None
        
        with open(requests_file, 'r', encoding='utf-8') as f:
            requests = json.load(f)
        
        for req_id, req_data in requests.items():
            if req_data.get('user_id') == user_id and req_data.get('status') == 'pending':
                req_data['id'] = req_id
                return req_data
        return None
    except Exception as e:
        logger.error(f"Ошибка получения заявки: {e}")
        return None

def create_request(user_id: int, role_name: str, season: str) -> int:
    """Создает новую заявку"""
    try:
        requests_file = os.path.join(DATA_DIR, 'system', 'requests.json')
        
        # Загружаем существующие заявки
        if os.path.exists(requests_file):
            with open(requests_file, 'r', encoding='utf-8') as f:
                requests = json.load(f)
        else:
            requests = {}
        
        # Генерируем ID заявки
        request_id = max([int(r) for r in requests.keys()], default=0) + 1
        
        # Получаем информацию о пользователе
        user_info = get_user_info(user_id)
        
        # Создаем заявку
        requests[str(request_id)] = {
            'user_id': user_id,
            'username': user_info.get('username', ''),
            'full_name': user_info.get('full_name', ''),
            'role': role_name,
            'season': season,
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        # Сохраняем
        with open(requests_file, 'w', encoding='utf-8') as f:
            json.dump(requests, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Создана заявка #{request_id} от {user_id} на роль {role_name} в {season}")
        return request_id
        
    except Exception as e:
        logger.error(f"Ошибка создания заявки: {e}")
        return None

def cancel_request(request_id: int) -> bool:
    """Отменяет заявку"""
    try:
        requests_file = os.path.join(DATA_DIR, 'system', 'requests.json')
        if not os.path.exists(requests_file):
            return False
        
        with open(requests_file, 'r', encoding='utf-8') as f:
            requests = json.load(f)
        
        if str(request_id) in requests:
            requests[str(request_id)]['status'] = 'canceled'
            requests[str(request_id)]['updated_at'] = datetime.now().isoformat()
            
            with open(requests_file, 'w', encoding='utf-8') as f:
                json.dump(requests, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Заявка #{request_id} отменена")
            return True
        
        return False
    except Exception as e:
        logger.error(f"Ошибка отмены заявки: {e}")
        return False

async def notify_admins(bot, user_id: int, role_name: str, season: str, request_id: int):
    """Уведомляет администраторов о новой заявке"""
    try:
        # Получаем список администраторов
        admins_file = os.path.join(DATA_DIR, 'admins', 'admins.txt')
        if not os.path.exists(admins_file):
            logger.warning("Файл с админами не найден")
            return
        
        admins = []
        with open(admins_file, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split('|')
                if len(parts) >= 1:
                    admins.append(int(parts[0]))
        
        if not admins:
            logger.warning("Нет администраторов для уведомления")
            return
        
        # Получаем информацию о пользователе
        user_info = get_user_info(user_id)
        user_mention = f"@{user_info['username']}" if user_info['username'] else f"[{user_info['full_name']}](tg://user?id={user_id})"
        
        # Создаем сообщение для админов
        text = (
            f"📨 **Новая заявка!**\n\n"
            f"👤 **Пользователь:** {user_mention}\n"
            f"🎭 **Роль:** {role_name}\n"
            f"📂 **Сезон:** {season}\n"
            f"🆔 **ID заявки:** #{request_id}\n\n"
            f"⏳ Ожидает решения."
        )
        
        # Кнопки для админов
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{request_id}"),
                InlineKeyboardButton(text="❌ Отказать", callback_data=f"reject_{request_id}")
            ]
        ])
        
        # Отправляем каждому админу
        for admin_id in admins:
            try:
                await bot.send_message(
                    admin_id,
                    text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                logger.info(f"📨 Уведомление о заявке #{request_id} отправлено админу {admin_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки админу {admin_id}: {e}")
        
    except Exception as e:
        logger.error(f"Ошибка уведомления админов: {e}")