"""
Утилиты для работы с заявками
"""

import json
import os
from config import REQUESTS_FILE
from utils.file_utils import ensure_dirs
from .user_utils import add_user
from .role_utils import update_role_status


def load_requests():
    """Загружает список заявок из JSON файла"""
    ensure_dirs()
    if not os.path.exists(REQUESTS_FILE):
        return []
    try:
        with open(REQUESTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_requests(requests):
    """Сохраняет список заявок в JSON файл"""
    ensure_dirs()
    with open(REQUESTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(requests, f, ensure_ascii=False, indent=2)


def add_request(user_id, username, full_name, role, position):
    """
    Добавляет новую заявку (только одна активная заявка)
    role - роль (например, "Глен")
    position - должность (Участник, Модер, Админ)
    """
    if user_id is None:
        return False

    # Проверяем, есть ли уже активная заявка у пользователя
    requests = load_requests()
    for req in requests:
        if req.get('user_id') == user_id and req.get('status') == 'pending':
            return False  # Уже есть активная заявка

    role_index = {
        'Участник': '0',
        'Модер': '1',
        'Админ': '4'
    }.get(position, '0')

    requests.append({
        'user_id': user_id,
        'username': username,
        'full_name': full_name or "Неизвестный",
        'role': role,
        'position': position,
        'role_index': role_index,
        'status': 'pending'
    })
    save_requests(requests)
    return True


def get_pending_requests():
    """Возвращает список непроверенных заявок"""
    return [r for r in load_requests() if r.get('status') == 'pending']


def get_request_by_user_id(user_id):
    """Возвращает заявку пользователя"""
    if user_id is None:
        return None
    requests = load_requests()
    for r in requests:
        if r.get('user_id') == user_id:
            return r
    return None


def approve_request(user_id):
    """Одобряет заявку и УДАЛЯЕТ её из списка"""
    requests = load_requests()
    for i, r in enumerate(requests):
        if r.get('user_id') == user_id and r.get('status') == 'pending':
            # Добавляем пользователя в список участников
            add_user(
                user_id=r.get('user_id'),
                username=r.get('username'),
                full_name=r.get('full_name'),
                role=r.get('role_index', '0')
            )
            # Удаляем заявку
            del requests[i]
            save_requests(requests)
            return True
    return False


def reject_request(user_id):
    """Отклоняет заявку и УДАЛЯЕТ её из списка"""
    requests = load_requests()
    for i, r in enumerate(requests):
        if r.get('user_id') == user_id and r.get('status') == 'pending':
            # Освобождаем роль
            role_name = r.get('role')
            if role_name:
                update_role_status(role_name, 'свободна', None, None)
            # Удаляем заявку
            del requests[i]
            save_requests(requests)
            return True
    return False


def get_requests_count():
    """Возвращает количество заявок"""
    return len(load_requests())


def get_pending_count():
    """Возвращает количество непроверенных заявок"""
    return len(get_pending_requests())