"""
Обёртка над parsers.py для обратной совместимости.
Все данные читаются/пишутся через parsers.
Логика рангов: ТОЛЬКО из admins.json + OWNER_ID из .env.
"""

import logging
from utils import parsers

logger = logging.getLogger(__name__)


def load_admins() -> list:
    """Совместимость: возвращает list"""
    data = parsers.load_admins()
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
            'rank': int(info.get('rank', 2)),
        })
    return result


def save_admins(admins: list) -> bool:
    data = {}
    for a in admins:
        aid = a.get('id')
        if aid is None:
            continue
        data[str(aid)] = {
            'username': a.get('username', ''),
            'full_name': a.get('full_name', ''),
            'rank': int(a.get('rank', 2)),
        }
    return parsers.save_admins(data)


def is_admin(user_id: int) -> bool:
    return parsers.is_admin(user_id)


def is_owner(user_id: int) -> bool:
    return parsers.is_owner(user_id)


def get_owner_ids() -> list:
    return parsers.get_owner_ids()


def get_admin_rank(user_id: int) -> int:
    return parsers.get_admin_rank(user_id)


def add_admin(user_id, username=None, full_name=None, rank=2) -> bool:
    return parsers.add_admin(user_id, username or '', full_name or '', rank)


def remove_admin(user_id) -> bool:
    return parsers.remove_admin(user_id)


def set_rank(user_id, rank) -> bool:
    return parsers.set_rank(user_id, rank)


def get_admin_info(user_id):
    return parsers.get_admin(user_id)