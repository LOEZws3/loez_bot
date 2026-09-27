"""
Обёртка над parsers.py для обратной совместимости.
Все данные читаются/пишутся через parsers.
"""

import os
import json
import logging

from config import DATA_DIR
from utils import parsers

logger = logging.getLogger(__name__)

USERS_JSON = os.path.join(DATA_DIR, 'users', 'users.json')
UNSUBSCRIBED_FILE = os.path.join(DATA_DIR, 'users', 'unsubscribed_calls.json')


# ======================== ПОЛЬЗОВАТЕЛИ ========================

def load_users() -> list:
    data = parsers.load_users()
    result = []
    for uid_str, info in data.items():
        try:
            uid = int(uid_str)
        except ValueError:
            continue
        result.append({
            'id': uid,
            'username': info.get('username', ''),
            'full_name': info.get('full_name', ''),
            'role': info.get('role', '0'),
            'extra': info.get('extra', '-993'),
            'changes_count': int(info.get('changes_count', 0)),
        })
    return result


def save_users(users: list) -> bool:
    data = {}
    for u in users:
        uid = u.get('id')
        if uid is None:
            continue
        data[str(uid)] = {
            'username': u.get('username', ''),
            'full_name': u.get('full_name', ''),
            'role': u.get('role', '0'),
            'extra': u.get('extra', '-993'),
            'changes_count': int(u.get('changes_count', 0)),
        }
    return parsers.save_users(data)


def add_user(user_id, username, full_name, role='0', extra='-993',
             changes_count: int = 0) -> bool:
    return parsers.add_user(user_id, username, full_name, role, extra, changes_count)


def remove_user(user_id) -> bool:
    return parsers.remove_user(user_id)


def get_users_count() -> int:
    return len(parsers.load_users())


def get_user_by_id(user_id):
    return parsers.get_user(user_id)


def update_user_role(user_id, new_role) -> bool:
    return parsers.update_user_role(user_id, new_role)


def get_user_role(user_id):
    user = parsers.get_user(user_id)
    return user.get('role', '0') if user else None


def get_users_by_role(role_key) -> list:
    return [u for u in load_users() if u.get('role') == role_key]


def get_role_stats() -> dict:
    stats = {}
    for u in load_users():
        role = u.get('role', '0')
        stats[role] = stats.get(role, 0) + 1
    return stats


def get_user_role_stats() -> dict:
    return get_role_stats()


def get_role_names() -> list:
    return list(set(u.get('role', '0') for u in load_users()))


def get_user_info(user_id: int) -> dict:
    try:
        user = parsers.get_user(user_id)
        if user:
            return {
                'user_id': user_id,
                'username': user.get('username', ''),
                'full_name': user.get('full_name', ''),
                'role': user.get('role', ''),
            }
        return {'user_id': user_id, 'username': '', 'full_name': '', 'role': ''}
    except Exception as e:
        logger.error(f"Ошибка получения пользователя {user_id}: {e}")
        return {'user_id': user_id, 'username': '', 'full_name': '', 'role': ''}


def is_user_registered(user_id: int) -> bool:
    return parsers.get_user(user_id) is not None


# ======================== СМЕНЫ РОЛЕЙ ========================

def get_changes_count(user_id) -> int:
    return parsers.get_changes_count(user_id)


def increment_changes_count(user_id) -> bool:
    return parsers.increment_changes_count(user_id)


def reset_changes_count(user_id) -> bool:
    return parsers.reset_changes_count(user_id)