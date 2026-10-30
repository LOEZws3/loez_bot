"""
Утилиты для работы с заявками (СЛОВАРЬ {})
Использует атомарную запись из parsers.py.
"""

import os
import logging
from config import REQUESTS_FILE
from utils.parsers import load_json, save_json

logger = logging.getLogger(__name__)

def load_requests() -> dict:
    """Загружает заявки из JSON (словарь {id: {...}})"""
    data = load_json(REQUESTS_FILE, {})
    if not isinstance(data, dict):
        return {}
    return data

def save_requests(requests: dict) -> bool:
    """Сохраняет заявки в JSON (атомарно)"""
    return save_json(REQUESTS_FILE, requests)

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
    return save_requests(requests)

def get_pending_requests() -> list:
    """Возвращает список (id, request) с status='pending'"""
    requests = load_requests()
    result = []
    for req_id, req in requests.items():
        if isinstance(req, dict) and req.get('status') == 'pending':
            result.append((req_id, req))
    return result

def get_request_by_user_id(user_id):
    """Возвращает активную (pending) заявку пользователя"""
    if user_id is None:
        return None
    requests = load_requests()
    for req_id, req in requests.items():
        if isinstance(req, dict) and req.get('user_id') == user_id and req.get('status') == 'pending':
            return req
    return None

def get_requests_count() -> int:
    return len(load_requests())

def get_pending_count() -> int:
    return len(get_pending_requests())