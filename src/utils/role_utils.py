import os
import json
import logging
from config import DATA_DIR, ROLES_DIR

logger = logging.getLogger(__name__)


# ======================== УТИЛИТЫ ИМЁН ========================

def format_role_display(role_key: str) -> str:
    """'Элиза (Голос времени)' → 'Элиза'"""
    if not role_key:
        return ''
    if '(' in role_key and role_key.endswith(')'):
        return role_key.rsplit('(', 1)[0].strip()
    return role_key


def get_role_season_from_key(role_key: str) -> str:
    """'Элиза (Голос времени)' → 'Голос времени'"""
    if not role_key or '(' not in role_key or not role_key.endswith(')'):
        return ''
    return role_key.rsplit('(', 1)[1][:-1].strip()


def make_role_key(role_name: str, season: str) -> str:
    """'Элиза' + 'Голос времени' → 'Элиза (Голос времени)'"""
    return f"{role_name} ({season})"


# ======================== БАЗОВЫЕ ========================

def load_roles_status() -> dict:
    try:
        status_file = os.path.join(DATA_DIR, 'roles', 'roles_status.json')
        if not os.path.exists(status_file):
            logger.error(f"Файл {status_file} не найден")
            return {}
        with open(status_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.error(f"roles_status.json — не словарь")
            return {}
        return data
    except Exception as e:
        logger.error(f"Ошибка загрузки roles_status.json: {e}")
        return {}


def save_roles_status(roles_data: dict) -> bool:
    try:
        status_file = os.path.join(DATA_DIR, 'roles', 'roles_status.json')
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(roles_data, f, ensure_ascii=False, indent=2)
        logger.info("✅ Данные roles_status.json сохранены")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения roles_status.json: {e}")
        return False


# ======================== ID РОЛЕЙ ========================

def get_role_by_id(role_id: int) -> dict:
    """Находит роль по её ID. Возвращает dict с полями + name + key."""
    data = load_roles_status()
    for role_key, role_info in data.items():
        if isinstance(role_info, dict) and role_info.get('id') == role_id:
            result = dict(role_info)
            result['name'] = format_role_display(role_key)
            result['key'] = role_key
            return result
    return None


# ======================== СЕЗОНЫ И РОЛИ ========================

def get_seasons_list() -> list:
    try:
        data = load_roles_status()
        seasons = set()
        for role_key, role_info in data.items():
            if isinstance(role_info, dict):
                season = role_info.get('season')
                if season:
                    seasons.add(season)
        return sorted(list(seasons))
    except Exception as e:
        logger.error(f"Ошибка получения сезонов: {e}")
        return []


def get_all_seasons() -> list:
    return get_seasons_list()


def get_roles_by_season(season: str) -> list:
    """Список ролей сезона. Каждая: name, key, id, status, owner_id, ..."""
    try:
        data = load_roles_status()
        roles = []
        for role_key, role_info in data.items():
            if isinstance(role_info, dict) and role_info.get('season') == season:
                role = dict(role_info)
                role['name'] = format_role_display(role_key)
                role['key'] = role_key
                roles.append(role)
        return roles
    except Exception as e:
        logger.error(f"Ошибка получения ролей для {season}: {e}")
        return []


def get_role_by_name(role_name: str, season: str = None) -> dict:
    try:
        data = load_roles_status()

        if season:
            role_key = make_role_key(role_name, season)
            role_info = data.get(role_key)
            if role_info and isinstance(role_info, dict):
                result = dict(role_info)
                result['name'] = role_name
                result['key'] = role_key
                return result

        role_info = data.get(role_name)
        if role_info and isinstance(role_info, dict):
            result = dict(role_info)
            result['name'] = format_role_display(role_name)
            result['key'] = role_name
            return result

        for role_key, info in data.items():
            if not isinstance(info, dict):
                continue
            if format_role_display(role_key) == role_name:
                if season and info.get('season') != season:
                    continue
                result = dict(info)
                result['name'] = role_name
                result['key'] = role_key
                return result

        return None
    except Exception as e:
        logger.error(f"Ошибка получения роли {role_name}: {e}")
        return None


def get_role_info(role_name: str, season: str = None) -> dict:
    return get_role_by_name(role_name, season)


def get_role_status(role_name: str, season: str = None) -> str:
    role = get_role_by_name(role_name, season)
    return role.get('status', 'unknown') if role else 'unknown'


def is_role_free(role_name: str, season: str = None) -> bool:
    return get_role_status(role_name, season) == 'свободна'


def update_role_status(role_name: str, season: str, status: str) -> bool:
    try:
        data = load_roles_status()
        role_key = make_role_key(role_name, season)

        if role_key not in data:
            logger.warning(f"Роль '{role_key}' не найдена")
            return False

        old_status = data[role_key].get('status', 'unknown')
        data[role_key]['status'] = status

        if save_roles_status(data):
            logger.info(f"✅ {role_key}: {old_status} -> {status}")
            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка обновления статуса {role_name}: {e}")
        return False


def update_role_status_by_id(role_id: int, status: str) -> bool:
    """Обновляет статус по ID роли."""
    try:
        data = load_roles_status()
        for role_key, role_info in data.items():
            if isinstance(role_info, dict) and role_info.get('id') == role_id:
                old_status = role_info.get('status', 'unknown')
                role_info['status'] = status
                if save_roles_status(data):
                    logger.info(f"✅ ID {role_id} ({role_key}): {old_status} -> {status}")
                    return True
                return False
        logger.warning(f"Роль с ID {role_id} не найдена")
        return False
    except Exception as e:
        logger.error(f"Ошибка обновления по ID {role_id}: {e}")
        return False


def free_role(role_name: str, season: str = None) -> bool:
    try:
        data = load_roles_status()

        if season:
            role_key = make_role_key(role_name, season)
            if role_key not in data:
                return False
        else:
            role_key = None
            if role_name in data:
                role_key = role_name
            else:
                for k, v in data.items():
                    if isinstance(v, dict) and format_role_display(k) == role_name:
                        role_key = k
                        break
            if not role_key:
                return False

        data[role_key]['status'] = 'свободна'
        data[role_key]['owner_id'] = None
        data[role_key]['username'] = None

        if save_roles_status(data):
            logger.info(f"✅ Роль {role_key} освобождена")
            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка освобождения роли {role_name}: {e}")
        return False


# ======================== ПОИСК ========================

def find_roles(query: str) -> list:
    from utils.user_utils import get_user_by_id
    data = load_roles_status()
    if not query or not query.strip():
        return []

    q = query.strip().lower().lstrip('@')
    results = []

    for role_key, role_info in data.items():
        if not isinstance(role_info, dict):
            continue

        short_name = format_role_display(role_key).lower()
        owner_id = role_info.get('owner_id')
        username = (role_info.get('username') or '').lower().lstrip('@')

        match = False

        if q in short_name:
            match = True
        if username and q in username:
            match = True
        if q.isdigit() and owner_id and int(q) == int(owner_id):
            match = True

        full_name = ''
        if owner_id:
            user_data = get_user_by_id(int(owner_id))
            if user_data:
                full_name = user_data.get('full_name', '')
                if q in full_name.lower():
                    match = True

        if match:
            results.append({
                'name': format_role_display(role_key),
                'key': role_key,
                'id': role_info.get('id'),
                'season': role_info.get('season', '?'),
                'status': role_info.get('status', '?'),
                'owner_id': owner_id,
                'username': role_info.get('username', ''),
                'full_name': full_name,
            })

    logger.info(f"🔍 find_roles('{query}') → найдено {len(results)}")
    return results


# ======================== ПОЛЬЗОВАТЕЛИ И РОЛИ ========================

def get_user_role(user_id: int) -> str:
    try:
        data = load_roles_status()
        for role_key, role_info in data.items():
            if isinstance(role_info, dict) and role_info.get('owner_id') == user_id:
                return format_role_display(role_key)
        return ''
    except Exception as e:
        logger.error(f"Ошибка получения роли юзера {user_id}: {e}")
        return ''


def get_user_role_key(user_id: int) -> str:
    try:
        data = load_roles_status()
        for role_key, role_info in data.items():
            if isinstance(role_info, dict) and role_info.get('owner_id') == user_id:
                return role_key
        return ''
    except Exception as e:
        logger.error(f"Ошибка получения ключа роли юзера {user_id}: {e}")
        return ''


def get_taken_roles() -> list:
    try:
        data = load_roles_status()
        taken = []
        for role_key, role_info in data.items():
            if isinstance(role_info, dict) and role_info.get('status') == 'занята':
                taken.append({
                    'season': role_info.get('season', ''),
                    'role': format_role_display(role_key),
                    'key': role_key,
                    'user': role_info.get('username') or 'Неизвестно'
                })
        return taken
    except Exception as e:
        logger.error(f"Ошибка получения занятых ролей: {e}")
        return []


def count_taken_roles() -> int:
    return len(get_taken_roles())


# ======================== СТАТИСТИКА ========================

def get_all_roles() -> dict:
    try:
        data = load_roles_status()
        result = {}
        for role_key, role_info in data.items():
            if isinstance(role_info, dict):
                season = role_info.get('season', 'Без сезона')
                if season not in result:
                    result[season] = []
                role = dict(role_info)
                role['name'] = format_role_display(role_key)
                role['key'] = role_key
                result[season].append(role)
        return result
    except Exception as e:
        logger.error(f"Ошибка получения всех ролей: {e}")
        return {}


def get_season_stats(season: str) -> dict:
    try:
        roles = get_roles_by_season(season)
        total = len(roles)
        free = sum(1 for r in roles if r.get('status') == 'свободна')
        occupied = sum(1 for r in roles if r.get('status') == 'занята')
        return {
            'season': season,
            'total': total,
            'free': free,
            'occupied': occupied,
            'free_percent': round((free / total * 100) if total > 0 else 0, 1)
        }
    except Exception as e:
        logger.error(f"Ошибка статистики {season}: {e}")
        return {'season': season, 'total': 0, 'free': 0, 'occupied': 0, 'free_percent': 0}


def get_all_seasons_stats() -> dict:
    return {season: get_season_stats(season) for season in get_seasons_list()}


def get_free_roles_by_season(season: str) -> list:
    return [r for r in get_roles_by_season(season) if r.get('status') == 'свободна']


def get_occupied_roles_by_season(season: str) -> list:
    return [r for r in get_roles_by_season(season) if r.get('status') == 'занята']


# ======================== НАСТРОЙКИ ========================

def get_system_settings() -> dict:
    try:
        settings_file = os.path.join(DATA_DIR, 'system', 'system_settings.json')
        if not os.path.exists(settings_file):
            default = {
                'closed_mode': False,
                'reminder_enabled': True,
                'welcome_enabled': True,
                'auto_unrest': True,
                'call_cooldown': 30,
                'callfal_cooldown': 60,
                'max_rest_days': 14
            }
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
            return default
        with open(settings_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки system_settings.json: {e}")
        return {}


def save_system_settings(settings: dict) -> bool:
    try:
        settings_file = os.path.join(DATA_DIR, 'system', 'system_settings.json')
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения system_settings.json: {e}")
        return False


def get_closed_mode() -> bool:
    return get_system_settings().get('closed_mode', False)


def set_closed_mode(value: bool) -> bool:
    settings = get_system_settings()
    settings['closed_mode'] = value
    return save_system_settings(settings)


# ======================== СИНХРОНИЗАЦИЯ (с ID) ========================

def _read_season_file(filepath: str) -> list:
    roles = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                roles.append(line)
    except Exception as e:
        logger.error(f"❌ Ошибка чтения {filepath}: {e}")
        return []
    return roles


def sync_roles_from_files() -> dict:
    """
    Синхронизация ролей из data/roles/*.txt.
    Новым ролям присваивается ID.
    """
    from utils.role_ids import get_next_id, add_free_id

    if not os.path.exists(ROLES_DIR):
        logger.warning(f"⚠️ Папка {ROLES_DIR} не найдена")
        return {'added': 0, 'removed': 0, 'kept': 0, 'total_files': 0}

    data = load_roles_status()

    expected_keys = set()
    total_files = 0

    try:
        files = [f for f in os.listdir(ROLES_DIR) if f.endswith('.txt')]
    except Exception as e:
        logger.error(f"❌ Ошибка чтения {ROLES_DIR}: {e}")
        return {'added': 0, 'removed': 0, 'kept': 0, 'total_files': 0}

    for filename in files:
        filepath = os.path.join(ROLES_DIR, filename)
        season_name = os.path.splitext(filename)[0]
        roles = _read_season_file(filepath)
        total_files += 1

        for role_name in roles:
            key = make_role_key(role_name, season_name)
            expected_keys.add(key)

    # Добавляем новые (с ID)
    added = 0
    for key in expected_keys:
        if key not in data:
            season = get_role_season_from_key(key)
            new_id = get_next_id(data)
            data[key] = {
                'id': new_id,
                'status': 'свободна',
                'owner_id': None,
                'username': None,
                'season': season,
                'extra': ''
            }
            added += 1
            logger.info(f"➕ Новая роль '{key}' (ID: {new_id})")

    # Удаляем лишние + освобождаем ID
    removed = 0
    kept = 0
    for key in list(data.keys()):
        if key in expected_keys:
            continue

        role_info = data[key]
        if not isinstance(role_info, dict):
            continue

        owner_id = role_info.get('owner_id')
        if owner_id:
            logger.warning(f"⚠️ Роль '{key}' не в файлах, но занята — оставляю")
            kept += 1
            continue

        # Освобождаем ID
        rid = role_info.get('id')
        if isinstance(rid, int):
            add_free_id(rid)
            logger.info(f"🆔 ID {rid} освобождён (роль '{key}' удалена)")

        del data[key]
        removed += 1
        logger.info(f"➖ Удалена роль '{key}'")

    if added > 0 or removed > 0:
        save_roles_status(data)

    logger.info(f"🔄 Синхронизация: файлов {total_files}, +{added}, -{removed}, сохранено {kept}")
    return {'added': added, 'removed': removed, 'kept': kept, 'total_files': total_files}


def rename_season(old_name: str, new_name: str) -> int:
    data = load_roles_status()
    new_data = {}
    count = 0

    for role_key, role_info in data.items():
        if isinstance(role_info, dict) and role_info.get('season') == old_name:
            short_name = format_role_display(role_key)
            new_key = make_role_key(short_name, new_name)
            role_info['season'] = new_name
            new_data[new_key] = role_info
            count += 1
        else:
            new_data[role_key] = role_info

    if count > 0:
        save_roles_status(new_data)
        logger.info(f"✅ Сезон '{old_name}' → '{new_name}': {count} ролей")

    return count