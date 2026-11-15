"""
Единый модуль работы с JSON-файлами.
Все данные бота читаются/пишутся ТОЛЬКО через parsers.
"""

import os
import json
import logging
import shutil
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

from config import (
    DATA_DIR, OWNER_ID,
    USERS_FILE_JSON, ADMINS_FILE_JSON,
    REQUESTS_FILE, SYSTEM_SETTINGS_FILE,
    ROLES_STATUS_FILE,
)

logger = logging.getLogger(__name__)


DEFAULT_USER_FIELDS = {
    "username": "",
    "full_name": "",
    "role": "",
    "extra": "",
    "changes_count": 0,
    "birthday": None,
    "notify_norm": True,
    "grace_until": None,
    "rest": False,
    "rest_end_date": None,
    "agreed_to_privacy": False,
    "is_fully_registered": False,
    "apply_sent": False,
    "invite_link": None,
    "invite_expire": None,
    "rating": 50
}
# ======================== ⚠️ НОВОЕ: КЭШ ========================
_cache = {
    'users': None,
    'admins': None,
    'roles_status': None,
}


def clear_cache():
    """Сбрасывает кэш (нужно, если файлы менялись вручную)."""
    global _cache
    _cache['users'] = None
    _cache['admins'] = None
    _cache['roles_status'] = None
    logger.info("🧹 Кэш JSON сброшен")


# ======================== ⚠️ НОВОЕ: ЛОГГЕР ДЛЯ ДЕЙСТВИЙ АДМИНОВ ========================
admin_logger = logging.getLogger('admin_actions')
admin_logger.setLevel(logging.INFO)
admin_log_path = os.path.join(DATA_DIR, 'logs', 'admin_actions.log')
os.makedirs(os.path.dirname(admin_log_path), exist_ok=True)
admin_handler = logging.FileHandler(admin_log_path, encoding='utf-8')
admin_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
admin_logger.addHandler(admin_handler)


# ======================== БАЗОВЫЕ ФУНКЦИИ ========================

def load_json(path: str, default: Any = None) -> Any:
    """Загружает JSON. При ошибке возвращает default, но НЕ затирает файл."""
    if not os.path.exists(path):
        return default if default is not None else {}

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"❌ Ошибка чтения {path}: {e}")
        # Пытаемся загрузить резервную копию
        backup_path = path + '.bak'
        if os.path.exists(backup_path):
            try:
                with open(backup_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.warning(f"⚠️ Загружена резервная копия {backup_path}")
                return data
            except Exception:
                pass
        return default if default is not None else {}

    return data


def save_json(path: str, data: Any) -> bool:
    """Атомарная запись JSON с резервной копией."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # Создаём резервную копию (если файл существует)
        if os.path.exists(path):
            backup_path = path + '.bak'
            try:
                shutil.copy2(path, backup_path)
            except Exception as e:
                logger.warning(f"⚠️ Не удалось создать бэкап {path}: {e}")

        # Пишем во временный файл
        tmp_path = path + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Атомарно заменяем
        os.replace(tmp_path, path)
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения {path}: {e}")
        return False


# ======================== ПОЛЬЗОВАТЕЛИ ========================

def load_users() -> Dict[str, dict]:
    if _cache['users'] is not None:
        return _cache['users']

    data = load_json(USERS_FILE_JSON, default={})
    if not isinstance(data, dict):
        data = {}

    _cache['users'] = data
    return data


def save_users(users: Dict[str, dict]) -> bool:
    global _cache
    if save_json(USERS_FILE_JSON, users):
        _cache['users'] = users
        return True
    return False


def get_user(user_id) -> dict:
    users = load_users()
    user_id_str = str(user_id)
    
    if user_id_str in users:
        user = users[user_id_str]
        # 🚀 Нормализация: добавляем недостающие поля "на лету"
        for key, default in DEFAULT_USER_FIELDS.items():
            if key not in user:
                user[key] = default
        return user
        
    return None


def add_user(user_id, username, full_name):
    users = load_users()
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        # 🚀 Создаем нового юзера сразу с дефолтными полями
        new_user = DEFAULT_USER_FIELDS.copy()
        new_user["username"] = username or ""
        new_user["full_name"] = full_name or ""
        
        users[user_id_str] = new_user
        save_users(users)
        return True
    return False

def remove_user(user_id: int) -> bool:
    users = load_users()
    if str(user_id) in users:
        del users[str(user_id)]
        save_users(users)
        logger.info(f"🗑️ Пользователь {user_id} удалён из users.json")
        return True
    return False


def update_user_role(user_id: int, new_role: str) -> bool:
    users = load_users()
    if str(user_id) in users:
        users[str(user_id)]['role'] = new_role
        return save_users(users)
    return False


def get_changes_count(user_id: int) -> int:
    users = load_users()
    info = users.get(str(user_id))
    if not info or not isinstance(info, dict):
        return 0
    return int(info.get('changes_count', 0))


def increment_changes_count(user_id: int) -> bool:
    users = load_users()
    uid_str = str(user_id)
    if uid_str not in users:
        return False
    current = int(users[uid_str].get('changes_count', 0))
    users[uid_str]['changes_count'] = current + 1
    return save_users(users)


def reset_changes_count(user_id: int) -> bool:
    users = load_users()
    uid_str = str(user_id)
    if uid_str not in users:
        return False
    users[uid_str]['changes_count'] = 0
    return save_users(users)


# ======================== ⚠️ НОВОЕ: ЛЬГОТНЫЙ ПЕРИОД ========================

def set_grace_period(user_id: int, days: int = 4) -> bool:
    users = load_users()
    uid_str = str(user_id)
    if uid_str not in users:
        return False

    grace_until = (datetime.now() + timedelta(days=days)).isoformat()
    users[uid_str]['grace_until'] = grace_until
    return save_users(users)


# ======================== ДЕНЬ РОЖДЕНИЯ ========================

def set_birthday(user_id: int, birthday: str) -> bool:
    users = load_users()
    uid_str = str(user_id)
    if uid_str not in users:
        return False
    users[uid_str]['birthday'] = birthday
    return save_users(users)


def get_birthday(user_id: int) -> Optional[str]:
    users = load_users()
    info = users.get(str(user_id))
    if not info or not isinstance(info, dict):
        return None
    return info.get('birthday', None)


def get_users_with_birthday(day: int, month: int) -> List[dict]:
    users = load_users()
    result = []
    target = f"{day:02d}.{month:02d}"
    for uid_str, info in users.items():
        if not isinstance(info, dict):
            continue
        bday = info.get('birthday')
        if bday == target:
            try:
                uid = int(uid_str)
            except ValueError:
                continue
            result.append({
                'id': uid,
                'username': info.get('username', ''),
                'full_name': info.get('full_name', ''),
                'role': info.get('role', '0'),
                'birthday': bday,
            })
    return result


# ======================== ПОДПИСКА НА НОРМУ ========================

def set_notify_norm(user_id: int, value: bool) -> bool:
    users = load_users()
    uid_str = str(user_id)
    if uid_str not in users:
        return False
    users[uid_str]['notify_norm'] = bool(value)
    return save_users(users)


def get_notify_norm(user_id: int) -> bool:
    users = load_users()
    info = users.get(str(user_id))
    if not info or not isinstance(info, dict):
        return True
    return bool(info.get('notify_norm', True))


# ======================== АДМИНИСТРАТОРЫ ========================

def load_admins() -> Dict[str, dict]:
    if _cache['admins'] is not None:
        return _cache['admins']

    data = load_json(ADMINS_FILE_JSON, default={})
    if not isinstance(data, dict):
        data = {}

    _cache['admins'] = data
    return data


def save_admins(admins: Dict[str, dict]) -> bool:
    global _cache
    if save_json(ADMINS_FILE_JSON, admins):
        _cache['admins'] = admins
        return True
    return False


def get_admin(user_id: int) -> Optional[dict]:
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
    if user_id == OWNER_ID:
        logger.warning(f"⛔ Попытка удалить главного владельца {user_id}")
        return False
    admins = load_admins()
    if str(user_id) in admins:
        del admins[str(user_id)]
        return save_admins(admins)
    return False


def set_rank(user_id: int, rank: int) -> bool:
    if user_id == OWNER_ID:
        return False
    admins = load_admins()
    if str(user_id) in admins:
        admins[str(user_id)]['rank'] = rank
        return save_admins(admins)
    return False


# ======================== ВЛАДЕЛЬЦЫ (ЕДИНАЯ ЛОГИКА) ========================

def get_owner_ids() -> List[int]:
    owners = set()
    if OWNER_ID:
        owners.add(OWNER_ID)

    admins = load_admins()
    for uid_str, info in admins.items():
        if isinstance(info, dict):
            try:
                uid_int = int(uid_str)
                if int(info.get('rank', 0)) == 1:
                    owners.add(uid_int)
            except (ValueError, TypeError):
                continue

    return list(owners)


def is_owner(user_id: int) -> bool:
    return user_id in get_owner_ids()


def is_admin(user_id: int) -> bool:
    if is_owner(user_id):
        return True
    admins = load_admins()
    return str(user_id) in admins


def get_admin_rank(user_id: int) -> int:
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
    data = load_json(REQUESTS_FILE, default={})
    if not isinstance(data, dict):
        return {}
    return data


def save_requests(requests: Dict[str, dict]) -> bool:
    return save_json(REQUESTS_FILE, requests)


# ======================== НАСТРОЙКИ ========================

def load_settings() -> dict:
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
        'max_role_changes': 3,
    }
    data = load_json(SYSTEM_SETTINGS_FILE, default=default)
    if not isinstance(data, dict):
        return default
    return data


def save_settings(settings: dict) -> bool:
    return save_json(SYSTEM_SETTINGS_FILE, settings)


# ======================== РОЛИ ========================

def load_roles_status() -> dict:
    if _cache['roles_status'] is not None:
        return _cache['roles_status']

    data = load_json(ROLES_STATUS_FILE, default={})
    if not isinstance(data, dict):
        data = {}

    _cache['roles_status'] = data
    return data


def save_roles_status(roles: dict) -> bool:
    global _cache
    if save_json(ROLES_STATUS_FILE, roles):
        _cache['roles_status'] = roles
        return True
    return False


# ======================== РЕСТЫ ========================

def set_rest_status(user_id: int, rest: bool, end_date: str = None) -> bool:
    users = load_users()
    uid_str = str(user_id)
    if uid_str not in users:
        return False

    users[uid_str]['rest'] = bool(rest)
    users[uid_str]['rest_end_date'] = end_date if rest else None
    return save_users(users)