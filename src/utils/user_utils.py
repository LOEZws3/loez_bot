import os
import json
import logging
from config import DATA_DIR

logger = logging.getLogger(__name__)

# ======================== ПУТИ ========================

USERS_JSON = os.path.join(DATA_DIR, 'users', 'users.json')
USERS_TXT_LEGACY = os.path.join(DATA_DIR, 'users', 'users.txt')
UNSUBSCRIBED_FILE = os.path.join(DATA_DIR, 'users', 'unsubscribed_calls.json')


# ======================== МИГРАЦИЯ ========================

def _migrate_from_txt_if_needed() -> bool:
    """
    Если есть users.txt, но нет users.json — конвертирует.
    Возвращает True, если миграция выполнена.
    """
    if not os.path.exists(USERS_TXT_LEGACY):
        return False
    if os.path.exists(USERS_JSON):
        return False

    logger.info("🔄 Миграция users.txt → users.json...")
    users = {}
    try:
        with open(USERS_TXT_LEGACY, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split('|', maxsplit=4)
                if len(parts) < 4:
                    continue
                try:
                    user_id = int(parts[0])
                except ValueError:
                    continue
                users[str(user_id)] = {
                    'username': parts[1] if len(parts) > 1 else '',
                    'full_name': parts[2] if len(parts) > 2 else '',
                    'role': parts[3] if len(parts) > 3 else '0',
                    'extra': parts[4] if len(parts) > 4 else '-993'
                }
        _save_users_raw(users)
        logger.info(f"✅ Миграция завершена: {len(users)} пользователей")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка миграции: {e}")
        return False


# ======================== ОСНОВНЫЕ ФУНКЦИИ ========================

def _load_users_raw() -> dict:
    """Загружает users.json как словарь {id: {...}}"""
    if not os.path.exists(USERS_JSON):
        # Пробуем миграцию
        if _migrate_from_txt_if_needed():
            pass
        else:
            return {}

    if not os.path.exists(USERS_JSON):
        return {}

    try:
        with open(USERS_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"❌ Ошибка чтения users.json: {e}")
        return {}

    if not isinstance(data, dict):
        logger.warning("⚠️ users.json не словарь — сбрасываю")
        return {}

    return data


def _save_users_raw(users: dict) -> bool:
    """Сохраняет users.json"""
    try:
        os.makedirs(os.path.dirname(USERS_JSON), exist_ok=True)
        with open(USERS_JSON, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения users.json: {e}")
        return False


def load_users() -> list:
    """Загружает список пользователей (совместимо со старым кодом)"""
    data = _load_users_raw()
    result = []
    for user_id_str, info in data.items():
        try:
            user_id = int(user_id_str)
        except ValueError:
            continue
        result.append({
            'id': user_id,
            'username': info.get('username', ''),
            'full_name': info.get('full_name', ''),
            'role': info.get('role', '0'),
            'extra': info.get('extra', '-993')
        })
    return result


def save_users(users: list) -> bool:
    """Сохраняет список пользователей"""
    data = {}
    for u in users:
        uid = u.get('id')
        if uid is None:
            continue
        data[str(uid)] = {
            'username': u.get('username', ''),
            'full_name': u.get('full_name', ''),
            'role': u.get('role', '0'),
            'extra': u.get('extra', '-993')
        }
    return _save_users_raw(data)


def add_user(user_id, username, full_name, role='0', extra='-993') -> bool:
    """Добавляет нового пользователя"""
    data = _load_users_raw()
    if str(user_id) in data:
        return False

    data[str(user_id)] = {
        'username': username or '',
        'full_name': full_name or f"User {user_id}",
        'role': role or '0',
        'extra': extra or '-993'
    }
    return _save_users_raw(data)


def remove_user(user_id) -> bool:
    """Удаляет пользователя по ID"""
    data = _load_users_raw()
    if str(user_id) in data:
        del data[str(user_id)]
        _save_users_raw(data)
        logger.info(f"🗑️ Пользователь {user_id} удалён из users.json")
        return True
    return False


def get_users_count() -> int:
    return len(_load_users_raw())


def get_user_by_id(user_id):
    """Ищет пользователя по ID"""
    data = _load_users_raw()
    info = data.get(str(user_id))
    if not info:
        return None
    return {
        'id': user_id,
        'username': info.get('username', ''),
        'full_name': info.get('full_name', ''),
        'role': info.get('role', '0'),
        'extra': info.get('extra', '-993')
    }


def update_user_role(user_id, new_role) -> bool:
    data = _load_users_raw()
    if str(user_id) in data:
        data[str(user_id)]['role'] = new_role
        return _save_users_raw(data)
    return False


def get_user_role(user_id):
    user = get_user_by_id(user_id)
    if user:
        return user.get('role', '0')
    return None


def get_users_by_role(role_key) -> list:
    return [u for u in load_users() if u.get('role') == role_key]


def get_role_stats() -> dict:
    """Статистика по ролям {роль: количество}"""
    stats = {}
    for u in load_users():
        role = u.get('role', '0')
        stats[role] = stats.get(role, 0) + 1
    return stats


def get_role_names() -> list:
    return list(set(u.get('role', '0') for u in load_users()))


def get_user_info(user_id: int) -> dict:
    """Возвращает информацию о пользователе"""
    try:
        user = get_user_by_id(user_id)
        if user:
            return {
                'user_id': user_id,
                'username': user.get('username', ''),
                'full_name': user.get('full_name', ''),
                'role': user.get('role', '')
            }
        return {
            'user_id': user_id,
            'username': '',
            'full_name': '',
            'role': ''
        }
    except Exception as e:
        logger.error(f"Ошибка получения информации о пользователе {user_id}: {e}")
        return {
            'user_id': user_id,
            'username': '',
            'full_name': '',
            'role': ''
        }


# ======================== СИСТЕМА ОТВИЗКИ ОТ КАЛОВ ========================

def ensure_unsubscribed_file():
    os.makedirs(os.path.dirname(UNSUBSCRIBED_FILE), exist_ok=True)
    if not os.path.exists(UNSUBSCRIBED_FILE):
        with open(UNSUBSCRIBED_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)


def load_unsubscribed() -> list:
    ensure_unsubscribed_file()
    try:
        with open(UNSUBSCRIBED_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_unsubscribed(unsubscribed_list):
    ensure_unsubscribed_file()
    with open(UNSUBSCRIBED_FILE, 'w', encoding='utf-8') as f:
        json.dump(unsubscribed_list, f, indent=4)


def add_unsubscribed(user_id) -> bool:
    unsubscribed = load_unsubscribed()
    if user_id not in unsubscribed:
        unsubscribed.append(user_id)
        save_unsubscribed(unsubscribed)
        return True
    return False


def remove_unsubscribed(user_id) -> bool:
    unsubscribed = load_unsubscribed()
    if user_id in unsubscribed:
        unsubscribed.remove(user_id)
        save_unsubscribed(unsubscribed)
        return True
    return False


def is_unsubscribed(user_id) -> bool:
    return user_id in load_unsubscribed()