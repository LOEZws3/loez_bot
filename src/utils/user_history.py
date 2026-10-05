import os
import json
import logging
from config import DATA_DIR

logger = logging.getLogger(__name__)

# Используем os.path.join вместо /
HISTORY_DIR = os.path.join(DATA_DIR, "users_history")

def ensure_history_dir():
    """Создаёт папку для истории, если её нет"""
    if not os.path.exists(HISTORY_DIR):
        os.makedirs(HISTORY_DIR)
        logger.info(f"📁 Создана папка истории: {HISTORY_DIR}")

def load_user_history(user_id: int) -> dict:
    """Загружает историю пользователя"""
    ensure_history_dir()
    file_path = os.path.join(HISTORY_DIR, f"{user_id}.json")

    if not os.path.exists(file_path):
        return {}

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_user_history(user_id: int, data: dict):
    """Сохраняет историю пользователя"""
    ensure_history_dir()
    file_path = os.path.join(HISTORY_DIR, f"{user_id}.json")

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def update_user_history(user_id: int, key: str, value):
    """Обновляет конкретное поле в истории пользователя"""
    history = load_user_history(user_id)
    history[key] = value
    save_user_history(user_id, history)

def get_user_history_field(user_id: int, key: str, default=None):
    """Получает конкретное поле из истории пользователя"""
    history = load_user_history(user_id)
    return history.get(key, default)

# ======================== ⚠️ НОВОЕ: ОБЁРТКИ (05.10.2026) ========================

def set_role(user_id: int, role_id: int = None, role_key: str = None):
    """Сохраняет ID и ключ роли в историю"""
    history = load_user_history(user_id)
    history['role_id'] = role_id
    history['role_key'] = role_key
    save_user_history(user_id, history)

def set_birthday(user_id: int, birthday: str = None):
    """Сохраняет ДР в историю"""
    update_user_history(user_id, 'birthday', birthday)

def set_last_message_at(user_id: int, iso_time: str = None):
    """Сохраняет время последнего сообщения"""
    import datetime
    if iso_time is None:
        iso_time = datetime.datetime.now().isoformat()
    update_user_history(user_id, 'last_message_at', iso_time)

def set_left(user_id: int, reason: str = "left"):
    """Сохраняет дату и причину выхода"""
    import datetime
    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    history = load_user_history(user_id)
    history['last_left'] = now
    history['left_reason'] = reason
    save_user_history(user_id, history)