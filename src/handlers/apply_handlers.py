import logging
from aiogram import Router, types, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import DATA_DIR, ADMINS_FILE
from utils.role_utils import get_roles_by_season, get_role_status, get_all_seasons
from utils.file_utils import load_json, save_json

logger = logging.getLogger(__name__)
router = Router()

# Состояния FSM для анкеты
class ApplyStates(StatesGroup):
    choosing_season = State()
    choosing_role = State()
    choosing_position = State()
    waiting_for_confirm = State()

# Путь к файлу с заявками
REQUESTS_FILE = f"{DATA_DIR}/system/requests.json"

def get_user_requests(user_id: int) -> list:
    """Получить все заявки пользователя"""
    data = load_json(REQUESTS_FILE, default=[])
    return [r for r in data if r['user_id'] == user_id]

def has_active_request(user_id: int) -> bool:
    """Проверить, есть ли у пользователя активная заявка"""
    requests = get_user_requests(user_id)
    return any(r['status'] == 'pending' for r in requests)

def create_apply_keyboard(seasons: list) -> InlineKeyboardMarkup:
    """Создать клавиатуру с сезонами"""
    buttons = []
    for season in seasons:
        # Считаем количество свободных ролей в сезоне
        roles = get_roles_by_season(season)
        free_count = sum(1 for role in roles if get_role_status(role) == 'free')
        total_count = len(roles)
        buttons.append([InlineKeyboardButton(
            text=f"📁 {season} ({free_count}/{total_count})",
            callback_data=f"apply_season_{season}"
        )])
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="apply_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def create_role_keyboard(roles: list) -> InlineKeyboardMarkup:
    """Создать клавиатуру с ролями"""
    buttons = []
    for role in roles:
        status = get_role_status(role)
        emoji = "✅" if status == 'free' else "🔒"
        buttons.append([InlineKeyboardButton(
            text=f"{emoji} {role}",
            callback_data=f"apply_role_{role}"
        ) if status == 'free' else InlineKeyboardButton(
            text=f"🔒 {role} (занята)",
            callback_data="apply_none"
        )])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="apply_back_to_seasons")])
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="apply_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def create_position_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру с должностями"""
    buttons = [
        [InlineKeyboardButton("👑 Администратор", callback_data="apply_position_admin")],
        [InlineKeyboardButton("👤 Участник", callback_data="apply_position_member")],
        [InlineKeyboardButton("🛡️ Модератор", callback_data="apply_position_moder")],
        [InlineKeyboardButton("🔙 Назад", callback_data="apply_back_to_roles")],
        [InlineKeyboardButton("❌ Отмена", callback_data="apply_cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(F.text == "/apply")
async def cmd_apply(message: types.Message, state: FSMContext):
    """Обработчик команды /apply"""
    user_id = message.from_user.id
    
    # Проверяем, есть ли активная заявка
    if has_active_request(user_id):
        await message.answer(
            "⚠️ У вас уже есть активная заявка!\n"
            "Дождитесь её обработки или отмените через /cancel_request"
        )
        return
    
    # Получаем все сезоны
    seasons = get_all_seasons()
    if not seasons:
        await message.answer("❌ Сезоны не найдены. Обратитесь к администратору.")
        return
    
    await state.set_state(ApplyStates.choosing_season)
    await message.answer(
        "🎯 Выберите сезон, в котором хотите подать заявку:",
        reply_markup=create_apply_keyboard(seasons)
    )

@router.callback_query(F.data.startswith("apply_season_"))
async def process_season_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора сезона"""
    season = callback.data.replace("apply_season_", "")
    await callback.answer()
    
    # Получаем роли из выбранного сезона
    roles = get_roles_by_season(season)
    if not roles:
        await callback.message.edit_text(
            f"❌ В сезоне '{season}' нет ролей.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton("🔙 Назад", callback_data="apply_back_to_seasons")],
                [InlineKeyboardButton("❌ Отмена", callback_data="apply_cancel")]
            ])
        )
        return
    
    await state.update_data(season=season)
    await state.set_state(ApplyStates.choosing_role)
    
    await callback.message.edit_text(
        f"📁 Сезон: {season}\n\n"
        "Выберите роль, на которую хотите подать заявку:\n"
        "✅ - свободна  |  🔒 - занята",
        reply_markup=create_role_keyboard(roles)
    )

@router.callback_query(F.data.startswith("apply_role_"))
async def process_role_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора роли"""
    role = callback.data.replace("apply_role_", "")
    await callback.answer()
    
    # Проверяем, свободна ли роль
    if get_role_status(role) != 'free':
        await callback.answer("❌ Эта роль уже занята!", show_alert=True)
        return
    
    await state.update_data(role=role)
    await state.set_state(ApplyStates.choosing_position)
    
    await callback.message.edit_text(
        f"🎯 Роль: {role}\n\n"
        "Теперь выберите должность, на которую претендуете:",
        reply_markup=create_position_keyboard()
    )

@router.callback_query(F.data.startswith("apply_position_"))
async def process_position_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора должности"""
    position = callback.data.replace("apply_position_", "")
    await callback.answer()
    
    # Преобразуем в нормальное название
    position_names = {
        'admin': 'Администратор',
        'member': 'Участник',
        'moder': 'Модератор'
    }
    position_name = position_names.get(position, position)
    
    await state.update_data(position=position, position_name=position_name)
    
    # Получаем все данные
    data = await state.get_data()
    season = data.get('season')
    role = data.get('role')
    
    await callback.message.edit_text(
        f"📋 Проверьте данные заявки:\n\n"
        f"📁 Сезон: {season}\n"
        f"🎭 Роль: {role}\n"
        f"👤 Должность: {position_name}\n\n"
        f"✅ Всё верно?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("✅ Отправить заявку", callback_data="apply_submit")],
            [InlineKeyboardButton("🔙 Назад к выбору должности", callback_data="apply_back_to_position")],
            [InlineKeyboardButton("🔙 Назад к ролям", callback_data="apply_back_to_roles")],
            [InlineKeyboardButton("🔙 Назад к сезонам", callback_data="apply_back_to_seasons")],
            [InlineKeyboardButton("❌ Отмена", callback_data="apply_cancel")]
        ])
    )

@router.callback_query(F.data == "apply_submit")
async def process_submit_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик отправки заявки"""
    await callback.answer()
    
    data = await state.get_data()
    user_id = callback.from_user.id
    username = callback.from_user.username or "без username"
    full_name = callback.from_user.full_name
    
    # Сохраняем заявку
    request = {
        'user_id': user_id,
        'username': username,
        'full_name': full_name,
        'season': data.get('season'),
        'role': data.get('role'),
        'position': data.get('position'),
        'position_name': data.get('position_name'),
        'status': 'pending',
        'created_at': str(datetime.now())
    }
    
    # Загружаем существующие заявки
    requests = load_json(REQUESTS_FILE, default=[])
    requests.append(request)
    save_json(REQUESTS_FILE, requests)
    
    await state.clear()
    
    await callback.message.edit_text(
        f"✅ Заявка успешно отправлена!\n\n"
        f"📁 Сезон: {data.get('season')}\n"
        f"🎭 Роль: {data.get('role')}\n"
        f"👤 Должность: {data.get('position_name')}\n\n"
        f"⏳ Ожидайте решения администратора."
    )
    
    # Уведомляем админов
    await notify_admins(callback.bot, request)

async def notify_admins(bot, request: dict):
    """Отправляет уведомление админам о новой заявке"""
    admins = load_json(ADMINS_FILE, default=[])
    
    message_text = (
        f"📨 Новая заявка!\n\n"
        f"👤 Пользователь: @{request['username']}\n"
        f"🆔 ID: {request['user_id']}\n"
        f"📁 Сезон: {request['season']}\n"
        f"🎭 Роль: {request['role']}\n"
        f"👤 Должность: {request['position_name']}\n\n"
        f"Для обработки используйте /requests"
    )
    
    for admin in admins:
        try:
            await bot.send_message(admin['id'], message_text)
        except:
            pass

@router.callback_query(F.data == "apply_back_to_seasons")
async def back_to_seasons(callback: types.CallbackQuery, state: FSMContext):
    """Возврат к выбору сезона"""
    await callback.answer()
    await state.set_state(ApplyStates.choosing_season)
    seasons = get_all_seasons()
    await callback.message.edit_text(
        "🎯 Выберите сезон:",
        reply_markup=create_apply_keyboard(seasons)
    )

@router.callback_query(F.data == "apply_back_to_roles")
async def back_to_roles(callback: types.CallbackQuery, state: FSMContext):
    """Возврат к выбору роли"""
    await callback.answer()
    data = await state.get_data()
    season = data.get('season')
    roles = get_roles_by_season(season)
    await state.set_state(ApplyStates.choosing_role)
    await callback.message.edit_text(
        f"📁 Сезон: {season}\n\n"
        "Выберите роль:",
        reply_markup=create_role_keyboard(roles)
    )

@router.callback_query(F.data == "apply_back_to_position")
async def back_to_position(callback: types.CallbackQuery, state: FSMContext):
    """Возврат к выбору должности"""
    await callback.answer()
    await state.set_state(ApplyStates.choosing_position)
    await callback.message.edit_text(
        "Выберите должность:",
        reply_markup=create_position_keyboard()
    )

@router.callback_query(F.data == "apply_cancel")
async def cancel_apply(callback: types.CallbackQuery, state: FSMContext):
    """Отмена подачи заявки"""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("❌ Подача заявки отменена.")

# Добавляем обработчик нажатия на занятую роль
@router.callback_query(F.data == "apply_none")
async def occupied_role_callback(callback: types.CallbackQuery):
    """Обработчик нажатия на занятую роль"""
    await callback.answer("❌ Эта роль уже занята!", show_alert=True)