import os
import json
import time
import logging
from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from config import DATA_DIR, GENERAL_CHAT_ID, OWNER_ID
from utils.role_utils import (
    get_roles_by_season, get_all_seasons,
    load_roles_status, save_roles_status,
    format_role_display, make_role_key,
    get_user_role as get_user_role_short,
    get_user_role_key,
    get_role_by_id,
    update_role_status, update_role_status_by_id, free_role,
)
from utils.user_utils import (
    get_user_info, remove_user,
    get_changes_count, increment_changes_count,
    get_user_by_id,
)

logger = logging.getLogger(__name__)
router = Router()

REQUESTS_FILE = os.path.join(DATA_DIR, 'system', 'requests.json')

# Таймаут подачи заявки — 5 минут (300 секунд)
APPLY_TIMEOUT = 300


class ApplyStates(StatesGroup):
    choosing_season = State()
    choosing_role = State()
    choosing_position = State()
    confirming = State()
    confirming_replace = State()


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


def _get_max_role_changes() -> int:
    try:
        from handlers.settings_commands import load_settings
        settings = load_settings()
        return int(settings.get('max_role_changes', 3))
    except Exception as e:
        logger.error(f"Ошибка чтения лимита смен роли: {e}")
        return 3


# ======================== ПРОВЕРКА ТАЙМАУТА ========================

async def _check_timeout(callback: CallbackQuery, state: FSMContext) -> bool:
    """
    Проверяет не истёк ли таймаут подачи заявки (5 минут).
    Возвращает True если всё ок, False если таймаут истёк.
    """
    data = await state.get_data()
    started_at = data.get('started_at')

    if not started_at:
        return True  # нет таймера — ок

    elapsed = time.time() - started_at
    if elapsed > APPLY_TIMEOUT:
        await state.clear()
        try:
            await callback.message.edit_text(
                "⏰ <b>Время на подачу заявки истекло (5 минут).</b>\n\n"
                "Пожалуйста, начните заново: /apply",
                parse_mode="HTML"
            )
        except Exception:
            pass
        logger.info(f"⏰ Таймаут подачи заявки для {callback.from_user.id}")
        return False

    return True


# ======================== КЛАВИАТУРЫ (по ID) ========================

def create_apply_keyboard(seasons: list) -> InlineKeyboardMarkup:
    sorted_seasons = sorted(seasons)
    buttons = []
    for idx, season in enumerate(sorted_seasons):
        roles = get_roles_by_season(season)
        free_count = sum(1 for r in roles if r.get('status') == 'свободна')
        total = len(roles)
        buttons.append([InlineKeyboardButton(
            text=f"📁 {season} ({free_count}/{total})",
            callback_data=f"apply_season_{idx}"
        )])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="apply_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_role_keyboard(roles: list) -> InlineKeyboardMarkup:
    """callback_data: apply_role_id_<id> — стабильно, никогда не сломается."""
    buttons = []
    for role in roles:
        role_name = role.get('name', '?')
        role_id = role.get('id')
        status = role.get('status', 'свободна')

        if not role_id:
            buttons.append([InlineKeyboardButton(
                text=f"⚠️ {role_name} (нет ID)",
                callback_data="apply_none"
            )])
            continue

        if status == 'свободна':
            buttons.append([InlineKeyboardButton(
                text=f"✅ {role_name}",
                callback_data=f"apply_role_id_{role_id}"
            )])
        else:
            buttons.append([InlineKeyboardButton(
                text=f"🔒 {role_name} (занята)",
                callback_data="apply_none"
            )])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="apply_back_to_seasons")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="apply_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_position_keyboard(user_id: int = None) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="👑 Администратор", callback_data="apply_position_admin")],
        [InlineKeyboardButton(text="🛡️ Модератор", callback_data="apply_position_moder")],
        [InlineKeyboardButton(text="👤 Участник", callback_data="apply_position_member")],
    ]
    if user_id and user_id == OWNER_ID:
        buttons.append([InlineKeyboardButton(
            text="👑 Восстановить права владельца",
            callback_data="apply_position_owner_restore"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="apply_back_to_roles")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="apply_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ======================== КОМАНДЫ ========================

@router.message(Command("apply"))
async def cmd_apply(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда недоступна во флуд-чате.")
        return

    if _has_active_request(user_id):
        await message.answer(
            "⚠️ У вас уже есть активная заявка!\n"
            "Дождитесь её обработки или отмените через /cancel_request."
        )
        return

    from utils.admin_utils import is_owner
    if not is_owner(user_id):
        current_changes = get_changes_count(user_id)
        max_changes = _get_max_role_changes()

        if current_changes >= max_changes:
            await message.answer(
                f"⛔ <b>Вы исчерпали лимит смен роли ({max_changes}).</b>\n\n"
                f"Обратитесь к администрации для сброса.",
                parse_mode="HTML"
            )
            return

    seasons = get_all_seasons()
    if not seasons:
        await message.answer("❌ Сезоны не найдены.")
        return

    # ✅ Запускаем таймер
    await state.set_state(ApplyStates.choosing_season)
    await state.update_data(started_at=time.time())

    await message.answer(
        "🎯 Выберите сезон:\n\n"
        "⏰ <i>У вас 5 минут на подачу заявки.</i>",
        parse_mode="HTML",
        reply_markup=create_apply_keyboard(seasons)
    )


@router.callback_query(F.data.startswith("apply_season_"))
async def process_season(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    if not await _check_timeout(callback, state):
        return

    try:
        season_idx = int(callback.data.replace("apply_season_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка.", show_alert=True)
        return

    seasons = sorted(get_all_seasons())
    if season_idx >= len(seasons):
        await callback.answer("❌ Сезон не найден. Обновите /apply", show_alert=True)
        return

    season = seasons[season_idx]
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

    try:
        await callback.message.edit_text(
            f"📁 Сезон: <b>{season}</b>\n\nВыберите роль:\n✅ свободна | 🔒 занята",
            parse_mode="HTML",
            reply_markup=create_role_keyboard(roles)
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


@router.callback_query(F.data.startswith("apply_role_id_"))
async def process_role(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    if not await _check_timeout(callback, state):
        return

    try:
        role_id = int(callback.data.replace("apply_role_id_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка ID.", show_alert=True)
        return

    role = get_role_by_id(role_id)
    if not role:
        await callback.answer("❌ Роль не найдена. Обновите список.", show_alert=True)
        return

    if role.get('status') != 'свободна':
        await callback.answer("❌ Роль уже занята!", show_alert=True)
        return

    await state.update_data(
        role_key=role['key'],
        role=role['name'],
        role_id=role_id
    )
    await state.set_state(ApplyStates.choosing_position)

    try:
        await callback.message.edit_text(
            f"🎭 Роль: <b>{role['name']}</b>\n\nВыберите должность:",
            parse_mode="HTML",
            reply_markup=create_position_keyboard(callback.from_user.id)
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            logger.info(f"ℹ️ [process_role] не изменено")
        else:
            raise


@router.callback_query(F.data.startswith("apply_position_"))
async def process_position(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    if not await _check_timeout(callback, state):
        return

    position = callback.data.replace("apply_position_", "")

    position_names = {
        'admin': 'Администратор',
        'moder': 'Модератор',
        'member': 'Участник',
        'owner_restore': '👑 Восстановить права владельца',
    }
    position_name = position_names.get(position, position)

    if position == 'owner_restore' and callback.from_user.id != OWNER_ID:
        await callback.answer("⛔ Недоступно.", show_alert=True)
        return

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

    if not await _check_timeout(callback, state):
        return

    data = await state.get_data()
    user_id = callback.from_user.id

    old_role = get_user_role_short(user_id)

    if old_role:
        await state.set_state(ApplyStates.confirming_replace)
        await callback.message.edit_text(
            f"⚠️ <b>У вас уже есть роль «{old_role}».</b>\n\n"
            f"Если вашу новую заявку одобрят — старая роль освободится автоматически.\n\n"
            f"Продолжить?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Да, продолжить", callback_data="apply_replace_confirm")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="apply_cancel")]
            ])
        )
        return

    await _submit_request(callback, state, data, user_id)


@router.callback_query(F.data == "apply_replace_confirm")
async def apply_replace_confirm(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    if not await _check_timeout(callback, state):
        return

    data = await state.get_data()
    user_id = callback.from_user.id
    await _submit_request(callback, state, data, user_id)


async def _submit_request(callback: CallbackQuery, state: FSMContext, data: dict, user_id: int):
    requests = _load_requests()
    existing_ids = [int(k) for k in requests.keys() if str(k).isdigit()]
    request_id = max(existing_ids, default=0) + 1

    role_key = data.get('role_key')
    role_short = data.get('role')
    role_id = data.get('role_id')
    season = data.get('season')

    requests[str(request_id)] = {
        'user_id': user_id,
        'username': callback.from_user.username or '',
        'full_name': callback.from_user.full_name,
        'season': season,
        'role': role_short,
        'role_key': role_key,
        'role_id': role_id,
        'position': data.get('position'),
        'position_name': data.get('position_name'),
        'status': 'pending',
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }

    _save_requests(requests)

    # Обновляем статус по ID
    if role_id:
        update_role_status_by_id(role_id, "ожидает")

    await state.clear()

    await callback.message.edit_text(
        f"✅ <b>Заявка отправлена!</b>\n\n"
        f"📁 Сезон: {season}\n"
        f"🎭 Роль: {role_short}\n"
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

    if not await _check_timeout(callback, state):
        return

    seasons = get_all_seasons()
    await state.set_state(ApplyStates.choosing_season)
    await callback.message.edit_text(
        "🎯 Выберите сезон:",
        reply_markup=create_apply_keyboard(seasons)
    )


@router.callback_query(F.data == "apply_back_to_roles")
async def back_to_roles(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    if not await _check_timeout(callback, state):
        return

    data = await state.get_data()
    season = data.get('season')
    if not season:
        await callback.answer("❌ Сезон потерян. Начните заново.", show_alert=True)
        return
    roles = get_roles_by_season(season)
    await state.set_state(ApplyStates.choosing_role)
    await callback.message.edit_text(
        f"📁 Сезон: <b>{season}</b>\n\nВыберите роль:",
        parse_mode="HTML",
        reply_markup=create_role_keyboard(roles)
    )


@router.callback_query(F.data == "apply_back_to_position")
async def back_to_position(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    if not await _check_timeout(callback, state):
        return

    await state.set_state(ApplyStates.choosing_position)
    await callback.message.edit_text(
        "Выберите должность:",
        reply_markup=create_position_keyboard(callback.from_user.id)
    )


# ======================== /free ========================

@router.message(Command("free"))
async def cmd_free(message: types.Message):
    user_id = message.from_user.id

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда недоступна во флуд-чате.")
        return

    role_short = get_user_role_short(user_id)

    if not role_short:
        await message.answer("❌ У вас нет активной роли.")
        return

    await message.answer(
        f"⚠️ <b>Вы уверены?</b>\n\n"
        f"Вы хотите освободить роль <b>{role_short}</b>?\n"
        f"Это действие нельзя отменить.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, освободить", callback_data="free_confirm"),
                InlineKeyboardButton(text="❌ Нет, отмена", callback_data="free_cancel")
            ]
        ])
    )


@router.callback_query(F.data == "free_confirm")
async def free_confirm(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id

    role_short = get_user_role_short(user_id)
    role_key = get_user_role_key(user_id)

    if not role_short or not role_key:
        await callback.message.edit_text("❌ У вас нет активной роли.")
        return

    status_data = load_roles_status()
    if role_key not in status_data:
        await callback.message.edit_text(f"❌ Роль '{role_short}' не найдена.")
        return

    status_data[role_key]['status'] = 'свободна'
    status_data[role_key]['owner_id'] = None
    status_data[role_key]['username'] = None

    if save_roles_status(status_data):
        try:
            removed = remove_user(user_id)
            if removed:
                logger.info(f"🗑️ Пользователь {user_id} удалён из users.json")
        except Exception as e:
            logger.error(f"Ошибка удаления {user_id}: {e}")

        await callback.message.edit_text(
            f"✅ <b>Роль «{role_short}» освобождена!</b>\n\n"
            f"Теперь она доступна для других.",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text("❌ Ошибка сохранения.")


@router.callback_query(F.data == "free_cancel")
async def free_cancel(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("❌ Освобождение роли отменено.")


# ======================== /cancel_request ========================

@router.message(Command("cancel_request"))
async def cmd_cancel_request(message: types.Message):
    user_id = message.from_user.id

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда недоступна во флуд-чате.")
        return

    request_id, request = _get_active_request(user_id)
    if not request:
        await message.answer("❌ У вас нет активных заявок.")
        return

    requests = _load_requests()
    requests[request_id]['status'] = 'canceled'
    requests[request_id]['updated_at'] = datetime.now().isoformat()
    _save_requests(requests)

    role_id = request.get('role_id')
    if role_id:
        update_role_status_by_id(role_id, "свободна")

    await message.answer(
        f"✅ Заявка #{request_id} на роль «{request.get('role')}» отменена."
    )


# ======================== УВЕДОМЛЕНИЕ АДМИНОВ ========================

async def _notify_admins(bot, request_id: int, request: dict):
    from config import ADMIN_GROUP_ID
    from utils.admin_utils import load_admins

    text = (
        f"📨 <b>Новая заявка #{request_id}!</b>\n\n"
        f"👤 {request.get('full_name', 'без имени')}\n"
        f"🔖 @{request.get('username') or 'без юзернейма'}\n"
        f"🎭 Роль: {request.get('role')}\n"
        f"🏷️ Должность: {request.get('position_name')}\n"
        f"📁 Сезон: {request.get('season')}\n\n"
        f"Обработать: /requests"
    )

    if ADMIN_GROUP_ID:
        try:
            await bot.send_message(ADMIN_GROUP_ID, text, parse_mode="HTML")
            logger.info(f"📨 Уведомление о заявке #{request_id} отправлено в админ-группу")
            return
        except Exception as e:
            logger.error(f"❌ Не удалось отправить в админ-группу: {e} — отправляю в ЛС")

    admins = load_admins()
    for admin in admins:
        if admin.get('rank') not in [1, 2]:
            continue
        try:
            await bot.send_message(admin['id'], text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Не удалось уведомить админа {admin['id']}: {e}")