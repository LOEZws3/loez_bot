"""
Утилита для счётчиков сообщений.
Файл: data/system/message_counts.json
"""

import os
import datetime
import logging
from zoneinfo import ZoneInfo

from config import DATA_DIR
from utils.parsers import load_json, save_json

logger = logging.getLogger(__name__)

COUNTERS_FILE = os.path.join(DATA_DIR, 'system', 'message_counts.json')
NORM_HISTORY_FILE = os.path.join(DATA_DIR, 'system', 'norm_history.json')
DAILY_COUNTS_FILE = os.path.join(DATA_DIR, 'system', 'daily_counts.json') # 🆕 Новый файл для дней

# ⚠️ Часовой пояс МСК
MSK_TZ = ZoneInfo("Europe/Moscow")

_counters_cache = None

def _now_msk() -> datetime.datetime:
    return datetime.datetime.now(MSK_TZ)


def clear_counters_cache():
    global _counters_cache
    _counters_cache = None


def load_counters() -> dict:
    global _counters_cache
    if _counters_cache is not None:
        return _counters_cache

    data = load_json(COUNTERS_FILE, {})
    if not isinstance(data, dict):
        data = {}

    _counters_cache = data
    return _counters_cache


def save_counters(data: dict) -> bool:
    global _counters_cache
    _counters_cache = data
    return save_json(COUNTERS_FILE, data)


def _get_current_week_start() -> str:
    """
    Дата начала текущей недели (последняя суббота 21:00 МСК).
    """
    now = _now_msk()
    days_since_saturday = (now.weekday() - 5) % 7
    if days_since_saturday == 0 and now.hour < 21:
        days_since_saturday = 7
    saturday = now.date() - datetime.timedelta(days=days_since_saturday)
    return saturday.isoformat()


def increment_message_count(user_id: int) -> bool:
    data = load_counters()
    uid_str = str(user_id)
    current_week = _get_current_week_start()

    if uid_str not in data or not isinstance(data[uid_str], dict):
        data[uid_str] = {'count': 0, 'week_start': current_week, 'history': []}

    if data[uid_str].get('week_start') != current_week:
        old_joined = data[uid_str].get('joined_at', '')
        old_last_msg = data[uid_str].get('last_message_at', '')
        data[uid_str] = {'count': 0, 'week_start': current_week, 'history': []}
        if old_joined:
            data[uid_str]['joined_at'] = old_joined
        if old_last_msg:
            data[uid_str]['last_message_at'] = old_last_msg

    data[uid_str]['count'] = int(data[uid_str].get('count', 0)) + 1
    now_iso = _now_msk().isoformat()
    data[uid_str]['last_message_at'] = now_iso

    # Добавляем в историю и чистим старше 7 дней
    history = data[uid_str].setdefault('history', [])
    history.append(now_iso)

    week_ago = _now_msk() - datetime.timedelta(days=7)
    data[uid_str]['history'] = [
        ts for ts in history
        if datetime.datetime.fromisoformat(ts) >= week_ago
    ]

    return save_counters(data)

# 🆕 ФУНКЦИЯ ИНКРЕМЕНТА ДЛЯ ДНЕЙ
def increment_daily_count(user_id: int) -> bool:
    """Плюсует 1 сообщение к статистике текущего дня (по МСК)."""
    try:
        today = _now_msk().strftime("%Y-%m-%d")
        data = load_json(DAILY_COUNTS_FILE, {})
        
        if today not in data:
            data[today] = {}
            
        uid_str = str(user_id)
        data[today][uid_str] = int(data[today].get(uid_str, 0)) + 1
        
        return save_json(DAILY_COUNTS_FILE, data)
    except Exception as e:
        logger.error(f"Ошибка в increment_daily_count: {e}")
        return False

# 🆕 ФУНКЦИЯ ПОЛУЧЕНИЯ СТАТИСТИКИ ПО ДНЯМ
def get_daily_counts(user_id: int, days: int = 7) -> list:
    """Возвращает список статистики по дням за последние N дней."""
    data = load_json(DAILY_COUNTS_FILE, {})
    uid_str = str(user_id)
    
    result = []
    today = _now_msk()
    
    for i in range(days - 1, -1, -1):
        date_obj = today - datetime.timedelta(days=i)
        date_str = date_obj.strftime("%Y-%m-%d")
        display_date = date_obj.strftime("%d.%m")
        
        count = int(data.get(date_str, {}).get(uid_str, 0))
        result.append({"date": display_date, "count": count})
        
    return result


def get_message_count(user_id: int) -> int:
    data = load_counters()
    uid_str = str(user_id)
    if uid_str not in data or not isinstance(data[uid_str], dict):
        return 0
    current_week = _get_current_week_start()
    if data[uid_str].get('week_start') != current_week:
        return 0
    return int(data[uid_str].get('count', 0))


def get_all_counts() -> dict:
    data = load_counters()
    current_week = _get_current_week_start()
    result = {}
    for uid_str, info in data.items():
        if not isinstance(info, dict):
            continue
        if info.get('week_start') != current_week:
            continue
        result[uid_str] = int(info.get('count', 0))
    return result


def save_weekly_norm_history() -> bool:
    data = load_counters()
    current_week = _get_current_week_start()

    week_stats = {}
    for uid_str, info in data.items():
        if not isinstance(info, dict):
            continue
        if info.get('week_start') == current_week:
            count = int(info.get('count', 0))
            if count > 0:
                week_stats[uid_str] = count

    if not week_stats:
        return True

    history = get_norm_history()
    history[current_week] = week_stats

    keys = sorted(history.keys())
    if len(keys) > 52:
        for k in keys[:-52]:
            del history[k]

    return save_json(NORM_HISTORY_FILE, history)


def get_norm_history() -> dict:
    data = load_json(NORM_HISTORY_FILE, {})
    if not isinstance(data, dict):
        return {}
    return data


def reset_all_counters() -> bool:
    data = load_counters()
    current_week = _get_current_week_start()

    new_data = {}
    for uid_str, info in data.items():
        joined_at = ''
        last_message_at = ''
        if isinstance(info, dict):
            joined_at = info.get('joined_at', '')
            last_message_at = info.get('last_message_at', '')
        new_data[uid_str] = {
            'count': 0,
            'week_start': current_week,
            'joined_at': joined_at,
            'last_message_at': last_message_at,
            'norm_notified': False,
        }

    return save_counters(new_data)


def clear_all_counters() -> bool:
    return save_counters({})


def set_joined_at(user_id: int, joined_at: str = None) -> bool:
    if joined_at is None:
        joined_at = _now_msk().isoformat()

    data = load_counters()
    uid_str = str(user_id)

    if uid_str not in data or not isinstance(data[uid_str], dict):
        data[uid_str] = {'count': 0, 'week_start': _get_current_week_start()}

    data[uid_str]['joined_at'] = joined_at
    data[uid_str]['last_message_at'] = _now_msk().isoformat()
    return save_counters(data)


def get_joined_at(user_id: int) -> str:
    data = load_counters()
    uid_str = str(user_id)
    if uid_str not in data or not isinstance(data[uid_str], dict):
        return ''
    return data[uid_str].get('joined_at', '')


def is_new_user(user_id: int, days: int = 7) -> bool:
    joined = get_joined_at(user_id)
    if not joined:
        return True
    try:
        joined_dt = datetime.datetime.fromisoformat(joined)
        delta = _now_msk() - joined_dt
        return delta.days < days
    except (ValueError, TypeError):
        return True


def update_last_message_at(user_id: int) -> bool:
    data = load_counters()
    uid_str = str(user_id)
    if uid_str not in data or not isinstance(data[uid_str], dict):
        return False
    data[uid_str]['last_message_at'] = _now_msk().isoformat()
    return save_counters(data)


def mark_norm_notified(user_id: int) -> bool:
    data = load_counters()
    uid_str = str(user_id)
    current_week = _get_current_week_start()

    if uid_str not in data or not isinstance(data[uid_str], dict):
        data[uid_str] = {'count': 0, 'week_start': current_week}

    if data[uid_str].get('week_start') != current_week:
        data[uid_str]['count'] = 0
        data[uid_str]['week_start'] = current_week

    if 'joined_at' not in data[uid_str]:
        old_data = load_counters().get(uid_str, {})
        if isinstance(old_data, dict) and old_data.get('joined_at'):
            data[uid_str]['joined_at'] = old_data['joined_at']

    data[uid_str]['norm_notified'] = True
    return save_counters(data)


def is_norm_notified(user_id: int) -> bool:
    data = load_counters()
    uid_str = str(user_id)
    if uid_str not in data or not isinstance(data[uid_str], dict):
        return False
    current_week = _get_current_week_start()
    if data[uid_str].get('week_start') != current_week:
        return False
    return bool(data[uid_str].get('norm_notified', False))


def get_last_message_at(user_id: int) -> str:
    data = load_counters()
    uid_str = str(user_id)
    if uid_str not in data or not isinstance(data[uid_str], dict):
        return ''
    return data[uid_str].get('last_message_at', '')

def get_last_7_days_count(user_id: int) -> int:
    data = load_counters()
    uid_str = str(user_id)
    if uid_str not in data or not isinstance(data[uid_str], dict):
        return 0

    history = data[uid_str].get('history', [])
    if not history:
        return 0

    now = datetime.datetime.now(MSK_TZ)
    week_ago = now - datetime.timedelta(days=7)

    count = 0
    for ts_str in history:
        try:
            ts = datetime.datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=MSK_TZ)
            if ts >= week_ago:
                count += 1
        except (ValueError, TypeError):
            continue
    return count