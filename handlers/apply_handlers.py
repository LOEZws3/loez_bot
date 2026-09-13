import os
import json
import logging
from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from config import DATA_DIR
from utils.role_utils import (
    get_roles_by_season, get_all_seasons,
    load_roles_status, save_roles_status
)
from utils.user_utils import get_user_info

logger = logging.getLogger(__name__)
router = Router()

REQUESTS_FILE = os.path.join(DATA_DIR, 'system', 'requests.json')
USERS_FILE = os.path.join(DATA_DIR, 'users', 'users.txt')


class ApplyStates(StatesGroup):
    choosing_season = State()
    choosing_role = State()
    choosing_position = State()
    confirming = State()


# ======================== ЗАГРУЗКА / СОХРАНЕНИЕ ========================

def _load_requests() -> dict:
    if not os.path.exists(REQUESTS_FILE):
        return {}
    try:
        with open(REQUESTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _save_requests(requests: dict) -> bool:
    try:
        with open(REQUESTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(requests, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения requests.json: {e}")
        return False


def _has_active_request(user_id: int) -> bool:
    requests = _load_requests()
    for req_id, req in requests.items():
        if isinstance(req, dict) and req.get('user_id') == user_id and req.get('status') == 'pending':
            return True
    return False


def _get_active_request(user_id: int):
    requests = _load_requests()
    for req_id, req in requests.items():
        if isinstance(req, dict) and req.get('user_id') == user_id and req.get('status') == 'pending':
            return req_id, req
    return None, None


def _is_user_registered(user_id: int) -> bool:
    if not os.path.exists(USERS_FILE):
        return False
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith(str(user_id) + '|'):
                return True
    return False


# ======================== КЛАВИАТУРЫ ========================

def create_apply_keyboard(seasons: list) -> InlineKeyboardMarkup:
    buttons = []
    for season in seasons:
        roles = get_roles_by_season(season)
        free_count = sum(1 for r in roles if r.get('status') == 'свободна')
        total = len(roles)
        buttons.append([InlineKeyboardButton(
            text=f"📁 {season} ({free_count}/{total})",
            callback_data=f"apply_season_{season}"
        )])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="apply_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_role_keyboard(roles: list, season: str) -> InlineKeyboardMarkup:
    buttons = []
    for role in roles:
        role_name = role.get('name', '?')
        status = role.get('status', 'свободна')
        if status == 'свободна':
            buttons.append([InlineKeyboardButton(
                text=f"✅ {role_name}",
                callback_data=f"apply_role_{role_name}"
            )])
        else:
            buttons.append([InlineKeyboardButton(
                text=f"🔒 {role_name} (занята)",
                callback_data="apply_none"
            )])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="apply_back_to_seasons")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="apply_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_position_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="👑 Администратор", callback_data="apply_position_admin")],
        [InlineKeyboardButton(text="🛡️ Модератор", callback_data="apply_position_moder")],
        [InlineKeyboardButton(text="👤 Участник", callback_data="apply_position_member")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="apply_back_to_roles")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="apply_cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ======================== КОМАНДЫ ========================

@router.message(Command("apply"))
async def cmd_apply(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    if not _is_user_registered(user_id):
        await message.answer("❌ Вы не зарегистрированы! Используйте /start.")
        return

    if _has_active_request(user_id):
        await message.answer(
            "⚠️ У вас уже есть активная заявка!\n"
            "Дождитесь её обработки или отмените через /cancel_request."
        )
        return

    seasons = get_all_seasons()
    if not seasons:
        await message.answer("❌ Сезоны не найдены.")
        return

    await state.set_state(ApplyStates.choosing_season)
    await message.answer(
        "🎯 Выберите сезон:",
        reply_markup=create_apply_keyboard(seasons)
    )


@router.callback_query(F.data.startswith("apply_season_"))
async def process_season(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    season = callback.data.replace("apply_season_", "")

    roles = get_roles_by_season(season)
    if not roles:
        await callback.message.edit_text(
            f"❌ В сезоне '{season}' нет ролей.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="apply_back_to_seasons")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="apply_cancel")]
            ])
        )
        return

    await state.update_data(season=season)
    await state.set_state(ApplyStates.choosing_role)

    await callback.message.edit_text(
        f"📁 Сезон: <b>{season}</b>\n\nВыберите роль:\n✅ свободна | 🔒 занята",
        parse_mode="HTML",
        reply_markup=create_role_keyboard(roles, season)
    )


@router.callback_query(F.data.startswith("apply_role_"))
async def process_role(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    role_name = callback.data.replace("apply_role_", "")

    data = await state.get_data()
    season = data.get('season')

    roles = get_roles_by_season(season)
    role = next((r for r in roles if r.get('name') == role_name), None)

    if not role or role.get('status') != 'свободна':
        await callback.answer("❌ Роль уже занята!", show_alert=True)
        return

    await state.update_data(role=role_name)
    await state.set_state(ApplyStates.choosing_position)

    await callback.message.edit_text(
        f"🎭 Роль: <b>{role_name}</b>\n\nВыберите должность:",
        parse_mode="HTML",
        reply_markup=create_position_keyboard()
    )


@router.callback_query(F.data.startswith("apply_position_"))
async def process_position(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    position = callback.data.replace("apply_position_", "")

    position_names = {
        'admin': 'Администратор',
        'moder': 'Модератор',
        'member': 'Участник',
    }
    position_name = position_names.get(position, position)

    await state.update_data(position=position, position_name=position_name)

    data = await state.get_data()
    await callback.message.edit_text(
        f"📋 <b>Проверьте заявку:</b>\n\n"
        f"📁 Сезон: {data.get('season')}\n"
        f"🎭 Роль: {data.get('role')}\n"
        f"🏷️ Должность: {position_name}\n\n"
        f"Всё верно?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отправить", callback_data="apply_submit")],
            [InlineKeyboardButton(text="🔙 К должностям", callback_data="apply_back_to_position")],
            [InlineKeyboardButton(text="🔙 К ролям", callback_data="apply_back_to_roles")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="apply_cancel")]
        ])
    )


@router.callback_query(F.data == "apply_submit")
async def process_submit(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    user_id = callback.from_user.id

    requests = _load_requests()
    existing_ids = [int(k) for k in requests.keys() if str(k).isdigit()]
    request_id = max(existing_ids, default=0) + 1

    user_info = get_user_info(user_id)

    requests[str(request_id)] = {
        'user_id': user_id,
        'username': callback.from_user.username or '',
        'full_name': callback.from_user.full_name,
        'season': data.get('season'),
        'role': data.get('role'),
        'position': data.get('position'),
        'position_name': data.get('position_name'),
        'status': 'pending',
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }

    _save_requests(requests)

    # Отмечаем роль как "ожидает"
    role_name = data.get('role')
    season = data.get('season')
    if role_name and season:
        from utils.role_utils import update_role_status
        update_role_status(role_name, season, "ожидает")

    await state.clear()

    await callback.message.edit_text(
        f"✅ <b>Заявка отправлена!</b>\n\n"
        f"📁 Сезон: {data.get('season')}\n"
        f"🎭 Роль: {data.get('role')}\n"
        f"🏷️ Должность: {data.get('position_name')}\n\n"
        f"⏳ Ожидайте решения администратора.",
        parse_mode="HTML"
    )

    await _notify_admins(callback.bot, request_id, requests[str(request_id)])


@router.callback_query(F.data == "apply_none")
async def apply_none(callback: CallbackQuery):
    await callback.answer("❌ Эта роль уже занята!", show_alert=True)


@router.callback_query(F.data == "apply_cancel")
async def apply_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("❌ Подача заявки отменена.")


@router.callback_query(F.data == "apply_back_to_seasons")
async def back_to_seasons(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    seasons = get_all_seasons()
    await state.set_state(ApplyStates.choosing_season)
    await callback.message.edit_text(
        "🎯 Выберите сезон:",
        reply_markup=create_apply_keyboard(seasons)
    )


@router.callback_query(F.data == "apply_back_to_roles")
async def back_to_roles(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    season = data.get('season')
    roles = get_roles_by_season(season)
    await state.set_state(ApplyStates.choosing_role)
    await callback.message.edit_text(
        f"📁 Сезон: <b>{season}</b>\n\nВыберите роль:",
        parse_mode="HTML",
        reply_markup=create_role_keyboard(roles, season)
    )


@router.callback_query(F.data == "apply_back_to_position")
async def back_to_position(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ApplyStates.choosing_position)
    await callback.message.edit_text(
        "Выберите должность:",
        reply_markup=create_position_keyboard()
    )


# ======================== /free и /cancel_request ========================

@router.message(Command("free"))
async def cmd_free(message: types.Message):
    user_id = message.from_user.id

    if not _is_user_registered(user_id):
        await message.answer("❌ Вы не зарегистрированы!")
        return

    from utils.role_utils import get_user_role as get_user_role_name
    role_name = get_user_role_name(user_id)

    if not role_name:
        await message.answer("❌ У вас нет активной роли.")
        return

    status_data = load_roles_status()
    if role_name not in status_data:
        await message.answer(f"❌ Роль '{role_name}' не найдена.")
        return

    status_data[role_name]['status'] = 'свободна'
    status_data[role_name]['owner_id'] = None
    status_data[role_name]['username'] = None

    if save_roles_status(status_data):
        await message.answer(
            f"✅ <b>Роль «{role_name}» освобождена!</b>\n\n"
            f"Теперь она доступна для других.",
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Ошибка сохранения.")


@router.message(Command("cancel_request"))
async def cmd_cancel_request(message: types.Message):
    user_id = message.from_user.id

    request_id, request = _get_active_request(user_id)
    if not request:
        await message.answer("❌ У вас нет активных заявок.")
        return

    requests = _load_requests()
    requests[request_id]['status'] = 'canceled'
    requests[request_id]['updated_at'] = datetime.now().isoformat()
    _save_requests(requests)

    # Возвращаем роль в "свободна"
    role_name = request.get('role')
    season = request.get('season')
    if role_name and season:
        from utils.role_utils import update_role_status
        update_role_status(role_name, season, "свободна")

    await message.answer(
        f"✅ Заявка #{request_id} на роль «{role_name}» отменена."
    )


# ======================== УВЕДОМЛЕНИЕ АДМИНОВ ========================

async def _notify_admins(bot, request_id: int, request: dict):
    admins_file = os.path.join(DATA_DIR, 'admins', 'admins.txt')
    if not os.path.exists(admins_file):
        return

    admins = []
    with open(admins_file, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('|')
            if len(parts) >= 1:
                try:
                    admins.append(int(parts[0]))
                except ValueError:
                    continue

    text = (
        f"📨 <b>Новая заявка #{request_id}!</b>\n\n"
        f"👤 {request.get('full_name', 'без имени')}\n"
        f"🔖 @{request.get('username') or 'без юзернейма'}\n"
        f"🎭 Роль: {request.get('role')}\n"
        f"🏷️ Должность: {request.get('position_name')}\n"
        f"📁 Сезон: {request.get('season')}\n\n"
        f"Обработать: /requests"
    )

    for admin_id in admins:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Не удалось уведомить админа {admin_id}: {e}")