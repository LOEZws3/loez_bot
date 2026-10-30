import os
import sys
import logging
import platform
import datetime
import json
import asyncio
import time
import psutil
import html
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
from config import (
    BOT_TOKEN, GENERAL_CHAT_ID, ADMIN_GROUP_ID, DATA_DIR,
    ROLES_STATUS_FILE, SYSTEM_SETTINGS_FILE,
    CHAT_INVITE_LINK, ADMIN_LINK, MODERATOR_LINK
)
from utils.admin_utils import is_owner
from utils import status as bot_status
from utils import stats_tracker
from utils.backup_utils import create_backup

logger = logging.getLogger(__name__)
router = Router()

START_TIME = datetime.datetime.now()
LAST_RUN_FILE = os.path.join(DATA_DIR, 'system', 'last_run.json')
RESTART_FLAG_FILE = os.path.join(DATA_DIR, 'system', 'restart_notify.json')

class StatsStates(StatesGroup):
    waiting_for_days = State()

async def _safe_answer(callback: CallbackQuery, text: str = None, show_alert: bool = False):
    try:
        await callback.answer(text=text, show_alert=show_alert)
    except TelegramBadRequest as e:
        if "query is too old" not in str(e):
            logger.warning(f"Ошибка callback.answer: {e}")
    except Exception as e:
        logger.warning(f"Неизвестная ошибка callback.answer: {e}")

def _get_downtime_str() -> str:
    if not os.path.exists(LAST_RUN_FILE):
        return "нет данных"
    try:
        with open(LAST_RUN_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            last_time = datetime.datetime.fromisoformat(data['last_run'])
            delta = START_TIME - last_time
            if delta.total_seconds() < 0:
                return "только что"
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours > 24:
                days = hours // 24
                return f"{days} д. {hours % 24} ч."
            return f"{hours} ч. {minutes} мин."
    except Exception:
        return "ошибка"

def _update_last_run():
    try:
        os.makedirs(os.path.dirname(LAST_RUN_FILE), exist_ok=True)
        with open(LAST_RUN_FILE, 'w', encoding='utf-8') as f:
            json.dump({'last_run': datetime.datetime.now().isoformat()}, f)
    except Exception as e:
        logger.error(f"Ошибка обновления last_run.json: {e}")

def _get_uptime_str() -> str:
    delta = datetime.datetime.now() - START_TIME
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    days = hours // 24
    if days > 0:
        return f"{days} д. {hours % 24} ч. {minutes} мин."
    return f"{hours} ч. {minutes} мин."

def _get_last_error() -> str:
    path = os.path.join(DATA_DIR, 'logs', 'errors.txt')
    if not os.path.exists(path):
        return "Файл errors.txt не найден"
    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if not lines:
                return "Ошибок нет"
            for line in reversed(lines):
                if "Ошибка" in line or "Error" in line:
                    return line.strip()[:80] + "..."
            return lines[-1].strip()[:80] + "..."
    except Exception as e:
        return f"Ошибка чтения: {e}"

def _check_tasks() -> str:
    expected_tasks = [
        "check_rests_loop", "sync_roles_loop", "expire_warns_loop", 
        "norm_reminder_loop", "norm_reset_loop", "check_kicked_loop",
        "birthday_personal_loop", "birthday_group_loop", "network_monitor_loop",
        "stats_collector_loop", "auto_backup_loop"
    ]
    running = []
    for task in asyncio.all_tasks():
        if task.get_name() in expected_tasks:
            running.append(task.get_name())
            
    if len(running) == len(expected_tasks):
        return f"✅ Все живы ({len(running)}/{len(expected_tasks)})"
    else:
        missing = set(expected_tasks) - set(running)
        return f"⚠️ Упали: {', '.join(missing)}"

def _check_integrity(users: list, roles: dict) -> str:
    issues = []
    for r_name, r_info in roles.items():
        if isinstance(r_info, dict):
            owner_id = r_info.get('owner_id')
            if owner_id and not any(u['id'] == owner_id for u in users):
                issues.append(f"Юзер {owner_id} держит '{r_name}', но удалён из базы.")
    if not issues:
        return "✅ Связи в порядке"
    return "⚠️ " + " | ".join(issues[:3]) + (" (и др.)" if len(issues) > 3 else "")

def _get_system_load() -> str:
    try:
        process = psutil.Process(os.getpid())
        mem = process.memory_info().rss / 1024 / 1024
        cpu = process.cpu_percent(interval=None)
        return f"RAM: {mem:.1f} MB | CPU: {cpu}%"
    except Exception:
        return "psutil не установлен"

def _build_stats_graph(days: int) -> str:
    data = stats_tracker.get_stats(days)
    dates = [d[0][5:] for d in data]
    uptimes = [d[1].get("uptime", 0) / 3600 for d in data]
    downtimes = [d[1].get("downtime", 0) / 3600 for d in data]
    bugtimes = [d[1].get("bugtime", 0) / 3600 for d in data]
    
    plt.figure(figsize=(10, 5))
    x = np.arange(len(dates))
    normal_uptime = [max(0, u - b) for u, b in zip(uptimes, bugtimes)]
    
    plt.bar(x, normal_uptime, color='#16a34a', label='Uptime (OK)')
    plt.bar(x, bugtimes, bottom=normal_uptime, color='#eab308', label='Bugtime (сеть)')
    plt.bar(x, downtimes, color='#dc2626', label='Downtime (off)')
    
    plt.xticks(x, dates, rotation=45, ha='right')
    plt.ylabel('Часы')
    plt.title(f'Статистика за {days} дн.')
    plt.legend()
    plt.tight_layout()
    
    filepath = os.path.join(DATA_DIR, f"temp_stats_{days}.png")
    plt.savefig(filepath)
    plt.close()
    return filepath

def _build_diag_report(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    now_str = datetime.datetime.now().strftime("%H:%M:%S")
    
    report = f"📋 <b>Диагностика системы</b>\n"
    report += f"🕒 <i>Обновлено: {now_str}</i>\n\n"
    
    report += f"💻 ОС: <code>{platform.system()} {platform.release()}</code> | 🐍 Python: <code>{platform.python_version()}</code>\n"
    report += f"⏱️ Uptime: <b>{_get_uptime_str()}</b> | ⏸️ Downtime: <b>{_get_downtime_str()}</b>\n"
    report += f"🐛 Bugtime: <b>{bot_status.get_bugtime_str()}</b>\n"
    report += f"⚙️ Нагрузка: {_get_system_load()}\n\n"

    from utils.user_utils import load_users
    from utils.role_utils import load_roles_status
    from utils.requests_utils import get_pending_count
    
    users = load_users()
    roles = load_roles_status()
    pending = get_pending_count()
    taken_roles = sum(1 for r in roles.values() if isinstance(r, dict) and r.get('status') == 'занята')
    
    report += f"👥 <b>Данные:</b> Юзеров: {len(users)} | Занято ролей: {taken_roles} | Заявок: {pending}\n"
    report += f"🔗 <b>Целостность:</b> {_check_integrity(users, roles)}\n\n"
    report += f"⚙️ <b>Фоновые циклы:</b> {_check_tasks()}\n"
    report += f"🔥 <b>Последняя ошибка:</b> <code>{_get_last_error()}</code>\n\n"

    try:
        from config import USE_PROXY
        from proxy_manager import proxy_manager
        if USE_PROXY:
            current = proxy_manager.get_current_proxy()
            pings = proxy_manager.get_proxy_pings()
            ping_val = pings.get(current, 0) if current else 0
            bad_count = len(proxy_manager.bad_proxies_until)
            report += f"🌐 <b>Прокси:</b> {current or 'не выбран'} ({ping_val:.3f}с) | В блэклисте: {bad_count}\n"
        else:
            report += f"🌐 <b>Прокси:</b> ❌ Отключён (работает каскад)\n"
    except Exception as e:
        report += f"🌐 <b>Прокси:</b> ⚠️ Ошибка: {e}\n"

    from utils.counters import _counters_cache
    cache_size = len(_counters_cache) if _counters_cache else 0
    report += f"🧠 <b>Кэш счётчиков:</b> {cache_size} записей\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Подробнее о Downtime", callback_data="diag_stats_menu")],
        [InlineKeyboardButton(text="🔄 Перезапустить бота", callback_data="diag_restart")],
        [InlineKeyboardButton(text="🛑 Экстренное отключение", callback_data="diag_shutdown")],
        [InlineKeyboardButton(text="💾 Сохранить всё в JSON", callback_data="diag_save_all")],
        [InlineKeyboardButton(text="📦 Сделать БЭКАП (ZIP)", callback_data="diag_backup")],
        [InlineKeyboardButton(text="🧹 Очистить кэш", callback_data="diag_clear_cache")],
        [InlineKeyboardButton(text="🛠️ Починить связи", callback_data="diag_fix_integrity")],
        [InlineKeyboardButton(text="🔄 Обновить отчёт", callback_data="diag_refresh")]
    ])
    return report, keyboard

@router.message(Command('diag'))
async def cmd_diag(message: Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ Доступ запрещён. Только для владельца.")
        return

    text, keyboard = _build_diag_report(message.from_user.id)
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

# ======================== НОВЫЕ КОМАНДЫ ========================

@router.message(Command('ping'))
async def cmd_ping(message: Message):
    if not is_owner(message.from_user.id):
        return
    start = time.time()
    msg = await message.answer("⏳ Пингую Telegram...")
    end = time.time()
    latency = int((end - start) * 1000)
    await msg.edit_text(f"🏓 <b>Pong!</b>\nЗадержка API: <b>{latency} мс</b>", parse_mode="HTML")

@router.message(Command('logs'))
async def cmd_logs(message: Message):
    if not is_owner(message.from_user.id):
        return
    path = os.path.join(DATA_DIR, 'logs', 'errors.txt')
    if not os.path.exists(path):
        await message.answer("📭 Файл ошибок пуст или не найден.")
        return
    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        last_lines = lines[-50:]
        if not last_lines:
            await message.answer("📭 Ошибок нет.")
            return
        text = "🔥 <b>Последние 50 строк ошибок:</b>\n\n<pre>"
        text += "".join(last_lines)
        text += "</pre>"
        if len(text) > 4096:
            await message.answer("⚠️ Слишком много текста. Отправляю файлом.")
            await message.answer_document(FSInputFile(path))
        else:
            await message.answer(text, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка чтения логов: {e}")

@router.message(Command('warns'))
async def cmd_warns(message: Message):
    if not is_owner(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Используй: /warns [ID]")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID.")
        return
        
    from utils.warns_utils import load_warns
    warns = load_warns()
    user_warns = warns.get(str(target_id), [])
    
    if not user_warns:
        await message.answer(f"✅ У юзера <code>{target_id}</code> нет активных варнов.", parse_mode="HTML")
        return
        
    text = f"⚠️ <b>Варны юзера <code>{target_id}</code>:</b>\n\n"
    for w in user_warns:
        text += f"• ID: {w.get('id')} | До: {w.get('expire_at')[:16]}\n"
        text += f"  Выдал: {w.get('issued_by')} | Причина: {html.escape(w.get('reason', 'Не указана'))}\n\n"
        
    await message.answer(text, parse_mode="HTML")

# ======================== ОБРАБОТЧИКИ КНОПОК ========================

@router.callback_query(F.data == "diag_clear_cache")
async def diag_clear_cache(callback: CallbackQuery):
    await _safe_answer(callback, "🧹 Очищаю кэш...")
    if not is_owner(callback.from_user.id):
        return
    try:
        from utils.counters import clear_counters_cache
        from utils.parsers import clear_cache
        clear_counters_cache()
        clear_cache()
        text, keyboard = _build_diag_report(callback.from_user.id)
        text += "\n\n✅ <b>Кэш успешно сброшен!</b>"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception as e:
        await _safe_answer(callback, f"❌ Ошибка: {e}", show_alert=True)

@router.callback_query(F.data == "diag_backup")
async def diag_backup(callback: CallbackQuery):
    await _safe_answer(callback, "📦 Создаю бэкап...")
    if not is_owner(callback.from_user.id):
        return
    try:
        filepath = create_backup()
        text, keyboard = _build_diag_report(callback.from_user.id)
        text += f"\n\n✅ <b>Бэкап создан!</b>\n📁 <code>{os.path.basename(filepath)}</code>"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception as e:
        await _safe_answer(callback, f"❌ Ошибка бэкапа: {e}", show_alert=True)

@router.callback_query(F.data == "diag_refresh")
async def diag_refresh(callback: CallbackQuery):
    await _safe_answer(callback, "🔄 Обновляю...")
    if not is_owner(callback.from_user.id):
        return
    text, keyboard = _build_diag_report(callback.from_user.id)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        pass

@router.callback_query(F.data == "diag_save_all")
async def diag_save_all(callback: CallbackQuery):
    await _safe_answer(callback, "💾 Сохраняю...")
    if not is_owner(callback.from_user.id):
        return
    try:
        from utils.user_utils import load_users, save_users
        from utils.role_utils import load_roles_status, save_roles_status
        from utils.counters import load_counters, save_counters
        from utils.admin_utils import load_admins, save_admins
        from utils.requests_utils import load_requests, save_requests
        
        save_users(load_users())
        save_roles_status(load_roles_status())
        save_counters(load_counters())
        save_admins(load_admins())
        save_requests(load_requests())
        
        text, keyboard = _build_diag_report(callback.from_user.id)
        text += "\n\n✅ <b>Все данные успешно сохранены на диск!</b>"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception as e:
        await _safe_answer(callback, f"❌ Ошибка: {e}", show_alert=True)

@router.callback_query(F.data == "diag_fix_integrity")
async def diag_fix_integrity(callback: CallbackQuery):
    await _safe_answer(callback, "🛠️ Исправляю...")
    if not is_owner(callback.from_user.id):
        return
    try:
        from utils.user_utils import load_users
        from utils.role_utils import load_roles_status, save_roles_status
        
        users = load_users()
        user_ids = {u['id'] for u in users}
        roles = load_roles_status()
        
        fixed = 0
        for r_name, r_info in roles.items():
            if isinstance(r_info, dict):
                owner_id = r_info.get('owner_id')
                if owner_id and owner_id not in user_ids:
                    r_info['status'] = 'свободна'
                    r_info['owner_id'] = None
                    r_info['username'] = None
                    fixed += 1
                    logger.info(f"🛠️ Освобождена роль '{r_name}' (юзер {owner_id} удалён)")
        
        if fixed > 0:
            save_roles_status(roles)
            
        text, keyboard = _build_diag_report(callback.from_user.id)
        if fixed > 0:
            text += f"\n\n✅ <b>Исправлено связей: {fixed}</b>"
        else:
            text += "\n\nℹ️ <b>Связи уже в порядке.</b>"
            
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception as e:
        await _safe_answer(callback, f"❌ Ошибка: {e}", show_alert=True)

@router.callback_query(F.data == "diag_restart")
async def diag_restart(callback: CallbackQuery):
    await _safe_answer(callback, "🔄 Перезапускаю...", show_alert=True)
    if not is_owner(callback.from_user.id):
        return
    actor = callback.from_user
    logger.warning(f"🔄⚠️ ADMIN {actor.id} (@{actor.username or 'no_username'}) INITIATED BOT RESTART!")
    
    _update_last_run()
    try:
        os.makedirs(os.path.dirname(RESTART_FLAG_FILE), exist_ok=True)
        with open(RESTART_FLAG_FILE, 'w', encoding='utf-8') as f:
            json.dump({'owner_id': actor.id}, f)
    except Exception as e:
        logger.error(f"Ошибка записи restart_notify.json: {e}")
    
    banner = (
        "╔══════════════════════════════════════╗\n"
        "║     🔄 REBOOT SYSTEM INITIATED       ║\n"
        "╚══════════════════════════════════════╝\n\n"
        "Бот ушел на перезагрузку. Планировщики и кэши будут подняты заново.\n"
        "Подожди пару секунд, броо! ⏳"
    )
    try:
        await callback.message.edit_text(f"<pre>{banner}</pre>", parse_mode="HTML")
    except Exception:
        pass
    await asyncio.sleep(1.5)
    os.execl(sys.executable, sys.executable, *sys.argv)

@router.callback_query(F.data == "diag_shutdown")
async def diag_shutdown(callback: CallbackQuery):
    await _safe_answer(callback, "🛑 Отключаю...", show_alert=True)
    if not is_owner(callback.from_user.id):
        return
    actor = callback.from_user
    logger.warning(f"🛑⚠️ ADMIN {actor.id} (@{actor.username or 'no_username'}) INITIATED BOT SHUTDOWN!")
    
    _update_last_run()
    banner = (
        "╔══════════════════════════════════════╗\n"
        "║     🛑 SYSTEM HALT / OFFLINE         ║\n"
        "╚══════════════════════════════════════╝\n\n"
        "Бот полностью остановлен. Процесс убит.\n"
        "Чтобы поднять его снова, тебе придется запустить start.bat вручную. 💤"
    )
    try:
        await callback.message.edit_text(f"<pre>{banner}</pre>", parse_mode="HTML")
    except Exception:
        pass
    await asyncio.sleep(1.5)
    os._exit(0)

# ======================== СТАТИСТИКА (ГРАФИКИ) ========================

@router.callback_query(F.data == "diag_stats_menu")
async def diag_stats_menu(callback: CallbackQuery):
    await _safe_answer(callback)
    if not is_owner(callback.from_user.id):
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 День (1)", callback_data="diag_stats_1")],
        [InlineKeyboardButton(text="📅 Неделя (7)", callback_data="diag_stats_7")],
        [InlineKeyboardButton(text="📅 Месяц (30)", callback_data="diag_stats_30")],
        [InlineKeyboardButton(text="📅 Год (365)", callback_data="diag_stats_365")],
        [InlineKeyboardButton(text="✏️ Свой период", callback_data="diag_stats_custom")],
        [InlineKeyboardButton(text="🔙 Назад в /diag", callback_data="diag_refresh")]
    ])
    text = (
        "📊 <b>Статистика за период</b>\n\n"
        "Выбери, за сколько дней построить график.\n"
        "На графике будет видно:\n"
        "🟢 Uptime (сколько бот работал)\n"
        "🟡 Bugtime (сетевые лаги)\n"
        "🔴 Downtime (сколько лежал)"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)

@router.callback_query(F.data.startswith("diag_stats_") & ~F.data.in_({"diag_stats_menu", "diag_stats_custom"}))
async def diag_stats_period(callback: CallbackQuery):
    await _safe_answer(callback, "📊 Строю график...")
    if not is_owner(callback.from_user.id):
        return
    days = int(callback.data.replace("diag_stats_", ""))
    try:
        filepath = _build_stats_graph(days)
        await callback.message.delete()
        photo = FSInputFile(filepath)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к выбору", callback_data="diag_stats_menu")]
        ])
        await callback.message.answer_photo(
            photo, 
            caption=f"📊 <b>Статистика за {days} дн.</b>\nЗелёный — Uptime, Жёлтый — Bugtime, Красный — Downtime.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        os.remove(filepath)
    except Exception as e:
        logger.error(f"Ошибка графика: {e}")
        await callback.message.answer(f"❌ Ошибка при построении графика: {e}")

@router.callback_query(F.data == "diag_stats_custom")
async def diag_stats_custom(callback: CallbackQuery, state: FSMContext):
    await _safe_answer(callback)
    if not is_owner(callback.from_user.id):
        return
    await callback.message.edit_text("✏️ Введи количество дней для графика (от 1 до 365):")
    await state.set_state(StatsStates.waiting_for_days)

@router.message(StatsStates.waiting_for_days)
async def process_stats_custom(message: Message, state: FSMContext):
    try:
        days = int(message.text.strip())
        if days < 1 or days > 365:
            raise ValueError
    except ValueError:
        await message.answer("❌ Неверное число. Введи от 1 до 365.")
        return
    await state.clear()
    msg = await message.answer("📊 Строю график...")
    try:
        filepath = _build_stats_graph(days)
        photo = FSInputFile(filepath)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к выбору", callback_data="diag_stats_menu")]
        ])
        await message.answer_photo(
            photo, 
            caption=f"📊 <b>Статистика за {days} дн.</b>\nЗелёный — Uptime, Жёлтый — Bugtime, Красный — Downtime.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        await msg.delete()
        os.remove(filepath)
    except Exception as e:
        logger.error(f"Ошибка графика: {e}")
        await msg.edit_text(f"❌ Ошибка при построении графика: {e}")

# ======================== /CHECK_CHATS ========================

@router.message(Command('check_chats'))
async def cmd_check_chats(message: Message):
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
        try:
            chat = await message.bot.get_chat(GENERAL_CHAT_ID)
            member = await message.bot.get_chat_member(GENERAL_CHAT_ID, message.bot.id)
            status = member.status
            status_emoji = {'creator': '👑', 'administrator': '🔐', 'member': '👤',
                            'restricted': '⛔', 'left': '❌', 'kicked': '🚫'}.get(status, '❓')
            result += f"{status_emoji} <b>Флуд-чат:</b>\n   • ID: <code>{GENERAL_CHAT_ID}</code>\n   • Название: {chat.title}\n   • Статус: <b>{status}</b>\n"
        except Exception as e:
            result += f"❌ <b>Флуд-чат:</b> Ошибка — {e}\n"
        try:
            chat = await message.bot.get_chat(ADMIN_GROUP_ID)
            member = await message.bot.get_chat_member(ADMIN_GROUP_ID, message.bot.id)
            status = member.status
            status_emoji = {'creator': '👑', 'administrator': '🔐', 'member': '👤',
                            'restricted': '⛔', 'left': '❌', 'kicked': '🚫'}.get(status, '❓')
            result += f"\n{status_emoji} <b>Админ-группа:</b>\n   • ID: <code>{ADMIN_GROUP_ID}</code>\n   • Название: {chat.title}\n   • Статус: <b>{status}</b>\n"
        except Exception as e:
            result += f"\n❌ <b>Админ-группа:</b> Ошибка — {e}\n"
        await message.answer(result, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка диагностики: {e}")