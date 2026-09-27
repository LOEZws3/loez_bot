"""
/clearme — полная очистка данных юзера.
История (users_history) НЕ удаляется.
"""

import os
import json
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import GENERAL_CHAT_ID, DATA_DIR
from utils.admin_utils import is_admin, is_owner, load_admins, save_admins
from utils.user_utils import get_user_by_id, remove_user
from utils.role_utils import (
    load_roles_status, save_roles_status,
    get_user_role_key,
)

logger = logging.getLogger(__name__)
router = Router()


class ClearMeStates(StatesGroup):
    waiting_for_confirm_button = State()
    waiting_for_final_phrase = State()


# ======================== ВСПОМОГАТЕЛЬНЫЕ ========================

def _delete_requests(user_id: int) -> int:
    """Удаляет все заявки юзера из requests.json. Возвращает число удалённых."""
    path = os.path.join(DATA_DIR, 'system', 'requests.json')
    if not os.path.exists(path):
        return 0
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return 0
    if not isinstance(data, dict):
        return 0

    removed = 0
    for req_id in list(data.keys()):
        req = data[req_id]
        if isinstance(req, dict) and req.get('user_id') == user_id:
            del data[req_id]
            removed += 1

    if removed > 0:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return removed


def _delete_rest_request(user_id: int) -> bool:
    """Удаляет заявку на рест юзера."""
    from handlers.utils import load_rest_requests, save_rest_requests
    data = load_rest_requests()
    if str(user_id) in data:
        del data[str(user_id)]
        save_rest_requests(data)
        return True
    return False


def _delete_unsubscribed(user_id: int) -> bool:
    """Удаляет отписку от калов."""
    from handlers.utils import load_unsubscribed, save_unsubscribed
    data = load_unsubscribed()
    if str(user_id) in data:
        del data[str(user_id)]
        save_unsubscribed(data)
        return True
    return False


def _free_role(user_id: int) -> str:
    """Освобождает роль юзера. Возвращает короткое имя роли или ''."""
    role_key = get_user_role_key(user_id)
    if not role_key:
        return ''

    status_data = load_roles_status()
    if role_key not in status_data:
        return ''

    from utils.role_utils import format_role_display
    role_short = format_role_display(role_key)

    status_data[role_key]['status'] = 'свободна'
    status_data[role_key]['owner_id'] = None
    status_data[role_key]['username'] = None
    save_roles_status(status_data)
    return role_short


async def _do_clear(bot, user_id: int) -> dict:
    """
    Полная очистка данных юзера.
    Возвращает отчёт: {'role': ..., 'requests': N, 'rest': bool, 'unsub': bool}
    """
    report = {'role': '', 'requests': 0, 'rest': False, 'unsub': False}

    # 1. Удаляем из users.json
    remove_user(user_id)

    # 2. Удаляем из admins.json (если был)
    admins = load_admins()
    new_admins = [a for a in admins if a['id'] != user_id]
    if len(new_admins) != len(admins):
        save_admins(new_admins)

    # 3. Освобождаем роль
    report['role'] = _free_role(user_id)

    # 4. Удаляем заявки на роли
    report['requests'] = _delete_requests(user_id)

    # 5. Удаляем заявку на рест
    report['rest'] = _delete_rest_request(user_id)

    # 6. Удаляем отписку от калов
    report['unsub'] = _delete_unsubscribed(user_id)

    # 7. Снимаем тег в чате
    try:
        await bot.set_chat_member_tag(chat_id=GENERAL_CHAT_ID, user_id=user_id, tag="")
        logger.info(f"🏷️ Снят тег у {user_id}")
    except Exception as e:
        logger.error(f"❌ Не удалось снять тег: {e}")

    logger.info(f"🧹 CLEARME {user_id}: role={report['role']}, requests={report['requests']}, rest={report['rest']}, unsub={report['unsub']}")
    return report


# ======================== КОМАНДА /CLEARME ========================

@router.message(Command('clearme'))
async def cmd_clearme(message: Message, state: FSMContext):
    """Юзер чистит свои данные. 3 шага подтверждения."""
    user_id = message.from_user.id

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда недоступна во флуд-чате.")
        return

    await state.clear()
    await state.update_data(clear_target=user_id, clear_self=True)
    await state.set_state(ClearMeStates.waiting_for_confirm_button)

    await message.answer(
        "⚠️ <b>ВНИМАНИЕ! Полная очистка данных</b>\n\n"
        "Будут удалены:\n"
        "• Ваша запись в users.json\n"
        "• Права администратора (если были)\n"
        "• Ваша роль (освободится)\n"
        "• Все ваши заявки\n"
        "• Ваша отписка от калов\n"
        "• Тег в чате\n\n"
        "✅ История сохранится.\n\n"
        "<b>Продолжить?</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, продолжить", callback_data="clearme_confirm_1"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="clearme_cancel")
            ]
        ])
    )


@router.callback_query(F.data == "clearme_cancel")
async def clearme_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    try:
        await callback.message.edit_text("❌ Очистка отменена.")
    except Exception:
        pass


@router.callback_query(F.data == "clearme_confirm_1")
async def clearme_confirm_1(callback: CallbackQuery, state: FSMContext):
    """Второе подтверждение (кнопка)."""
    await callback.answer()

    data = await state.get_data()
    target_id = data.get('clear_target')
    is_self = data.get('clear_self', True)

    if not target_id:
        await callback.message.edit_text("❌ Данные потеряны. Начните заново.")
        await state.clear()
        return

    if is_self:
        # Юзер чистит себя — третье подтверждение (написать ник delete)
        user = callback.from_user
        full_name = user.full_name or 'User'
        await state.set_state(ClearMeStates.waiting_for_final_phrase)
        await callback.message.edit_text(
            f"⚠️ <b>ПОСЛЕДНЕЕ ПРЕДУПРЕЖДЕНИЕ!</b>\n\n"
            f"Чтобы подтвердить удаление, напишите <b>одним сообщением</b>:\n\n"
            f"<code>{full_name} delete</code>\n\n"
            f"(ваш ник + слово delete)\n\n"
            f"❌ Любое другое сообщение отменит очистку.",
            parse_mode="HTML"
        )
        return

    # Владелец чистит другого — тут уже подтверждено, делаем сразу
    report = await _do_clear(callback.bot, int(target_id))

    await state.clear()
    await callback.message.edit_text(
        f"✅ <b>Данные пользователя <code>{target_id}</code> очищены.</b>\n\n"
        f"📌 Освобождена роль: {report['role'] or '—'}\n"
        f"📝 Удалено заявок: {report['requests']}\n"
        f"⏳ Заявка на рест: {'удалена' if report['rest'] else '—'}\n"
        f"📢 Отписка от калов: {'удалена' if report['unsub'] else '—'}",
        parse_mode="HTML"
    )
    logger.info(f"🧹 Владелец {callback.from_user.id} очистил {target_id}")


@router.message(ClearMeStates.waiting_for_final_phrase)
async def clearme_final_phrase(message: Message, state: FSMContext):
    """Третье подтверждение: ник + delete."""
    user_id = message.from_user.id
    text = (message.text or "").strip()

    data = await state.get_data()
    target_id = data.get('clear_target')
    is_self = data.get('clear_self', True)

    if not target_id:
        await state.clear()
        await message.answer("❌ Данные потеряны.")
        return

    # Проверка: текст = "<full_name> delete"?
    user = message.from_user
    full_name = (user.full_name or 'User').strip()

    expected = f"{full_name} delete".lower().strip()
    actual = text.lower().strip()

    if actual != expected:
        await state.clear()
        await message.answer(
            "❌ Неверная фраза. Очистка отменена.",
        )
        return

    # Всё совпало — чистим
    report = await _do_clear(message.bot, target_id)
    await state.clear()

    await message.answer(
        f"✅ <b>Ваши данные очищены.</b>\n\n"
        f"📌 Освобождена роль: {report['role'] or '—'}\n"
        f"📝 Удалено заявок: {report['requests']}\n"
        f"⏳ Заявка на рест: {'удалена' if report['rest'] else '—'}\n"
        f"📢 Отписка от калов: {'удалена' if report['unsub'] else '—'}\n\n"
        f"💾 История сохранена.\n\n"
        f"📌 Чтобы зарегистрироваться заново — используйте /apply.",
        parse_mode="HTML"
    )


# ======================== CLEAR ДРУГОГО (вызывается из /userstats) ========================

@router.callback_query(F.data.startswith("clearme_other_"))
async def clearme_other(callback: CallbackQuery, state: FSMContext):
    """Владелец чистит другого (вызывается из /userstats)."""
    await callback.answer()

    caller_id = callback.from_user.id
    if not is_owner(caller_id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return

    try:
        target_id = int(callback.data.replace("clearme_other_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка.", show_alert=True)
        return

    # Ставим состояние для третьего подтверждения
    await state.update_data(clear_target=target_id, clear_self=False)
    await state.set_state(ClearMeStates.waiting_for_final_phrase)

    # Получаем инфу о цели
    target = get_user_by_id(target_id)
    target_name = target.get('full_name', '?') if target else '?'

    await callback.message.edit_text(
        f"⚠️ <b>Очистка данных пользователя</b>\n\n"
        f"👤 {target_name}\n"
        f"🆔 <code>{target_id}</code>\n\n"
        f"Чтобы подтвердить, напишите <b>одним сообщением</b>:\n\n"
        f"<code>{target_name} delete</code>\n\n"
        f"❌ Любое другое сообщение отменит очистку.",
        parse_mode="HTML"
    )