"""
Утилиты для работы с заявками (СЛОВАРЬ {})
"""

import json
import os
from config import REQUESTS_FILE
from utils.file_utils import ensure_dirs
from .user_utils import add_user
from .role_utils import update_role_status


def load_requests() -> dict:
    """Загружает заявки из JSON (словарь {id: {...}})"""
    ensure_dirs()
    if not os.path.exists(REQUESTS_FILE):
        return {}
    try:
        with open(REQUESTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}
    # Защита: если список — конвертируем
    if isinstance(data, list):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def save_requests(requests: dict) -> None:
    """Сохраняет заявки в JSON"""
    ensure_dirs()
    with open(REQUESTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(requests, f, ensure_ascii=False, indent=2)


def add_request(user_id, username, full_name, role, position) -> bool:
    """Добавляет новую заявку (только одна активная)"""
    if user_id is None:
        return False

    requests = load_requests()

    # Проверка: есть ли активная заявка
    for req in requests.values():
        if isinstance(req, dict) and req.get('user_id') == user_id and req.get('status') == 'pending':
            return False

    role_index = {
        'Участник': '0',
        'Модер': '1',
        'Админ': '4'
    }.get(position, '0')

    existing_ids = [int(k) for k in requests.keys() if str(k).isdigit()]
    request_id = max(existing_ids, default=0) + 1

    requests[str(request_id)] = {
        'user_id': user_id,
        'username': username,
        'full_name': full_name or "Неизвестный",
        'role': role,
        'position': position,
        'role_index': role_index,
        'status': 'pending'
    }
    save_requests(requests)
    return True


def get_pending_requests() -> list:
    """Возвращает список (id, request) с status='pending'"""
    requests = load_requests()
    result = []
    for req_id, req in requests.items():
        if isinstance(req, dict) and req.get('status') == 'pending':
            result.append((req_id, req))
    return result


def get_request_by_user_id(user_id):
    """Возвращает активную заявку пользователя"""
    if user_id is None:
        return None
    requests = load_requests()
    for req_id, req in requests.items():
        if isinstance(req, dict) and req.get('user_id') == user_id:
            return req
    return None


def approve_request(user_id) -> bool:
    """Одобряет заявку (по user_id)"""
    requests = load_requests()
    for req_id, req in requests.items():
        if isinstance(req, dict) and req.get('user_id') == user_id and req.get('status') == 'pending':
            add_user(
                user_id=req.get('user_id'),
                username=req.get('username'),
                full_name=req.get('full_name'),
                role=req.get('role_index', '0')
            )
            req['status'] = 'approved'
            save_requests(requests)
            return True
    return False


def reject_request(user_id) -> bool:
    """Отклоняет заявку (по user_id)"""
    requests = load_requests()
    for req_id, req in requests.items():
        if isinstance(req, dict) and req.get('user_id') == user_id and req.get('status') == 'pending':
            req['status'] = 'rejected'
            save_requests(requests)
            return True
    return False


def get_requests_count() -> int:
    return len(load_requests())


def get_pending_count() -> int:
    return len(get_pending_requests())