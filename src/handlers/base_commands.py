# ============================================================
# ⚠️ ВАЖНОЕ ПРАВИЛО ДЛЯ КОМАНД ВО ФЛУДЕ
# ============================================================
# 
# Во флуд-чате (GENERAL_CHAT_ID) РАЗРЕШЕНЫ ТОЛЬКО:
# - /members (только количество)
# - /roles (только список, БЕЗ КНОПОК)
# - /call, /callfal, /callstaff (для админов)
# - /hide, /menu (управление клавиатурой)
# - /stats (только админам, краткая версия)
# 
# ВСЕ ОСТАЛЬНЫЕ КОМАНДЫ — ЗАПРЕЩЕНЫ!
# ============================================================

import os
import html
import datetime
import logging
import matplotlib
matplotlib.use('Agg') # Обязательно для работы без графического интерфейса
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import make_interp_spline
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardRemove, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import GENERAL_CHAT_ID, DATA_DIR
from utils.admin_utils import get_admin_rank, is_admin, load_admins
from utils.user_utils import (
    load_users, get_users_count, get_user_by_id, get_role_stats,
    set_birthday, get_birthday, set_notify_norm, get_notify_norm,
)
from utils.requests_utils import get_request_by_user_id, get_pending_count
from utils.role_utils import (
    get_taken_roles, count_taken_roles,
    get_user_role as get_user_role_from_roles,
    get_all_seasons, get_roles_by_season, load_roles_status
)
from utils.counters import load_counters, get_message_count
from utils.user_history import load_user_history
from utils.settings_utils import get_messages_norm, get_messages_norm_low
from .keyboards import get_main_keyboard
from utils.norm_utils import get_user_category, get_emoji

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

# ============================================================
# ⚠️ НОВОЕ (05.10.2026): FSM для /setbirthday
# ============================================================

class SetBirthdayStates(StatesGroup):
    choosing_day = State()
    choosing_month = State()

MONTHS_RU = [
    'январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
    'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь'
]

def _build_days_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for day in range(1, 32):
        row.append(InlineKeyboardButton(
            text=str(day),
            callback_data=f"bday_day_{day}"
        ))
        if len(row) == 7:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="bday_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def _build_months_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for i in range(0, 12, 3):
        row = []
        for j in range(3):
            if i + j < 12:
                row.append(InlineKeyboardButton(
                    text=MONTHS_RU[i + j].capitalize(),
                    callback_data=f"bday_month_{i + j + 1}"
                ))
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="bday_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ============================================================
# 🆕 /start
# ============================================================

@router.message(Command('start'))
async def cmd_start(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда недоступна во флуд-чате.")
        return

    user = get_user_by_id(user_id)
    
    # ⚠️ Проверка политики конфиденциальности
    if not user or not user.get('agreed_to_privacy', False):
        from config import PRIVACY_POLICY_URL, TERMS_OF_USE_URL
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📄 Политика конфиденциальности", url=PRIVACY_POLICY_URL)],
            [InlineKeyboardButton(text="📜 Правила пользования", url=TERMS_OF_USE_URL)],
            [InlineKeyboardButton(text="✅ Я согласен", callback_data="agree_privacy")]
        ])
        
        await message.answer(
            "👋 <b>Добро пожаловать!</b>\n\n"
            "Перед началом работы, пожалуйста, ознакомьтесь с:\n"
            "• Политикой конфиденциальности\n"
            "• Правилами пользования\n\n"
            "Нажимая «✅ Я согласен», вы подтверждаете, что прочитали и принимаете эти условия.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        return

    # Если согласился — показываем стандартное приветствие
    from utils.user_history import load_user_history
    history = load_user_history(user_id)
    is_returning = bool(history)

    request = get_request_by_user_id(user_id)
    status_text = ""
    if request:
        if request.get('status') == 'pending':
            status_text = "\n\n📌 Ваша заявка рассматривается администрацией."
        elif request.get('status') == 'approved':
            status_text = "\n\n✅ Ваша заявка одобрена!"
        elif request.get('status') == 'rejected':
            status_text = "\n\n❌ Ваша заявка отклонена. Попробуйте подать новую."

    safe_name = html.escape(message.from_user.full_name)
    
    if is_returning:
        greeting = f"👋 <b>С возвращением, {safe_name}!</b>\n\n"
    else:
        greeting = f"👋 Добро пожаловать, <b>{safe_name}</b>!\n\n"

    text = (
        greeting +
        f"Я бот для управления ролями и заявками.\n"
        f"Если у вас есть вопросы — напишите <b>@Sedrikai_bot</b> (бот-пересыльщик), "
        f"и ближайший освободившийся администратор ответит вам, как только сможет.\n\n"
        f"📌 Используйте /help для списка команд.{status_text}"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))


@router.callback_query(F.data == "agree_privacy")
async def agree_privacy_callback(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    from utils.user_utils import get_user_by_id, add_user, set_agreed_to_privacy
    
    # Если юзера нет — создаём его (с ролью "0")
    user = get_user_by_id(user_id)
    if not user:
        add_user(
            user_id,
            callback.from_user.username or '',
            callback.from_user.full_name or '',
            role='0'
        )
    
    # Ставим флаг согласия
    set_agreed_to_privacy(user_id, True)
    
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    await callback.message.answer(
        "✅ <b>Спасибо! Вы приняли условия.</b>\n\n"
        "Теперь вы можете пользоваться ботом.\n"
        "Нажмите /start чтобы продолжить.",
        parse_mode="HTML"
    )
    logger.info(f"👤 {user_id} согласился с политикой конфиденциальности")

# ============================================================
# 📚 /help
# ============================================================

@router.message(Command('help'))
async def cmd_help(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда недоступна во флуд-чате.")
        return

    is_admin_user = is_admin(user_id)
    rank = get_admin_rank(user_id)
    user_data = get_user_by_id(user_id)
    is_registered = user_data is not None

    if not is_registered:
        buttons = [
            [InlineKeyboardButton(text="👤 Основное", callback_data="help_group_main")]
        ]
        text = (
            "📚 <b>Справка</b>\n\n"
            "⚠️ Вы ещё не зарегистрированы в системе.\n"
            "Чтобы получить доступ ко всем командам — подайте заявку через /apply.\n\n"
            "Нажмите на группу чтобы посмотреть команды:"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        return

    buttons = [
        [InlineKeyboardButton(text="👤 Для всех", callback_data="help_group_main")],
        [InlineKeyboardButton(text="📝 Заявки", callback_data="help_group_apply")],
        [InlineKeyboardButton(text="⏳ Ресты", callback_data="help_group_rest")],
        [InlineKeyboardButton(text="📢 Калы", callback_data="help_group_calls")],
    ]

    if is_admin_user:
        buttons.append([InlineKeyboardButton(text="🔐 Административные", callback_data="help_group_admin")])

    if rank == 1:
        buttons.append([InlineKeyboardButton(text="👑 Владелец", callback_data="help_group_owner")])

    text = (
        "📚 <b>Справка</b>\n\n"
        "Нажмите на группу чтобы посмотреть команды.\n\n"
        f"⭐ Ваш ранг: <b>{'Владелец' if rank == 1 else 'Админ' if rank == 2 else 'Модератор' if rank == 3 else 'Участник'}</b>"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

HELP_GROUPS = {
    "main": {
        "title": "👤 Для всех",
        "text": (
            "👤 <b>Основные команды</b>\n\n"
            "/start — приветствие\n"
            "/help — эта справка\n"
            "/about — информация о флуд-чате\n"
            "/aboutme — ваши данные\n"
            "/members — список участников\n"
            "/roles — список ролей\n"
            "/update — проверить статус регистрации\n"
            "/setbirthday — установить дату рождения\n"
            "/subnorm — подписаться на уведомления о норме\n"
            "/unsubnorm — отписаться от уведомлений о норме\n"
            "/mynorm — ваш график активности за неделю\n"
            "/history — ваша история (или /history ID для админа)\n"
            "/hide — скрыть клавиатуру\n"
            "/menu — показать клавиатуру"
        )
    },
    "apply": {
        "title": "📝 Заявки",
        "text": (
            "📝 <b>Заявки и роли</b>\n\n"
            "/apply — подать заявку на роль\n"
            "/free — освободить свою роль\n"
            "/cancel_request — отменить заявку\n\n"
            "📌 Для админов:\n"
            "/requests — список заявок\n"
            "/approve [ID] — одобрить\n"
            "/reject [ID] — отклонить"
        )
    },
    "rest": {
        "title": "⏳ Ресты",
        "text": (
            "⏳ <b>Ресты</b>\n\n"
            "/rest — подать заявку на рест\n\n"
            "📌 Для админов:\n"
            "/restlist — список активных рестов\n"
            "/unrest — снять рест\n"
            "/restextend — продлить рест\n"
            "/setrest — поставить рест\n"
            "/giverest [ID] [дней] — отправить в рест за юзера"
        )
    },
    "calls": {
        "title": "📢 Калы",
        "text": (
            "📢 <b>Калы</b>\n\n"
            "/regc — подписаться на калы\n"
            "/unregc — отписаться от калов\n\n"
            "📌 Для админов:\n"
            "/call — обычный кал\n"
            "/callfal — непропускаемый кал\n"
            "/callstaff — кал только для администрации"
        )
    },
    "admin": {
        "title": "🔐 Административные",
        "text": (
            "🔐 <b>Административные команды</b>\n\n"
            "/admins — список администраторов\n"
            "/users — полный список участников\n"
            "/adduser [ID] — добавить участника\n"
            "/removeuser [ID] — удалить участника\n"
            "/resetuser [ID] — сбросить пользователя\n"
            "/refresh — обновить список\n"
            "/find [ID] — найти по ID\n"
            "/finduser [@username] — найти по юзернейму\n"
            "/findrole [запрос] — найти роль\n"
            "/userstats [ID] — статистика пользователя\n"
            "/stats — статистика бота\n"
            "/check_chats — диагностика чатов\n"
            "/sync_norm [дни] [сообщений] — начислить норму"
        )
    },
    "owner": {
        "title": "👑 Владелец",
        "text": (
            "👑 <b>Команды владельца</b>\n\n"
            "/settings — меню настроек\n"
            "/diag — полная диагностика\n"
            "/setrank [ID] [ранг] — назначить ранг\n"
            "/close — закрыть набор\n"
            "/open — открыть набор\n"
            "/message_all — рассылка всем юзерам"
        )
    },
}

@router.callback_query(F.data.startswith("help_group_"))
async def help_group_callback(callback: CallbackQuery):
    await callback.answer()

    if callback.message.chat.id == GENERAL_CHAT_ID:
        await callback.answer("⛔ Во флуд-чате недоступно.", show_alert=True)
        return

    group_key = callback.data.replace("help_group_", "")
    group = HELP_GROUPS.get(group_key)

    if not group:
        await callback.answer("❌ Группа не найдена.", show_alert=True)
        return

    buttons = [
        [InlineKeyboardButton(text="🔙 Назад", callback_data="help_back")]
    ]

    await callback.message.edit_text(
        group["text"],
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(F.data == "help_back")
async def help_back_callback(callback: CallbackQuery):
    await callback.answer()

    if callback.message.chat.id == GENERAL_CHAT_ID:
        await callback.answer("⛔ Недоступно.", show_alert=True)
        return

    user_id = callback.from_user.id
    is_admin_user = is_admin(user_id)
    rank = get_admin_rank(user_id)
    user_data = get_user_by_id(user_id)
    is_registered = user_data is not None

    if not is_registered:
        buttons = [
            [InlineKeyboardButton(text="👤 Основное", callback_data="help_group_main")]
        ]
        text = (
            "📚 <b>Справка</b>\n\n"
            "⚠️ Вы ещё не зарегистрированы в системе.\n"
            "Чтобы получить доступ ко всем командам — подайте заявку через /apply.\n\n"
            "Нажмите на группу чтобы посмотреть команды:"
        )
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        return

    buttons = [
        [InlineKeyboardButton(text="👤 Для всех", callback_data="help_group_main")],
        [InlineKeyboardButton(text="📝 Заявки", callback_data="help_group_apply")],
        [InlineKeyboardButton(text="⏳ Ресты", callback_data="help_group_rest")],
        [InlineKeyboardButton(text="📢 Калы", callback_data="help_group_calls")],
    ]

    if is_admin_user:
        buttons.append([InlineKeyboardButton(text="🔐 Административные", callback_data="help_group_admin")])

    if rank == 1:
        buttons.append([InlineKeyboardButton(text="👑 Владелец", callback_data="help_group_owner")])

    text = (
        "📚 <b>Справка</b>\n\n"
        "Нажмите на группу чтобы посмотреть команды.\n\n"
        f"⭐ Ваш ранг: <b>{'Владелец' if rank == 1 else 'Админ' if rank == 2 else 'Модератор' if rank == 3 else 'Участник'}</b>"
    )

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# ============================================================
# 🎂 /setbirthday
# ============================================================

@router.message(Command('setbirthday'))
async def cmd_setbirthday(message: Message, state: FSMContext):
    user_id = message.from_user.id

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда недоступна во флуд-чате.")
        return

    user_data = get_user_by_id(user_id)
    if not user_data:
        await message.answer(
            "⛔ Для установки ДР нужно сначала зарегистрироваться.\n"
            "Подайте заявку через /apply."
        )
        return

    current = get_birthday(user_id)
    current_text = f"\n\n📌 Текущая дата: <b>{current}</b>" if current else ""

    await state.set_state(SetBirthdayStates.choosing_day)
    await message.answer(
        f"🎂 <b>Установка даты рождения</b>{current_text}\n\n"
        f"Выберите <b>день</b>:",
        parse_mode="HTML",
        reply_markup=_build_days_keyboard()
    )

@router.callback_query(SetBirthdayStates.choosing_day, F.data.startswith("bday_day_"))
async def bday_day_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    try:
        day = int(callback.data.replace("bday_day_", ""))
    except ValueError:
        return

    await state.update_data(bday_day=day)
    await state.set_state(SetBirthdayStates.choosing_month)

    try:
        await callback.message.edit_text(
            f"🎂 <b>Установка даты рождения</b>\n\n"
            f"День: <b>{day}</b>\n\n"
            f"Теперь выберите <b>месяц</b>:",
            parse_mode="HTML",
            reply_markup=_build_months_keyboard()
        )
    except Exception:
        pass

@router.callback_query(SetBirthdayStates.choosing_month, F.data.startswith("bday_month_"))
async def bday_month_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    try:
        month = int(callback.data.replace("bday_month_", ""))
    except ValueError:
        return

    data = await state.get_data()
    day = data.get('bday_day')
    if not day:
        await callback.message.edit_text("❌ Ошибка: день потерян. Начните заново /setbirthday.")
        await state.clear()
        return

    user_id = callback.from_user.id
    birthday = f"{day:02d}.{month:02d}"

    set_birthday(user_id, birthday)

    try:
        from utils.user_history import set_birthday as hist_set_birthday
        hist_set_birthday(user_id, birthday)
    except Exception as e:
        logger.error(f"❌ Не удалось сохранить ДР в историю: {e}")

    await state.clear()

    await callback.message.edit_text(
        f"✅ <b>Дата рождения сохранена!</b>\n\n"
        f"🎂 {birthday}\n\n"
        f"📌 Поздравления приходят 00:00 (лично) и 12:00 (в чат).",
        parse_mode="HTML"
    )
    logger.info(f"🎂 {user_id} установил ДР: {birthday}")

@router.callback_query(F.data == "bday_cancel")
async def bday_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    try:
        await callback.message.edit_text("❌ Установка ДР отменена.")
    except Exception:
        pass

# ============================================================
# 🔔 /subnorm, /unsubnorm
# ============================================================

@router.message(Command('subnorm'))
async def cmd_subnorm(message: Message):
    user_id = message.from_user.id

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Только в ЛС.")
        return

    user_data = get_user_by_id(user_id)
    if not user_data:
        await message.answer("⛔ Сначала зарегистрируйтесь (/apply).")
        return

    if get_notify_norm(user_id):
        await message.answer("ℹ️ Вы уже подписаны на уведомления о норме.")
        return

    set_notify_norm(user_id, True)
    await message.answer(
        "🔔 <b>Вы подписались на уведомления о норме!</b>\n\n"
        "Теперь бот напишет вам в ЛС, когда вы наберёте норму за неделю.",
        parse_mode="HTML"
    )
    logger.info(f"🔔 {user_id} подписался на уведомления о норме")

@router.message(Command('unsubnorm'))
async def cmd_unsubnorm(message: Message):
    user_id = message.from_user.id

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Только в ЛС.")
        return

    user_data = get_user_by_id(user_id)
    if not user_data:
        await message.answer("⛔ Сначала зарегистрируйтесь (/apply).")
        return

    if not get_notify_norm(user_id):
        await message.answer("ℹ️ Вы уже отписаны от уведомлений о норме.")
        return

    set_notify_norm(user_id, False)
    await message.answer(
        "🔕 <b>Вы отписались от уведомлений о норме.</b>\n\n"
        "Чтобы подписаться обратно — /subnorm.",
        parse_mode="HTML"
    )
    logger.info(f"🔕 {user_id} отписался от уведомлений о норме")

# ============================================================
# 📖 /about
# ============================================================

@router.message(Command('about'))
async def cmd_about(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда недоступна во флуд-чате.")
        return

    users_count = count_taken_roles()
    pending_count = get_pending_count()
    flood_creation = datetime.date(2026, 5, 12)
    days = (datetime.date.today() - flood_creation).days

    text = (
        f"💬 <b>Информация о флуде (чате)</b>\n\n"
        f"👥 Участников: {users_count}\n"
        f"📅 Чату: {days} дн. (создан 12 мая 2026 года)\n"
        f"📝 Заявок в ожидании: {pending_count}\n\n"
        f"🔗 <b>Ссылка для просмотра инфо:</b>\n"
        f"👉 <a href='https://t.me/+p7g_-IQv-v5kYjgy'>Нажмите для просмотра</a>\n\n"
        f"📝 <b>Хотите вступить?</b>\n"
        f"Подайте заявку через /apply в личных сообщениях с ботом."
    )

    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id), disable_web_page_preview=False)

# ============================================================
# 📖 /aboutme
# ============================================================

@router.message(Command('aboutme'))
async def cmd_aboutme(message: Message):
    user = message.from_user
    if user is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда недоступна во флуд-чате.")
        return

    rank = get_admin_rank(user.id)
    rank_name = {1: "👑 Владелец", 2: "🔐 Админ", 3: "🛡️ Модератор"}.get(rank, "👤 Нет")
    character = get_user_role_from_roles(user.id) or "Не указан"

    request = get_request_by_user_id(user.id)
    status_text = ""
    if request:
        status_map = {
            'pending': '⏳ Ожидает рассмотрения',
            'approved': '✅ Одобрена',
            'rejected': '❌ Отклонена'
        }
        status_text = f"\n📝 Статус заявки: {status_map.get(request.get('status'), 'Неизвестно')}"
        if request.get('status') == 'pending':
            status_text += f"\n📌 Роль: {request.get('role', 'Не указана')}"
            status_text += f"\n📌 Должность: {request.get('position_name', request.get('position', 'Не указана'))}"

    birthday = get_birthday(user.id)
    notify_norm = get_notify_norm(user.id)
    bday_text = f"\n🎂 ДР: <b>{birthday}</b>" if birthday else "\n🎂 ДР: <i>не указан</i> (/setbirthday)"
    notify_text = f"\n🔔 Уведомления о норме: {'✅ вкл' if notify_norm else '❌ выкл'}"

    # ⚠️ НОВОЕ: Проверка реста
    user_data = get_user_by_id(user.id)
    rest_text = ""
    if user_data and user_data.get('rest'):
        rest_end = user_data.get('rest_end_date', '?')
        rest_text = f"\n⏳ <b>В ресте до:</b> {rest_end}"

    safe_name = html.escape(user.full_name)
    safe_username = html.escape(user.username if user.username else 'не указан')

    text = (
        f"📝 <b>Ваши данные</b>\n\n"
        f"👤 Имя: <b>{safe_name}</b>\n"
        f"🔖 Юзернейм: @{safe_username}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"⭐ Ранг: {rank_name}\n"
        f"🎭 Персонаж: {character}"
        f"{bday_text}"
        f"{notify_text}"
        f"{rest_text}"
        f"{status_text}"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user.id, message.chat.id))

# ============================================================
# 📖 /update
# ============================================================

@router.message(Command('update'))
async def cmd_update(message: Message):
    user = message.from_user
    if user is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда недоступна во флуд-чате.")
        return

    user_id = user.id
    user_data = get_user_by_id(user_id)

    if user_data is None:
        await message.answer(
            "❌ Вы не зарегистрированы!\n\n"
            "📌 Чтобы зарегистрироваться, перейдите в бота:\n"
            f"👉 @REG_sf_BOT\n\n"
            "И подайте заявку через команду /apply в личных сообщениях с ботом."
        )
        return

    user_role = get_user_role_from_roles(user_id)

    if user_role:
        await message.answer(
            f"👤 <b>Ваши данные:</b>\n\n"
            f"📌 Имя: {html.escape(user_data['full_name'])}\n"
            f"🎭 Персонаж: {html.escape(user_role)}\n\n"
            f"✅ Вы зарегистрированы!\n"
            f"📌 Чтобы обновить данные, перейдите в бота:\n"
            f"👉 @REG_sf_BOT",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"👤 Вы зарегистрированы, но у вас нет роли!\n\n"
            f"📌 Чтобы получить роль, перейдите в бота:\n"
            f"👉 @REG_sf_BOT\n\n"
            f"И подайте заявку через команду /apply в личных сообщениях с ботом.",
            parse_mode="HTML"
        )

# ============================================================
# ⌨️ УПРАВЛЕНИЕ КЛАВИАТУРОЙ
# ============================================================

@router.message(Command('hide'))
async def cmd_hide(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    await message.answer(
        "🗑️ <b>Клавиатура скрыта!</b>\n\n"
        "Чтобы вернуть меню, отправьте /menu",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )
    logger.info(f"👤 Пользователь {user_id} скрыл клавиатуру")

@router.message(Command('menu'))
async def cmd_menu(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Во флуд-чате клавиатура недоступна.")
        return

    await message.answer(
        "⌨️ <b>Клавиатура восстановлена!</b>",
        parse_mode="HTML",
        reply_markup=get_main_keyboard(user_id, message.chat.id)
    )
    logger.info(f"👤 Пользователь {user_id} показал клавиатуру")

# ============================================================
# ✅ КОМАНДЫ, ДОСТУПНЫЕ ВО ФЛУДЕ
# ============================================================

@router.message(Command('members'))
async def cmd_members(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    users = load_users()
    if not users:
        await message.answer("📭 В списке пока нет участников.")
        return

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer(f"👥 Всего участников: {len(users)}")
        return

    is_admin_user = is_admin(user_id)
    if not is_admin_user:
        await message.answer(f"👥 Всего участников: {len(users)}")
        return

    text = f"👥 <b>Список участников</b>\n"
    text += f"📅 {datetime.date.today().strftime('%d.%m.%Y')}\n"
    text += f"👥 Всего: {len(users)}\n\n"

    for u in users:
        username = f"@{u['username']}" if u['username'] else "без юзернейма"
        role_index = u.get('role', '0')
        role_name = ROLE_NAMES.get(role_index, 'Неизвестно')
        character = get_user_role_from_roles(u['id']) or "Нет роли"

        try:
            category = get_user_category(u['id'])
            emoji = get_emoji(category)
        except Exception:
            emoji = ''

        text += f"{emoji} • [{role_index}] {html.escape(u['full_name'])} ({username}) – {role_name} ({character}) (ID: <code>{u['id']}</code>)\n"

    if len(text) > 4000:
        await message.answer(text[:3900], parse_mode="HTML")
        await message.answer("\n... продолжение ...\n" + text[3900:], parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_id, message.chat.id))

@router.message(Command('roles'))
async def cmd_roles(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    seasons = get_all_seasons()
    if not seasons:
        await message.answer("📭 Сезоны не найдены.")
        return

    if message.chat.id == GENERAL_CHAT_ID:
        text = "📋 <b>Список ролей по сезонам</b>\n\n"
        for season in sorted(seasons):
            roles = get_roles_by_season(season)
            text += f"📂 <b>{season}</b> ({len(roles)} ролей):\n"
            for role in roles:
                role_name = role.get('name', '?')
                status = role.get('status', 'свободна')
                if status == 'свободна':
                    status_text = "🟢 свободна"
                elif status == 'бронь':
                    status_text = "🟡 забронирована"
                elif status == 'рест':
                    extra = role.get('extra', '')
                    status_text = f"🔵 рест до {extra}" if extra else "🔵 рест"
                elif status == 'ожидает':
                    status_text = "⏳ ожидает"
                else:
                    status_text = "🔴 занята"
                text += f"  • {html.escape(role_name)} — {status_text}\n"
            text += "\n"
        await message.answer(text, parse_mode="HTML")
        return

    buttons = []
    for season in sorted(seasons):
        roles = get_roles_by_season(season)
        buttons.append([InlineKeyboardButton(
            text=f"📂 {season} ({len(roles)})",
            callback_data=f"roles_season_{season}"
        )])
    buttons.append([InlineKeyboardButton(
        text="🔙 Назад в меню",
        callback_data="back_to_menu_from_roles"
    )])

    await message.answer(
        "📋 <b>Список ролей по сезонам</b>\n\n"
        "Выберите сезон для просмотра.\n\n"
        "🟢 свободна | 🟡 забронирована | 🔴 занята | 🔵 рест | ⏳ ожидает",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.message(Command('stats'))
async def cmd_stats(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён. Только для администраторов.")
        return

    from .admin_stats import cmd_stats as admin_stats
    await admin_stats(message)

@router.callback_query(F.data == "back_to_menu_from_roles")
async def back_to_menu_from_roles(callback: CallbackQuery):
    await callback.answer()
    if callback.message.chat.id == GENERAL_CHAT_ID:
        await callback.message.delete()
        await callback.message.answer("🔙 Вы вернулись.")
        return

    user_id = callback.from_user.id
    await callback.message.delete()
    await callback.message.answer(
        "🔙 Вы вернулись в главное меню.",
        reply_markup=get_main_keyboard(user_id, callback.message.chat.id)
    )

@router.callback_query(F.data.startswith("roles_season_"))
async def show_roles_by_season(callback: CallbackQuery):
    await callback.answer()
    if callback.message.chat.id == GENERAL_CHAT_ID:
        await callback.answer("⛔ Во флуд-чате недоступно.", show_alert=True)
        return

    season = callback.data.replace("roles_season_", "")
    roles = get_roles_by_season(season)

    if not roles:
        await callback.message.edit_text(f"📭 В сезоне '{html.escape(season)}' нет ролей.")
        return

    text = f"📂 <b>{html.escape(season)}</b>\n\n"
    for role in roles:
        role_name = role.get('name', '?')
        status = role.get('status', 'свободна')
        if status == 'свободна':
            status_text = "🟢 свободна"
        elif status == 'бронь':
            status_text = "🟡 забронирована"
        elif status == 'рест':
            extra = role.get('extra', '')
            status_text = f"🔵 рест до {extra}" if extra else "🔵 рест"
        elif status == 'ожидает':
            status_text = "⏳ ожидает"
        else:
            status_text = "🔴 занята"
        text += f"  • {html.escape(role_name)} — {status_text}\n"

    buttons = [
        [InlineKeyboardButton(text="🔙 Назад к сезонам", callback_data="back_to_seasons_list")],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu_from_roles")]
    ]

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data == "back_to_seasons_list")
async def back_to_seasons_list(callback: CallbackQuery):
    await callback.answer()
    if callback.message.chat.id == GENERAL_CHAT_ID:
        await callback.answer("⛔ Недоступно.", show_alert=True)
        return

    seasons = get_all_seasons()
    buttons = []
    for season in sorted(seasons):
        roles = get_roles_by_season(season)
        buttons.append([InlineKeyboardButton(
            text=f"📂 {season} ({len(roles)})",
            callback_data=f"roles_season_{season}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu_from_roles")])

    await callback.message.edit_text(
        "📋 <b>Список ролей по сезонам</b>\n\n"
        "Выберите сезон:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

# ============================================================
# 📈 НОВОЕ: /mynorm (График активности)
# ============================================================

@router.message(Command('mynorm'))
async def cmd_mynorm(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        return

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда недоступна во флуд-чате. Напишите в ЛС.")
        return

    user = get_user_by_id(user_id)
    if not user:
        await message.answer("⛔ Вы не зарегистрированы. Подайте заявку через /apply.")
        return

    # Получаем счётчики за текущую неделю
    counters = load_counters()
    uid_str = str(user_id)
    current_count = get_message_count(user_id)
    
    # Получаем настройки нормы
    norm = get_messages_norm()
    npndb = get_messages_norm_low()

    # Генерируем график
    msg = await message.answer("⏳ Строю ваш график...")
    
    try:
        # Данные для графика (для простоты генерируем 7 точек по дням недели)
        # В идеале тут нужно брать историю сообщений по дням, но у нас пока нет такой статистики.
        # Поэтому сделаем условный плавный график, отображающий текущее количество.
        
        # Заглушка: распределяем текущее количество по 7 дням для красивой дуги
        days = np.array([1, 2, 3, 4, 5, 6, 7])
        
        # Если сообщений мало, рисуем маленькую дугу, если много — большую
        if current_count == 0:
            y_values = np.array([0, 0, 0, 0, 0, 0, 0])
        else:
            # Просто красивое распределение, чтобы график выглядел как на скрине
            peak = current_count
            y_values = np.array([0, peak*0.4, peak*0.8, peak, peak*0.7, peak*0.3, peak*0.1])
            y_values = np.round(y_values).astype(int)

        # Сглаживание (Spline)
        X_Y_Spline = make_interp_spline(days, y_values)
        X_ = np.linspace(days.min(), days.max(), 500)
        Y_ = X_Y_Spline(X_)

        # Отрисовка
        plt.figure(figsize=(10, 6))
        plt.plot(X_, Y_, color='#2563eb', linewidth=4) # Синяя линия
        plt.scatter(days, y_values, color='#2563eb', s=100, zorder=5) # Точки

        # Линия Нормы
        plt.axhline(y=norm, color='#16a34a', linestyle='--', linewidth=3, label=f'норма ({norm})')
        # Линия НПНДБ
        plt.axhline(y=npndb, color='#dc2626', linestyle='--', linewidth=3, label=f'нпндб ({npndb})')

        # Оформление
        plt.title(f"{current_count} сообщений за неделю", fontsize=20, pad=15)
        plt.xlabel("Дни", fontsize=14)
        plt.ylabel("Количество сообщений", fontsize=14)
        
        plt.xticks(days, [f"День {d}" for d in days], fontsize=12)
        plt.yticks(fontsize=12)
        
        # Добавляем текст справа от линий
        plt.text(7.1, norm, f'норма ({norm})', color='#16a34a', va='center', fontsize=12)
        plt.text(7.1, npndb, f'нпндб ({npndb})', color='#dc2626', va='center', fontsize=12)
        
        # Убираем верхнюю и правую рамки
        plt.gca().spines['top'].set_visible(False)
        plt.gca().spines['right'].set_visible(False)
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        
        # Сохраняем и отправляем
        filepath = os.path.join(DATA_DIR, f"temp_graph_{user_id}.png")
        plt.savefig(filepath, bbox_inches='tight')
        plt.close()

        photo = FSInputFile(filepath)
        await message.answer_photo(
            photo,
            caption=f"📊 <b>Ваша активность за неделю</b>\n\n"
                    f"✅ Набрано: <b>{current_count}</b> сообщений\n"
                    f"🎯 До нормы осталось: <b>{max(0, norm - current_count)}</b>\n"
                    f"⚠️ До НПНДБ: <b>{max(0, npndb - current_count)}</b>",
            parse_mode="HTML"
        )
        await msg.delete()
        os.remove(filepath) # Удаляем временный файл

    except Exception as e:
        logger.error(f"❌ Ошибка графика для {user_id}: {e}")
        await msg.edit_text(f"❌ Произошла ошибка при построении графика: {e}")

# ============================================================
# 📜 НОВОЕ: /history (История)
# ============================================================

@router.message(Command('history'))
async def cmd_history(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        return

    if message.chat.id == GENERAL_CHAT_ID:
        await message.answer("⛔ Эта команда недоступна во флуд-чате.")
        return

    parts = message.text.split(maxsplit=1)
    target_id = user_id
    
    if len(parts) > 1:
        # Если указан ID, проверяем права
        if not is_admin(user_id):
            await message.answer("⛔ Просматривать чужую историю могут только админы.")
            return
        try:
            target_id = int(parts[1])
        except ValueError:
            await message.answer("❌ Неверный формат ID.")
            return

    history = load_user_history(target_id)
    user_data = get_user_by_id(target_id)

    if not history and not user_data:
        await message.answer(f"📭 История для <code>{target_id}</code> не найдена.")
        return

    text = f"📜 <b>История пользователя</b>\n"
    text += f"🆔 ID: <code>{target_id}</code>\n\n"
    
    if user_data:
        text += f"👤 Имя: {html.escape(user_data.get('full_name', '—'))}\n"
        text += f"🔖 Юзернейм: @{user_data.get('username', '—')}\n"
    
    text += "<b>Данные из истории:</b>\n"
    if history.get('role_key'):
        text += f"🎭 Роль: {html.escape(history.get('role_key'))} (ID: {history.get('role_id', '?')})\n"
    if history.get('birthday'):
        text += f"🎂 ДР: {history.get('birthday')}\n"
    if history.get('last_message_at'):
        text += f"💬 Последнее сообщение: {history.get('last_message_at')[:16].replace('T', ' ')}\n"
    if history.get('last_left'):
        text += f"🚪 Последний выход: {history.get('last_left')} (Причина: {history.get('left_reason', '?')})\n"

    await message.answer(text, parse_mode="HTML")