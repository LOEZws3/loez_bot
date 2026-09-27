"""
Утилита для работы с уникальными ID ролей.
ID хранятся в roles_status.json (поле "id").
Свободные ID — в data/system/free_role_ids.json.
"""

import os
import json
import logging
from config import DATA_DIR

logger = logging.getLogger(__name__)

FREE_IDS_FILE = os.path.join(DATA_DIR, 'system', 'free_role_ids.json')


def load_free_ids() -> list:
    """Загружает список свободных ID."""
    try:
        os.makedirs(os.path.dirname(FREE_IDS_FILE), exist_ok=True)
        if not os.path.exists(FREE_IDS_FILE):
            with open(FREE_IDS_FILE, 'w', encoding='utf-8') as f:
                json.dump([], f)
            return []
        with open(FREE_IDS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return sorted([int(x) for x in data if isinstance(x, (int, str)) and str(x).isdigit()])
    except Exception as e:
        logger.error(f"Ошибка загрузки free_role_ids.json: {e}")
        return []


def save_free_ids(ids: list) -> bool:
    """Сохраняет список свободных ID."""
    try:
        os.makedirs(os.path.dirname(FREE_IDS_FILE), exist_ok=True)
        with open(FREE_IDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(sorted(ids), f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения free_role_ids.json: {e}")
        return False


def get_next_id(roles_status: dict) -> int:
    """
    Возвращает следующий доступный ID.
    Сначала из free_role_ids, иначе max+1.
    """
    free = load_free_ids()
    if free:
        next_id = free.pop(0)
        save_free_ids(free)
        return next_id

    # Ищем максимальный ID среди ролей
    max_id = 0
    for role_key, info in roles_status.items():
        if isinstance(info, dict):
            rid = info.get('id')
            if isinstance(rid, int) and rid > max_id:
                max_id = rid
    return max_id + 1


def add_free_id(role_id: int) -> bool:
    """Добавляет ID в список свободных."""
    if not isinstance(role_id, int) or role_id <= 0:
        return False
    free = load_free_ids()
    if role_id not in free:
        free.append(role_id)
        return save_free_ids(free)
    return True


def get_stats(roles_status: dict) -> dict:
    """Возвращает статистику по ID."""
    used_ids = []
    missing_id = 0

    for role_key, info in roles_status.items():
        if not isinstance(info, dict):
            continue
        rid = info.get('id')
        if isinstance(rid, int):
            used_ids.append(rid)
        else:
            missing_id += 1

    free_ids = load_free_ids()

    return {
        'total_roles': len(roles_status),
        'with_id': len(used_ids),
        'missing_id': missing_id,
        'max_id': max(used_ids) if used_ids else 0,
        'free_count': len(free_ids),
        'free_ids': free_ids,
    }