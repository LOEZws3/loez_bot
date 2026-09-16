"""
Единый модуль работы с JSON-файлами.
Все данные бота читаются/пишутся ТОЛЬКО через parsers.

Правило: ранги читаются ТОЛЬКО из admins.json.
OWNER_ID (из .env) — главный владелец.
Дополнительные владельцы — rank=1 в admins.json.
"""

import os
import json
import logging
from typing import Optional, Dict, List, Any

from config import (
    DATA_DIR, OWNER_ID,
    USERS_FILE_JSON, ADMINS_FILE_JSON,
    REQUESTS_FILE, SYSTEM_SETTINGS_FILE,
    ROLES_STATUS_FILE,
)

logger = logging.getLogger(__name__)


# ======================== БАЗОВЫЕ ФУНКЦИИ ========================

def load_json(path: str, default: Any = None) -> Any:
    """Универсальная загрузка JSON"""
    if not os.path.exists(path):
        return default if default is not None else {}

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"❌ Ошибка чтения {path}: {e}")
        return default if default is not None else {}

    return data


def save_json(path: str, data: Any) -> bool:
    """Универсальное сохранение JSON"""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения {path}: {e}")
        return False


# ======================== ПОЛЬЗОВАТЕЛИ ========================

def load_users() -> Dict[str, dict]:
    """Загружает users.json → {id: {username, full_name, role, extra}}"""
    data = load_json(USERS_FILE_JSON, default={})
    if not isinstance(data, dict):
        return {}
    return data


def save_users(users: Dict[str, dict]) -> bool:
    return save_json(USERS_FILE_JSON, users)


def get_user(user_id: int) -> Optional[dict]:
    """Возвращает данные пользователя по ID"""
    users = load_users()
    info = users.get(str(user_id))
    if not info or not isinstance(info, dict):
        return None
    return {
        'id': user_id,
        'username': info.get('username', ''),
        'full_name': info.get('full_name', ''),
        'role': info.get('role', '0'),
        'extra': info.get('extra', '-993'),
    }


def add_user(user_id: int, username: str, full_name: str,
             role: str = '0', extra: str = '-993') -> bool:
    """Добавляет пользователя"""
    users = load_users()
    if str(user_id) in users:
        return False
    users[str(user_id)] = {
        'username': username or '',
        'full_name': (full_name or f"User {user_id}").replace('|', '¦'),
        'role': role or '0',
        'extra': extra or '-993',
    }
    return save_users(users)


def remove_user(user_id: int) -> bool:
    """Удаляет пользователя"""
    users = load_users()
    if str(user_id) in users:
        del users[str(user_id)]
        save_users(users)
        logger.info(f"🗑️ Пользователь {user_id} удалён из users.json")
        return True
    return False


def update_user_role(user_id: int, new_role: str) -> bool:
    """Обновляет роль пользователя"""
    users = load_users()
    if str(user_id) in users:
        users[str(user_id)]['role'] = new_role
        return save_users(users)
    return False


# ======================== АДМИНИСТРАТОРЫ ========================

def load_admins() -> Dict[str, dict]:
    """Загружает admins.json → {id: {username, full_name, rank}}"""
    data = load_json(ADMINS_FILE_JSON, default={})
    if not isinstance(data, dict):
        return {}
    return data


def save_admins(admins: Dict[str, dict]) -> bool:
    return save_json(ADMINS_FILE_JSON, admins)


def get_admin(user_id: int) -> Optional[dict]:
    """Возвращает данные администратора по ID"""
    admins = load_admins()
    info = admins.get(str(user_id))
    if not info or not isinstance(info, dict):
        return None
    return {
        'id': user_id,
        'username': info.get('username', ''),
        'full_name': info.get('full_name', ''),
        'rank': int(info.get('rank', 2)),
    }


def add_admin(user_id: int, username: str = '', full_name: str = '',
              rank: int = 2) -> bool:
    """Добавляет администратора"""
    admins = load_admins()
    if str(user_id) in admins:
        return False
    admins[str(user_id)] = {
        'username': username or '',
        'full_name': (full_name or f"User {user_id}").replace('|', '¦'),
        'rank': rank,
    }
    return save_admins(admins)


def remove_admin(user_id: int) -> bool:
    """Удаляет администратора (кроме OWNER_ID)"""
    if user_id == OWNER_ID:
        logger.warning(f"⛔ Попытка удалить главного владельца {user_id}")
        return False
    admins = load_admins()
    if str(user_id) in admins:
        del admins[str(user_id)]
        return save_admins(admins)
    return False


def set_rank(user_id: int, rank: int) -> bool:
    """Устанавливает ранг (кроме OWNER_ID)"""
    if user_id == OWNER_ID:
        return False
    admins = load_admins()
    if str(user_id) in admins:
        admins[str(user_id)]['rank'] = rank
        return save_admins(admins)
    return False


# ======================== ВЛАДЕЛЬЦЫ (ЕДИНАЯ ЛОГИКА) ========================

def get_owner_ids() -> List[int]:
    """
    Возвращает список всех владельцев:
    - OWNER_ID (из .env) — главный владелец
    - Все с rank=1 в admins.json
    """
    owners = set()
    if OWNER_ID:
        owners.add(OWNER_ID)

    admins = load_admins()
    for uid_str, info in admins.items():
        if isinstance(info, dict) and info.get('rank') == 1:
            try:
                owners.add(int(uid_str))
            except ValueError:
                continue

    return list(owners)


def is_owner(user_id: int) -> bool:
    """Проверяет, владелец ли пользователь (OWNER_ID или rank=1)"""
    return user_id in get_owner_ids()


def is_admin(user_id: int) -> bool:
    """
    Проверяет, админ ли пользователь.
    Ранг читается ТОЛЬКО из admins.json.
    """
    if is_owner(user_id):
        return True
    admins = load_admins()
    return str(user_id) in admins


def get_admin_rank(user_id: int) -> int:
    """
    Возвращает ранг:
    1 — Владелец (OWNER_ID или rank=1 в admins.json)
    2 — Админ (rank=2)
    3 — Модератор (rank=3)
    0 — Нет
    """
    if is_owner(user_id):
        return 1
    admins = load_admins()
    info = admins.get(str(user_id))
    if info and isinstance(info, dict):
        try:
            return int(info.get('rank', 2))
        except (ValueError, TypeError):
            return 2
    return 0


# ======================== ЗАЯВКИ ========================

def load_requests() -> Dict[str, dict]:
    """Загружает requests.json → {id: {...}}"""
    data = load_json(REQUESTS_FILE, default={})
    if not isinstance(data, dict):
        return {}
    return data


def save_requests(requests: Dict[str, dict]) -> bool:
    return save_json(REQUESTS_FILE, requests)


# ======================== НАСТРОЙКИ ========================

def load_settings() -> dict:
    """Загружает system_settings.json"""
    default = {
        'closed_mode': False,
        'reminder_enabled': True,
        'max_rest_days': 14,
        'call_cooldown': 20,
        'callfal_cooldown': 30,
        'welcome_enabled': True,
        'auto_rest_removal': True,
        'forward_enabled': False,
        'anonymous_mode': False,
    }
    data = load_json(SYSTEM_SETTINGS_FILE, default=default)
    if not isinstance(data, dict):
        return default
    return data


def save_settings(settings: dict) -> bool:
    return save_json(SYSTEM_SETTINGS_FILE, settings)


# ======================== РОЛИ ========================

def load_roles_status() -> dict:
    """Загружает roles_status.json → {имя: {...}}"""
    data = load_json(ROLES_STATUS_FILE, default={})
    if not isinstance(data, dict):
        return {}
    return data


def save_roles_status(roles: dict) -> bool:
    return save_json(ROLES_STATUS_FILE, roles)