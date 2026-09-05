import os
import json
import datetime
from config import ROLES_DIR, ROLES_STATUS_FILE
from .file_utils import ensure_dirs


def ensure_roles_dir():
    ensure_dirs()
    if not os.path.exists(ROLES_DIR):
        os.makedirs(ROLES_DIR)


def load_roles():
    status_data = load_roles_status()
    roles = []
    for name, data in status_data.items():
        roles.append({
            'name': name,
            'status': data.get('status', 'свободна'),
            'owner_id': data.get('owner_id'),
            'username': data.get('username'),
            'season': data.get('season', 'Неизвестно'),
            'extra': data.get('extra', '')
        })
    return roles


def save_roles(roles):
    status_data = {}
    for r in roles:
        status_data[r['name']] = {
            'status': r.get('status', 'свободна'),
            'owner_id': r.get('owner_id'),
            'username': r.get('username'),
            'season': r.get('season', 'Неизвестно'),
            'extra': r.get('extra', '')
        }
    save_roles_status(status_data)


def load_roles_status():
    ensure_roles_dir()
    if not os.path.exists(ROLES_STATUS_FILE):
        roles = load_all_role_names()
        status_data = {}
        for role in roles:
            status_data[role] = {
                "status": "свободна",
                "owner_id": None,
                "username": None,
                "season": get_season_for_role(role),
                "extra": ""
            }
        save_roles_status(status_data)
        return status_data

    with open(ROLES_STATUS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_roles_status(status_data):
    ensure_roles_dir()
    with open(ROLES_STATUS_FILE, 'w', encoding='utf-8') as f:
        json.dump(status_data, f, ensure_ascii=False, indent=2)


def load_all_role_names():
    ensure_roles_dir()
    all_roles = []
    for file in os.listdir(ROLES_DIR):
        if file.endswith('.txt'):
            file_path = ROLES_DIR / file
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        all_roles.append(line)
    return all_roles


def get_season_for_role(role_name):
    ensure_roles_dir()
    for file in os.listdir(ROLES_DIR):
        if file.endswith('.txt'):
            file_path = ROLES_DIR / file
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip() == role_name:
                        return file.replace('.txt', '')
    return "Неизвестно"


def get_all_seasons():
    ensure_roles_dir()
    seasons = []
    for file in os.listdir(ROLES_DIR):
        if file.endswith('.txt'):
            seasons.append(file.replace('.txt', ''))
    return sorted(seasons)


def get_roles_by_season(season):
    ensure_roles_dir()
    file_path = ROLES_DIR / f"{season}.txt"
    if not os.path.exists(file_path):
        return []
    roles = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                roles.append(line)
    return roles


def get_role_by_name(role_name):
    status_data = load_roles_status()
    if role_name not in status_data:
        return None
    data = status_data[role_name]
    return {
        'name': role_name,
        'status': data.get('status', 'свободна'),
        'owner_id': data.get('owner_id'),
        'username': data.get('username'),
        'season': data.get('season', 'Неизвестно'),
        'extra': data.get('extra', '')
    }


def get_role_status(role_name):
    role = get_role_by_name(role_name)
    return role['status'] if role else None


def update_role_status(role_name, status, owner_id=None, username=None, extra=None):
    """Обновляет статус роли, опционально с extra."""
    status_data = load_roles_status()
    if role_name not in status_data:
        return False
    status_data[role_name]["status"] = status
    status_data[role_name]["owner_id"] = owner_id
    status_data[role_name]["username"] = username
    if extra is not None:
        status_data[role_name]["extra"] = extra
    else:
        status_data[role_name]["extra"] = ""
    save_roles_status(status_data)
    return True


def set_rest(role_name, until_date_str):
    """Устанавливает рест для роли до указанной даты (строка YYYY-MM-DD). Записывает дату в extra."""
    role = get_role_by_name(role_name)
    if role is None:
        return False
    if role['status'] != 'занята':
        return False
    # Парсим дату
    try:
        until_date = datetime.date.fromisoformat(until_date_str)
    except ValueError:
        return False
    if until_date <= datetime.date.today():
        return False
    # Обновляем статус и записываем дату в extra
    return update_role_status(role_name, 'рест', role['owner_id'], role['username'], until_date_str)


def clear_rest(role_name):
    """Снимает рест с роли (возвращает статус в 'занята') и очищает extra."""
    role = get_role_by_name(role_name)
    if role is None:
        return False
    if role['status'] != 'рест':
        return False
    return update_role_status(role_name, 'занята', role['owner_id'], role['username'], "")


def check_expired_rests():
    """Проверяет все роли со статусом 'рест' и освобождает их, если дата в extra истекла."""
    status_data = load_roles_status()
    today = datetime.date.today()
    updated = False
    for role_name, data in status_data.items():
        if data.get('status') == 'рест' and data.get('extra'):
            extra = data['extra']
            try:
                rest_until = datetime.date.fromisoformat(extra)
                if rest_until <= today:
                    # Возвращаем в занята и очищаем extra
                    data['status'] = 'занята'
                    data['extra'] = ""
                    updated = True
            except ValueError:
                # Если в extra не дата — игнорируем
                continue
    if updated:
        save_roles_status(status_data)
    return updated


def get_taken_roles():
    """Возвращает список занятых ролей (статусы 'занята' и 'рест')."""
    status_data = load_roles_status()
    return [role for role, data in status_data.items() if data.get('status') in ('занята', 'рест')]


def count_taken_roles() -> int:
    """Возвращает количество занятых ролей (статусы 'занята' и 'рест')."""
    status_data = load_roles_status()
    return sum(1 for data in status_data.values() if data.get('status') in ('занята', 'рест'))


def get_role_stats():
    status_data = load_roles_status()
    stats = {
        "всего": len(status_data),
        "свободна": 0,
        "бронь": 0,
        "занята": 0,
        "рест": 0,
    }
    for data in status_data.values():
        status = data.get("status", "свободна")
        if status in stats:
            stats[status] += 1
    return stats


def get_user_role(user_id):
    status_data = load_roles_status()
    for role, data in status_data.items():
        if data.get("owner_id") == user_id:
            return role
    return None


def occupy_role(user_id, username, full_name, role_name):
    role = get_role_by_name(role_name)
    if role is None:
        return False, "Роль не найдена"
    if role['status'] == 'занята' or role['status'] == 'рест':
        return False, "Роль уже занята"
    if role['status'] == 'бронь':
        return False, "Роль забронирована"
    update_role_status(role_name, 'занята', user_id, username, "")
    return True, "Роль занята"


def free_role(user_id):
    role_name = get_user_role(user_id)
    if role_name:
        update_role_status(role_name, 'свободна', None, None, "")
        return role_name
    return None