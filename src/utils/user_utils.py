import os
import json
import logging

logger = logging.getLogger(__name__)

USERS_FILE = "data/users/users.txt"
UNSUBSCRIBED_FILE = "data/users/unsubscribed_calls.txt"


# ============================================================
# ОСНОВНЫЕ ФУНКЦИИ ПОЛЬЗОВАТЕЛЕЙ
# ============================================================

def ensure_users_file():
    """Создает файл пользователей, если его нет."""
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w') as f:
            json.dump([], f)


def load_users():
    """Загружает список пользователей из файла."""
    ensure_users_file()
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_users(users):
    """Сохраняет список пользователей в файл."""
    ensure_users_file()
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)


def add_user(user_id, username, full_name, role='0'):
    """Добавляет нового пользователя."""
    users = load_users()
    for u in users:
        if u['id'] == user_id:
            return False  # Уже существует

    new_user = {
        'id': user_id,
        'username': username,
        'full_name': full_name,
        'role': role
    }
    users.append(new_user)
    save_users(users)
    return True


def remove_user(user_id):
    """Удаляет пользователя по ID."""
    users = load_users()
    new_users = [u for u in users if u['id'] != user_id]
    if len(new_users) < len(users):
        save_users(new_users)
        return True
    return False


def get_users_count():
    """Возвращает количество пользователей."""
    return len(load_users())


def get_user_by_id(user_id):
    """Ищет пользователя по ID."""
    users = load_users()
    for u in users:
        if u['id'] == user_id:
            return u
    return None


def update_user_role(user_id, new_role):
    """Обновляет роль пользователя."""
    users = load_users()
    for u in users:
        if u['id'] == user_id:
            u['role'] = new_role
            save_users(users)
            return True
    return False


def get_user_role(user_id):
    """Получает роль пользователя."""
    user = get_user_by_id(user_id)
    if user:
        return user.get('role', '0')
    return None


def get_users_by_role(role_key):
    """Возвращает список пользователей с определенной ролью."""
    users = load_users()
    return [u for u in users if u.get('role') == role_key]


def get_role_stats():
    """Возвращает статистику по ролям (словарь {роль: количество})."""
    users = load_users()
    stats = {}
    for u in users:
        role = u.get('role', '0')
        if role not in stats:
            stats[role] = 0
        stats[role] += 1
    return stats


def get_role_names():
    """Возвращает список всех уникальных ролей."""
    users = load_users()
    roles = set()
    for u in users:
        roles.add(u.get('role', '0'))
    return list(roles)


# ============================================================
# СИСТЕМА ОТВИЗКИ ОТ КАЛОВ
# ============================================================

def ensure_unsubscribed_file():
    """Создает файл отписок, если его нет."""
    os.makedirs(os.path.dirname(UNSUBSCRIBED_FILE), exist_ok=True)
    if not os.path.exists(UNSUBSCRIBED_FILE):
        with open(UNSUBSCRIBED_FILE, 'w') as f:
            json.dump([], f)


def load_unsubscribed():
    """Загружает список ID отписавшихся пользователей."""
    ensure_unsubscribed_file()
    try:
        with open(UNSUBSCRIBED_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_unsubscribed(unsubscribed_list):
    """Сохраняет список ID отписавшихся пользователей."""
    ensure_unsubscribed_file()
    with open(UNSUBSCRIBED_FILE, 'w') as f:
        json.dump(unsubscribed_list, f, indent=4)


def add_unsubscribed(user_id):
    """Добавляет пользователя в список отписавшихся."""
    unsubscribed = load_unsubscribed()
    if user_id not in unsubscribed:
        unsubscribed.append(user_id)
        save_unsubscribed(unsubscribed)
        logger.info(f"🔕 Пользователь {user_id} добавлен в список отписок")
        return True
    return False


def remove_unsubscribed(user_id):
    """Удаляет пользователя из списка отписавшихся."""
    unsubscribed = load_unsubscribed()
    if user_id in unsubscribed:
        unsubscribed.remove(user_id)
        save_unsubscribed(unsubscribed)
        logger.info(f"🔔 Пользователь {user_id} удален из списка отписок")
        return True
    return False


def is_unsubscribed(user_id):
    """Проверяет, отписан ли пользователь от калов."""
    unsubscribed = load_unsubscribed()
    return user_id in unsubscribed


def sync_unsubscribed_with_users(users_ids):
    """
    Синхронизирует список отписавшихся с актуальным списком участников.
    Удаляет из отписок тех, кого нет в users.txt.
    Возвращает количество удаленных записей.
    """
    unsubscribed = load_unsubscribed()
    # Оставляем в списке отписок только тех, кто есть в текущем списке участников
    new_unsubscribed = [uid for uid in unsubscribed if uid in users_ids]

    removed_count = len(unsubscribed) - len(new_unsubscribed)

    if removed_count > 0:
        save_unsubscribed(new_unsubscribed)
        logger.info(f"🔄 Синхронизация отписок: удалено {removed_count} записей несуществующих пользователей")

    return removed_count