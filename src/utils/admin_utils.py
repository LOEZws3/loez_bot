import os
import json
import logging
from typing import List, Dict, Optional

from config import DATA_DIR

logger = logging.getLogger(__name__)

# ======================== ПУТИ ========================

ADMINS_JSON = os.path.join(DATA_DIR, 'admins', 'admins.json')
ADMINS_TXT_LEGACY = os.path.join(DATA_DIR, 'admins', 'admins.txt')
OWNER_ID = 8076284478


# ======================== МИГРАЦИЯ ========================

def _migrate_from_txt_if_needed() -> bool:
    """Конвертирует admins.txt → admins.json"""
    if not os.path.exists(ADMINS_TXT_LEGACY):
        return False
    if os.path.exists(ADMINS_JSON):
        return False

    logger.info("🔄 Миграция admins.txt → admins.json...")
    admins = {}
    try:
        with open(ADMINS_TXT_LEGACY, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split('|', maxsplit=3)
                if len(parts) < 4:
                    continue
                try:
                    admin_id = int(parts[0])
                except ValueError:
                    continue
                admins[str(admin_id)] = {
                    'username': parts[1] if len(parts) > 1 else '',
                    'full_name': parts[2] if len(parts) > 2 else '',
                    'rank': int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 2
                }
        _save_admins_raw(admins)
        logger.info(f"✅ Миграция завершена: {len(admins)} админов")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка миграции: {e}")
        return False


# ======================== ОСНОВНЫЕ ========================

def _load_admins_raw() -> dict:
    if not os.path.exists(ADMINS_JSON):
        _migrate_from_txt_if_needed()

    if not os.path.exists(ADMINS_JSON):
        return {}

    try:
        with open(ADMINS_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"❌ Ошибка чтения admins.json: {e}")
        return {}

    if not isinstance(data, dict):
        return {}

    return data


def _save_admins_raw(admins: dict) -> bool:
    try:
        os.makedirs(os.path.dirname(ADMINS_JSON), exist_ok=True)
        with open(ADMINS_JSON, 'w', encoding='utf-8') as f:
            json.dump(admins, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения admins.json: {e}")
        return False


def load_admins() -> List[Dict]:
    """Загружает список администраторов"""
    data = _load_admins_raw()
    result = []
    for admin_id_str, info in data.items():
        try:
            admin_id = int(admin_id_str)
        except ValueError:
            continue
        result.append({
            'id': admin_id,
            'username': info.get('username', ''),
            'full_name': info.get('full_name', ''),
            'rank': info.get('rank', 2)
        })
    return result


def save_admins(admins: List[Dict]) -> bool:
    data = {}
    for a in admins:
        aid = a.get('id')
        if aid is None:
            continue
        data[str(aid)] = {
            'username': a.get('username', ''),
            'full_name': a.get('full_name', ''),
            'rank': a.get('rank', 2)
        }
    return _save_admins_raw(data)


def is_admin(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    return str(user_id) in _load_admins_raw()


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def get_admin_rank(user_id: int) -> int:
    if user_id == OWNER_ID:
        return 1
    data = _load_admins_raw()
    info = data.get(str(user_id))
    if info:
        return info.get('rank', 2)
    return 0


def add_admin(user_id: int, username: str = None, full_name: str = None, rank: int = 2) -> bool:
    if is_admin(user_id):
        return False

    data = _load_admins_raw()
    data[str(user_id)] = {
        'username': username or '',
        'full_name': full_name or f"User {user_id}",
        'rank': rank
    }
    return _save_admins_raw(data)


def remove_admin(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return False
    data = _load_admins_raw()
    if str(user_id) in data:
        del data[str(user_id)]
        return _save_admins_raw(data)
    return False


def set_rank(user_id: int, rank: int) -> bool:
    if user_id == OWNER_ID:
        return False
    data = _load_admins_raw()
    if str(user_id) in data:
        data[str(user_id)]['rank'] = rank
        return _save_admins_raw(data)
    return False


def get_admin_info(user_id: int) -> Optional[Dict]:
    data = _load_admins_raw()
    info = data.get(str(user_id))
    if not info:
        return None
    return {
        'id': user_id,
        'username': info.get('username', ''),
        'full_name': info.get('full_name', ''),
        'rank': info.get('rank', 2)
    }