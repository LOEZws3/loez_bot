import html
import datetime
import json
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

from config import GENERAL_CHAT_ID, OWNER_ID, DATA_DIR, LEFTOVER_FILE
from utils.admin_utils import is_admin, load_admins
from utils.user_utils import load_users
from utils.norm_utils import get_user_category, get_emoji, get_category_label
from utils.counters import load_counters
import logging

logger = logging.getLogger(__name__)
router = Router()

def _load_leftdata() -> dict:
    if not os.path.exists(LEFTOVER_FILE):
        return {}
    try:
        with open(LEFTOVER_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, IOError):
        return {}

def _parse_iso(s: str):
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None

def _count_users_joined_in_period(days: int) -> int:
    data = load_counters()
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    count = 0
    for uid_str, info in data.items():
        if not isinstance(info, dict):
            continue
        joined = _parse_iso(info.get('joined_at', ''))
        if joined and joined >= cutoff:
            count += 1
    return count

def _count_active_in_period(days: int) -> int:
    data = load_counters()
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    count = 0
    for uid_str, info in data.items():
        if not isinstance(info, dict):
            continue
        last = _parse_iso(info.get('last_message_at', ''))
        if last and last >= cutoff:
            count += 1
    return count

def _count_left_in_period(days: int) -> int:
    data = _load_leftdata()
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    count = 0
    for uid_str, info in data.items():
        if not isinstance(info, dict):
            continue
        left_at = _parse_iso(info.get('left_at', ''))
        if left_at and left_at >= cutoff:
            count += 1
    return count

def _get_categories_stats() -> dict:
    from utils.norm_utils import (
        CATEGORY_GOOD, CATEGORY_WARN, CATEGORY_BAN,
        CATEGORY_NEW, CATEGORY_REST,
    )
    result = {'good': 0, 'warn': 0, 'ban': 0, 'rest': 0, 'new': 0}
    users = load_users()
    for u in users:
        uid = u.get('id')
        if not uid:
            continue
        try:
            cat = get_user_category(uid)
            if cat == CATEGORY_GOOD:
                result['good'] += 1
            elif cat == CATEGORY_WARN:
                result['warn'] += 1
            elif cat == CATEGORY_BAN:
                result['ban'] += 1
            elif cat == CATEGORY_REST:
                result['rest'] += 1
            elif cat == CATEGORY_NEW:
                result['new'] += 1
        except Exception:
            continue
    return result

def _build_stats_base_text() -> str:
    from utils.role_utils import get_all_seasons, get_roles_by_season

    seasons = get_all_seasons()
    roles_stats = {"свободна": 0, "занята": 0, "ожидает": 0, "рест": 0, "бронь": 0}
    total_roles = 0
    for season in seasons:
        roles = get_roles_by_season(season)
        for role in roles:
            status = role.get('status', 'свободна')
            if status in roles_stats:
                roles_stats[status] += 1
            total_roles += 1

    users = load_users()
    total_users = len(users)

    admins = load_admins()
    total_admins = len(admins)

    text = (
        f"📊 <b>Статистика (база)</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎭 <b>РОЛИ:</b>\n"
        f"  Всего: {total_roles}\n"
        f"  🟢 Свободна: {roles_stats['свободна']}\n"
        f"  🔴 Занята: {roles_stats['занята']}\n"
        f"  ⏳ Ожидает: {roles_stats['ожидает']}\n"
        f"  🔵 Рест: {roles_stats['рест']}\n"
        f"  🟡 Бронь: {roles_stats['бронь']}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>УЧАСТНИКИ:</b>\n"
        f"  Всего: {total_users}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 <b>АДМИНЫ:</b> {total_admins}\n"
    )
    return text

def _build_stats_period_text(period: str) -> str:
    days_map = {'day': 1, 'week': 7, 'month': 30}
    titles = {'day': 'за день', 'week': 'за неделю', 'month': 'за месяц'}
    days = days_map.get(period, 7)
    title = titles.get(period, period)

    cats = _get_categories_stats()
    joined = _count_users_joined_in_period(days)
    active = _count_active_in_period(days)
    left = _count_left_in_period(days)
    total_users = len(load_users())

    text = (
        f"📊 <b>Статистика {title}</b>\n\n"
        f"👥 Всего зарегистрировано: {total_users}\n"
        f"👶 Нью (пришло за период): {joined}\n\n"
        f"✅ Хороших: {cats['good']}\n"
        f"⚠️ Варн: {cats['warn']}\n"
        f"🚫 Бан: {cats['ban']}\n"
        f"⏳ В ресте: {cats['rest']}\n"
        f"👶 Всего Нью: {cats['new']}\n\n"
        f"📈 Активных за период: {active}\n"
        f"📉 Ушло (кикнуто): {left}\n"
    )
    return text

def _build_stats_keyboard(current_period: str = 'base') -> InlineKeyboardMarkup:
    def mark(p):
        return "✅ " if current_period == p else ""

    return InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏆 Топ недели", callback_data="stats_top_week")],
        [
            InlineKeyboardButton(text=f"{mark('base')}📊 База", callback_data="stats_period_base"),
            InlineKeyboardButton(text=f"{mark('day')}📅 День", callback_data="stats_period_day"),
        ],
        [
            InlineKeyboardButton(text=f"{mark('week')}📆 Неделя", callback_data="stats_period_week"),
            InlineKeyboardButton(text=f"{mark('month')}📈 Месяц", callback_data="stats_period_month"),
        ],
        [InlineKeyboardButton(text="📈 График активности (365 дней)", callback_data="stats_graph_365")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"stats_period_{current_period}")],
    ])

@router.message(Command('stats'))
async def cmd_stats(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён. Только для администраторов.")
        return

    if message.chat.id == GENERAL_CHAT_ID:
        from utils.role_utils import get_all_seasons, get_roles_by_season
        seasons = get_all_seasons()
        total_roles = 0
        for season in seasons:
            total_roles += len(get_roles_by_season(season))
        total_users = len(load_users())
        text = (
            f"📊 <b>Статистика</b>\n\n"
            f"🎭 Роли: {total_roles}\n"
            f"👥 Участников: {total_users}"
        )
        await message.answer(text, parse_mode="HTML")
        return

    text = _build_stats_base_text()
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=_build_stats_keyboard('base')
    )

@router.callback_query(F.data.startswith("stats_period_"))
async def stats_period_callback(callback: CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass

    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    if callback.message.chat.id == GENERAL_CHAT_ID:
        await callback.answer("⛔ В ЛС, пожалуйста.", show_alert=True)
        return

    period = callback.data.replace("stats_period_", "")

    if period == 'base':
        text = _build_stats_base_text()
    else:
        text = _build_stats_period_text(period)

    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=_build_stats_keyboard(period)
        )
    except Exception:
        pass

@router.callback_query(F.data == "stats_graph_365")
async def stats_graph_365_callback(callback: CallbackQuery):
    try:
        await callback.answer("⏳ Строю график...")
    except Exception:
        pass

    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    if callback.message.chat.id == GENERAL_CHAT_ID:
        await callback.answer("⛔ В ЛС, пожалуйста.", show_alert=True)
        return

    try:
        from utils.counters import get_norm_history
        history = get_norm_history()

        if not history:
            await callback.message.answer("📭 Пока нет данных для графика. Подождите, пока пройдёт первая неделя.")
            return

        weeks = sorted(history.keys())
        y_values = []
        labels = []
        for week in weeks:
            total_msgs = sum(history[week].values())
            y_values.append(total_msgs)
            dt = datetime.datetime.strptime(week, "%Y-%m-%d")
            labels.append(dt.strftime("%d.%m"))

        days_x = np.arange(len(weeks))

        plt.figure(figsize=(12, 6))
        plt.bar(days_x, y_values, color='#84cc16', width=0.6)
        plt.title("Общее количество сообщений за неделю (365 дней)", fontsize=16, pad=15)
        plt.ylabel("Сообщений", fontsize=12)

        if len(labels) > 12:
            step = len(labels) // 12
            plt.xticks(days_x[::step], labels[::step], fontsize=10, rotation=45)
        else:
            plt.xticks(days_x, labels, fontsize=10, rotation=45)

        plt.grid(axis='y', linestyle='--', alpha=0.5)
        plt.gca().spines['top'].set_visible(False)
        plt.gca().spines['right'].set_visible(False)

        filepath = os.path.join(DATA_DIR, f"temp_stats_graph.png")
        plt.savefig(filepath, bbox_inches='tight')
        plt.close()

        photo = FSInputFile(filepath)
        await callback.message.answer_photo(
            photo,
            caption="📈 <b>Активность за неделю (сумма сообщений)</b>\n\n"
                    f"<i>(На основе сохранённой истории норм)</i>",
            parse_mode="HTML"
        )
        os.remove(filepath)

    except Exception as e:
        logger.error(f"❌ Ошибка генерации графика: {e}")
        await callback.message.answer(f"❌ Ошибка: {e}")
@router.callback_query(F.data == "stats_top_week")
async def stats_top_week_callback(callback: CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass

    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    from utils.counters import get_all_counts
    from utils.user_utils import get_user_by_id

    counts = get_all_counts()
    # Сортируем по убыванию и берём топ-5
    sorted_users = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]

    if not sorted_users:
        await callback.message.answer("📭 Пока нет данных.")
        return

    text = "🏆 <b>Топ-5 активных юзеров за неделю</b>\n\n"
    for i, (uid_str, count) in enumerate(sorted_users, 1):
        uid = int(uid_str)
        user_data = get_user_by_id(uid)
        name = user_data.get('full_name', f'ID {uid}') if user_data else f'ID {uid}'
        text += f"{i}. {html.escape(name)} — <b>{count}</b> соо\n"

    await callback.message.answer(text, parse_mode="HTML")