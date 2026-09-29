"""
Утилита для работы с варнами.
Файл: data/system/warns.json

Формат:
{
    "8076284478": [
        {
            "id": 1,
            "issued_at": "2026-09-28T21:00:00",
            "expire_at": "2026-10-04T21:00:00",
            "issued_by": 8076284478,
            "reason": "Не набрал норму"
        }
    ]
}
"""

import os
import json
import datetime
import logging

from config import DATA_DIR

logger = logging.getLogger(__name__)

WARNS_FILE = os.path.join(DATA_DIR, 'system', 'warns.json')


def load_warns() -> dict:
    try:
        os.makedirs(os.path.dirname(WARNS_FILE), exist_ok=True)
        if not os.path.exists(WARNS_FILE):
            return {}
        with open(WARNS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Ошибка чтения warns.json: {e}")
        return {}


def save_warns(data: dict) -> bool:
    try:
        os.makedirs(os.path.dirname(WARNS_FILE), exist_ok=True)
        with open(WARNS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения warns.json: {e}")
        return False


def get_user_warns(user_id: int) -> list:
    """Все активные варны юзера."""
    data = load_warns()
    return data.get(str(user_id), [])


def get_warns_count(user_id: int) -> int:
    """Количество активных варнов."""
    return len(get_user_warns(user_id))


def add_warn(user_id: int, days: int, issued_by: int, reason: str = "") -> dict:
    """
    Добавляет варн юзеру. days — срок в днях.
    Возвращает созданный варн.
    """
    data = load_warns()
    uid_str = str(user_id)
    if uid_str not in data or not isinstance(data[uid_str], list):
        data[uid_str] = []

    now = datetime.datetime.now()
    expire_at = now + datetime.timedelta(days=days)

    # Генерируем id
    existing_ids = [w.get('id', 0) for w in data[uid_str] if isinstance(w, dict)]
    new_id = max(existing_ids, default=0) + 1

    warn = {
        'id': new_id,
        'issued_at': now.isoformat(),
        'expire_at': expire_at.isoformat(),
        'issued_by': issued_by,
        'reason': reason,
    }
    data[uid_str].append(warn)
    save_warns(data)
    logger.info(f"⚠️ Варн #{new_id} выдан {user_id} на {days} дней")
    return warn


def remove_warn(user_id: int, warn_id: int) -> bool:
    """Удаляет конкретный варн."""
    data = load_warns()
    uid_str = str(user_id)
    if uid_str not in data:
        return False
    original_len = len(data[uid_str])
    data[uid_str] = [w for w in data[uid_str] if w.get('id') != warn_id]
    if len(data[uid_str]) < original_len:
        save_warns(data)
        return True
    return False


def clear_user_warns(user_id: int) -> bool:
    """Удаляет все варны юзера."""
    data = load_warns()
    uid_str = str(user_id)
    if uid_str in data:
        del data[uid_str]
        save_warns(data)
        return True
    return True


def expire_old_warns() -> int:
    """Удаляет истёкшие варны. Возвращает количество удалённых."""
    data = load_warns()
    now = datetime.datetime.now()
    removed = 0

    for uid_str in list(data.keys()):
        if not isinstance(data[uid_str], list):
            continue
        before = len(data[uid_str])
        new_list = []
        for w in data[uid_str]:
            if not isinstance(w, dict):
                continue
            expire_str = w.get('expire_at')
            if not expire_str:
                new_list.append(w)
                continue
            try:
                expire_at = datetime.datetime.fromisoformat(expire_str)
                if expire_at > now:
                    new_list.append(w)
                else:
                    removed += 1
            except (ValueError, TypeError):
                new_list.append(w)

        if len(new_list) != before:
            data[uid_str] = new_list

    if removed > 0:
        save_warns(data)
        logger.info(f"🕐 Удалено истёкших варнов: {removed}")

    return removed


def get_last_warn_number(user_id: int, limit: int = 3) -> str:
    """
    Возвращает текстовое описание: сколько варнов осталось до лимита.
    Например: '2 из 3'
    """
    count = get_warns_count(user_id)
    return f"{count} из {limit}"