"""
Утилиты для работы с участниками и их ролями
"""

import os
from config import USERS_FILE
from .file_utils import ensure_dirs


def load_users():
    """
    Загружает список участников из файла.
    Формат: id|username|full_name|role|extra
    role - индекс роли (0,1,2,3,4,5)
    extra - дополнительные данные (дата окончания реста и т.д.)
    """
    if not os.path.exists(USERS_FILE):
        return []
    users = []
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split('|')
            if len(parts) >= 4:
                user = {
                    'id': int(parts[0]),
                    'username': parts[1] if parts[1] != 'None' else None,
                    'full_name': parts[2],
                    'role': parts[3] if parts[3] else '0',
                    'extra': parts[4] if len(parts) > 4 else ''
                }
                users.append(user)
            elif len(parts) == 3:
                users.append({
                    'id': int(parts[0]),
                    'username': parts[1] if parts[1] != 'None' else None,
                    'full_name': parts[2],
                    'role': '0',
                    'extra': ''
                })
    return users


def save_users(users):
    ensure_dirs()
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        for u in users:
            f.write(f"{u['id']}|{u['username'] or 'None'}|{u['full_name']}|{u.get('role', '0')}|{u.get('extra', '')}\n")


def add_user(user_id, username, full_name, role="0", extra=""):
    users = load_users()
    for u in users:
        if u['id'] == user_id:
            return False
    users.append({
        'id': user_id,
        'username': username,
        'full_name': full_name,
        'role': role,
        'extra': extra
    })
    save_users(users)
    return True


def remove_user(user_id):
    users = load_users()
    new_users = [u for u in users if u['id'] != user_id]
    if len(new_users) == len(users):
        return False
    save_users(new_users)
    return True


def update_user_role(user_id, new_role, extra=""):
    users = load_users()
    for u in users:
        if u['id'] == user_id:
            u['role'] = new_role
            if extra:
                u['extra'] = extra
            save_users(users)
            return True
    return False


def get_user_role(user_id):
    users = load_users()
    for u in users:
        if u['id'] == user_id:
            return u.get('role', '0')
    return None


def get_users_count():
    return len(load_users())


def get_users_by_role():
    users = load_users()
    roles = {}
    for u in users:
        role = u.get('role', '0')
        if role not in roles:
            roles[role] = []
        roles[role].append(u)
    return roles


def get_role_stats():
    users = load_users()
    stats = {}
    for u in users:
        role = u.get('role', '0')
        stats[role] = stats.get(role, 0) + 1
    return stats


def get_role_names():
    users = load_users()
    names = []
    for u in users:
        if u['full_name'] not in names:
            names.append(u['full_name'])
    return sorted(names)