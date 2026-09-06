import os
import json
import logging
from config import ROLES_DIR, ROLES_STATUS_FILE

logger = logging.getLogger(__name__)


def ensure_roles_dir():
    """Создаёт папку для ролей, если её нет"""
    if not os.path.exists(ROLES_DIR):
        os.makedirs(ROLES_DIR)
        logger.info(f"📁 Создана папка ролей: {ROLES_DIR}")


def get_all_seasons() -> list:
    """Возвращает список всех сезонов (названия файлов без расширения)"""
    ensure_roles_dir()
    
    seasons = []
    for file in os.listdir(ROLES_DIR):
        if file.endswith('.txt'):
            seasons.append(file[:-4])  # Убираем .txt
    return sorted(seasons)


def get_roles_by_season(season: str) -> list:
    """Возвращает список ролей из файла сезона"""
    # ✅ ИСПРАВЛЕНО: используем os.path.join вместо /
    file_path = os.path.join(ROLES_DIR, f"{season}.txt")
    
    if not os.path.exists(file_path):
        logger.warning(f"⚠️ Файл сезона не найден: {file_path}")
        return []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            roles = [line.strip() for line in f if line.strip()]
        return roles
    except Exception as e:
        logger.error(f"❌ Ошибка чтения {file_path}: {e}")
        return []


def load_roles_status() -> dict:
    """Загружает статусы ролей из JSON"""
    if not os.path.exists(ROLES_STATUS_FILE):
        return {}
    
    try:
        with open(ROLES_STATUS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_roles_status(status: dict):
    """Сохраняет статусы ролей в JSON"""
    os.makedirs(os.path.dirname(ROLES_STATUS_FILE), exist_ok=True)
    with open(ROLES_STATUS_FILE, 'w', encoding='utf-8') as f:
        json.dump(status, f, indent=4, ensure_ascii=False)


def get_role_status(role_name: str) -> dict:
    """Возвращает статус конкретной роли"""
    status = load_roles_status()
    return status.get(role_name, {})


def get_role_by_name(role_name: str) -> dict:
    """Возвращает данные роли по имени"""
    status = load_roles_status()
    return status.get(role_name, {})


def update_role_status(role_name: str, status: str, owner_id: int = None, username: str = None, extra: str = "") -> bool:
    """Обновляет статус роли"""
    roles = load_roles_status()
    
    if role_name not in roles:
        roles[role_name] = {}
    
    roles[role_name]['status'] = status
    roles[role_name]['owner_id'] = owner_id
    roles[role_name]['username'] = username
    roles[role_name]['extra'] = extra or ""
    
    save_roles_status(roles)
    return True


def get_user_role(user_id: int) -> str:
    """Возвращает имя роли, которую занимает пользователь"""
    roles = load_roles_status()
    for role_name, data in roles.items():
        if data.get('owner_id') == user_id:
            return role_name
    return None


def get_taken_roles() -> list:
    """Возвращает список занятых ролей"""
    roles = load_roles_status()
    taken = []
    for role_name, data in roles.items():
        if data.get('status') in ['занята', 'бронь'] and data.get('owner_id'):
            taken.append(role_name)
    return taken


def get_role_stats() -> dict:
    """Возвращает статистику по ролям (словарь {статус: количество})"""
    roles = load_roles_status()
    stats = {
        'свободна': 0,
        'занята': 0,
        'бронь': 0,
        'рест': 0
    }
    for data in roles.values():
        status = data.get('status', 'свободна')
        if status in stats:
            stats[status] += 1
        else:
            stats['свободна'] += 1
    return stats


def count_taken_roles() -> int:
    """Возвращает количество занятых ролей"""
    return len(get_taken_roles())


def occupy_role(role_name: str, user_id: int, username: str) -> bool:
    """Занимает роль пользователем"""
    role = get_role_by_name(role_name)
    if not role or role.get('status') != 'свободна':
        return False
    
    return update_role_status(role_name, 'занята', user_id, username, "")


def free_role(user_id: int) -> str:
    """Освобождает роль пользователя"""
    role_name = get_user_role(user_id)
    if not role_name:
        return None
    
    update_role_status(role_name, 'свободна', None, None, "")
    return role_name


def set_rest(role_name: str, days: int) -> bool:
    """Устанавливает рест для роли"""
    role = get_role_by_name(role_name)
    if not role or role.get('status') != 'занята':
        return False
    
    from datetime import datetime, timedelta
    rest_until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    return update_role_status(role_name, 'рест', role.get('owner_id'), role.get('username'), rest_until)


def clear_rest(role_name: str) -> bool:
    """Снимает рест с роли"""
    role = get_role_by_name(role_name)
    if not role or role.get('status') != 'рест':
        return False
    
    return update_role_status(role_name, 'занята', role.get('owner_id'), role.get('username'), "")