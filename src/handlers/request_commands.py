import os
import json
import html
import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import DATA_DIR, GENERAL_CHAT_ID
from utils.admin_utils import is_admin
from utils.role_utils import (
    load_roles_status, save_roles_status,
    get_role_by_name, update_role_status
)

logger = logging.getLogger(__name__)
router = Router()

REQUESTS_FILE = os.path.join(DATA_DIR, 'system', 'requests.json')
ADMINS_FILE = os.path.join(DATA_DIR, 'admins', 'admins.txt')
USERS_FILE = os.path.join(DATA_DIR, 'users', 'users.txt')

POSITION_RANK = {'admin': 2, 'moder': 3}
POSITION_NAMES = {'admin': 'Администратор', 'moder': 'Модератор', 'member': 'Участник'}


class RejectReason(StatesGroup):
    waiting_for_reason = State()


# ======================== РАБОТА С ФАЙЛАМИ ========================

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


def _get_pending() -> list:
    requests = _load_requests()
    return [(rid, req) for rid, req in requests.items()
            if isinstance(req, dict) and req.get('status') == 'pending']


# ======================== РАНГИ И ИРИС ========================

def _add_admin(user_id: int, username: str, full_name: str, rank: int) -> bool:
    try:
        if os.path.exists(ADMINS_FILE):
            with open(ADMINS_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith(str(user_id) + '|'):
                        return True
        with open(ADMINS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{user_id}|{username or ''}|{full_name or ''}|{rank}\n")
        logger.info(f"✅ {user_id} → admins.txt (ранг {rank})")
        return True
    except Exception as e:
        logger.error(f"Ошибка admins.txt: {e}")
        return False


def _add_user(user_id: int, username: str, full_name: str, role: str) -> bool:
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith(str(user_id) + '|'):
                        return True
        with open(USERS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{user_id}|{username or ''}|{full_name or ''}|{role}|\n")
        logger.info(f"✅ {user_id} → users.txt (роль {role})")
        return True
    except Exception as e:
        logger.error(f"Ошибка users.txt: {e}")
        return False


async def _send_to_iris(bot, user_id: int, rank: int, position_name: str):
    """TODO: Заглушка для @iris_moon_bot"""
    logger.info(f"🔔 [ИРИС-ЗАГЛУШКА] Повысить {user_id} до ранга {rank} ({position_name})")


# ======================== КОМАНДЫ ========================

@router.message(Command('requests'))
async def cmd_requests(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return

    pending = _get_pending()
    if not pending:
        await message.answer("📭 Нет заявок в ожидании.")
        return

    buttons = []
    for req_id, req in pending:
        safe_name = html.escape(req.get('full_name', 'без имени'))
        safe_role = html.escape(req.get('role', '?'))
        buttons.append([InlineKeyboardButton(
            text=f"{safe_name} — {safe_role}",
            callback_data=f"view_req_{req_id}"
        )])
    buttons.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_requests")])

    await message.answer(
        f"📝 <b>Заявки в ожидании ({len(pending)})</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.message(Command('approve'))
async def cmd_approve(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /approve [ID заявки]")
        return

    request_id = parts[1].strip()
    requests = _load_requests()
    if request_id not in requests:
        await message.answer(f"❌ Заявка #{request_id} не найдена.")
        return

    if requests[request_id].get('status') != 'pending':
        await message.answer(f"❌ Заявка #{request_id} уже обработана.")
        return

    # Эмулируем нажатие кнопки
    await message.answer(
        f"ℹ️ Используйте /requests → выберите заявку → «Одобрить»."
    )


@router.message(Command('reject'))
async def cmd_reject(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Используйте: /reject [ID заявки]")
        return

    request_id = parts[1].strip()
    requests = _load_requests()
    if request_id not in requests:
        await message.answer(f"❌ Заявка #{request_id} не найдена.")
        return

    if requests[request_id].get('status') != 'pending':
        await message.answer(f"❌ Заявка #{request_id} уже обработана.")
        return

    await state.update_data(request_id=request_id)
    await state.set_state(RejectReason.waiting_for_reason)
    await message.answer("📝 Напишите причину отклонения заявки:")


@router.message(RejectReason.waiting_for_reason)
async def reject_with_reason(message: Message, state: FSMContext):
    reason = (message.text or "")[:500]

    data = await state.get_data()
    request_id = data.get('request_id')

    if not request_id:
        await message.answer("❌ ID заявки потерян. Попробуйте снова /reject.")
        await state.clear()
        return

    requests = _load_requests()
    if request_id in requests and requests[request_id].get('status') == 'pending':
        requests[request_id]['status'] = 'rejected'
        requests[request_id]['reason'] = reason
        requests[request_id]['updated_at'] = datetime.now().isoformat()
        _save_requests(requests)

        role_name = requests[request_id].get('role')
        season = requests[request_id].get('season')
        if role_name and season:
            update_role_status(role_name, season, "свободна")

        await message.answer(f"✅ Заявка #{request_id} отклонена.\nПричина: {html.escape(reason)}")
    else:
        await message.answer(f"❌ Заявка #{request_id} уже обработана.")

    await state.clear()


# ======================== INLINE-ОБРАБОТЧИКИ ========================

@router.callback_query(F.data == "refresh_requests")
async def refresh_requests(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.message.edit_text("⛔ Доступ запрещён.")
        return

    pending = _get_pending()
    if not pending:
        await callback.message.edit_text("📭 Нет заявок в ожидании.")
        return

    buttons = []
    for req_id, req in pending:
        safe_name = html.escape(req.get('full_name', 'без имени'))
        safe_role = html.escape(req.get('role', '?'))
        buttons.append([InlineKeyboardButton(
            text=f"{safe_name} — {safe_role}",
            callback_data=f"view_req_{req_id}"
        )])
    buttons.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_requests")])

    await callback.message.edit_text(
        f"📝 <b>Заявки в ожидании ({len(pending)})</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("view_req_"))
async def view_request(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    request_id = callback.data.replace("view_req_", "")
    requests = _load_requests()
    request = requests.get(request_id)

    if not request or request.get('status') != 'pending':
        await callback.message.edit_text(
            "❌ Заявка уже обработана.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_requests")]
            ])
        )
        return

    safe_name = html.escape(request.get('full_name', '?'))
    safe_role = html.escape(request.get('role', '?'))
    safe_position = html.escape(request.get('position_name', request.get('position', '?')))

    text = (
        f"📝 <b>Заявка #{request_id}</b>\n\n"
        f"👤 {safe_name}\n"
        f"🔖 @{request.get('username') or 'нет'}\n"
        f"🆔 <code>{request.get('user_id')}</code>\n"
        f"📌 Роль: {safe_role}\n"
        f"🏷️ Должность: {safe_position}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_req_{request_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_req_{request_id}")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_requests")]
    ])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith("approve_req_"))
async def approve_request_callback(callback: CallbackQuery):
    await callback.answer()
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    request_id = callback.data.replace("approve_req_", "")
    requests = _load_requests()
    request = requests.get(request_id)

    if not request or request.get('status') != 'pending':
        await callback.message.edit_text("❌ Заявка уже обработана.")
        return

    role_name = request.get('role')
    season = request.get('season')
    user_id = request.get('user_id')
    username = request.get('username', '')
    full_name = request.get('full_name', '')
    position = request.get('position', 'member')
    position_name = request.get('position_name', POSITION_NAMES.get(position, 'Участник'))

    if not role_name or not season:
        await callback.message.edit_text("❌ Ошибка: нет роли или сезона.")
        return

    # 1. Занимаем роль
    status_data = load_roles_status()
    if role_name in status_data:
        status_data[role_name]['status'] = 'занята'
        status_data[role_name]['owner_id'] = user_id
        status_data[role_name]['username'] = username
        save_roles_status(status_data)

    # 2. Обновляем заявку
    requests[request_id]['status'] = 'approved'
    requests[request_id]['updated_at'] = datetime.now().isoformat()
    _save_requests(requests)

    # 3. users.txt
    _add_user(user_id, username, full_name, role_name)

    # 4. Ранг
    rank = POSITION_RANK.get(position)
    if rank:
        _add_admin(user_id, username, full_name, rank)
        await _send_to_iris(callback.bot, user_id, rank, position_name)

    # 5. Уведомление пользователю
    try:
        await callback.bot.send_message(
            user_id,
            f"✅ <b>Заявка одобрена!</b>\n\n"
            f"📌 Роль: <b>{html.escape(role_name)}</b>\n"
            f"🏷️ Должность: <b>{html.escape(position_name)}</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Уведомление {user_id}: {e}")

    await callback.message.edit_text(
        f"✅ <b>Заявка #{request_id} одобрена!</b>\n\n"
        f"👤 {html.escape(full_name)}\n"
        f"📌 {html.escape(role_name)}\n"
        f"🏷️ {html.escape(position_name)}"
        + (f"\n⭐ Ранг: {rank}" if rank else ""),
        parse_mode="HTML"
    )

    logger.info(f"Админ {admin_id} одобрил заявку #{request_id}")


@router.callback_query(F.data.startswith("reject_req_"))
async def reject_request_callback(callback: CallbackQuery):
    await callback.answer()
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    request_id = callback.data.replace("reject_req_", "")
    requests = _load_requests()
    request = requests.get(request_id)

    if not request or request.get('status') != 'pending':
        await callback.message.edit_text("❌ Заявка уже обработана.")
        return

    requests[request_id]['status'] = 'rejected'
    requests[request_id]['updated_at'] = datetime.now().isoformat()
    _save_requests(requests)

    role_name = request.get('role')
    season = request.get('season')
    if role_name and season:
        update_role_status(role_name, season, "свободна")

    user_id = request.get('user_id')
    try:
        await callback.bot.send_message(
            user_id,
            f"❌ <b>Ваша заявка на роль '{html.escape(role_name or '?')}' отклонена.</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Уведомление {user_id}: {e}")

    await callback.message.edit_text(
        f"❌ <b>Заявка #{request_id} отклонена.</b>",
        parse_mode="HTML"
    )

    logger.info(f"Админ {admin_id} отклонил заявку #{request_id}")


@router.callback_query(F.data == "back_to_requests")
async def back_to_requests(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.message.edit_text("⛔ Доступ запрещён.")
        return

    pending = _get_pending()
    if not pending:
        await callback.message.edit_text("📭 Нет заявок.")
        return

    buttons = []
    for req_id, req in pending:
        safe_name = html.escape(req.get('full_name', 'без имени'))
        safe_role = html.escape(req.get('role', '?'))
        buttons.append([InlineKeyboardButton(
            text=f"{safe_name} — {safe_role}",
            callback_data=f"view_req_{req_id}"
        )])
    buttons.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_requests")])

    await callback.message.edit_text(
        f"📝 <b>Заявки в ожидании ({len(pending)})</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )