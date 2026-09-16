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