"""
Централизованный модуль для работы с настройками бота.
Единственный источник истины для system_settings.json.

Все остальные модули должны использовать эти функции,
а не читать файл напрямую.
"""

import os
import json
import logging

from config import DATA_DIR

logger = logging.getLogger(__name__)

SETTINGS_FILE = os.path.join(DATA_DIR, 'system', 'system_settings.json')


# ======================== ДЕФОЛТНЫЕ НАСТРОЙКИ ========================

DEFAULT_SETTINGS = {
    # Существующие
    "closed_mode": False,
    "reminder_enabled": True,
    "welcome_enabled": True,
    "auto_rest_removal": True,
    "call_cooldown": 20,
    "callfal_cooldown": 30,
    "max_rest_days": 14,
    "max_role_changes": 1,

    # Прочие
    "forward_enabled": False,
    "anonymous_mode": False,

    # НОВОЕ (Подшаг 2.1)
    "messages_norm": 70,  # Норма сообщений в неделю

    # НОВОЕ (Подшаг 2.3, будет использоваться позже)
    "norm_auto_message_enabled": True,  # Авто-сообщение юзеру при наборе нормы
}


# ======================== ЗАГРУЗКА / СОХРАНЕНИЕ ========================

def load_settings() -> dict:
    """
    Загружает настройки.
    Если каких-то ключей нет — добавляет их из DEFAULT_SETTINGS.
    """
    if not os.path.exists(SETTINGS_FILE):
        return dict(DEFAULT_SETTINGS)

    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Ошибка чтения настроек: {e}. Использую дефолтные.")
        return dict(DEFAULT_SETTINGS)

    if not isinstance(data, dict):
        return dict(DEFAULT_SETTINGS)

    # Дополняем недостающие ключи
    changed = False
    for key, default_value in DEFAULT_SETTINGS.items():
        if key not in data:
            data[key] = default_value
            changed = True

    if changed:
        save_settings(data)

    return data


def save_settings(settings: dict) -> bool:
    """Сохраняет настройки."""
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения настроек: {e}")
        return False


# ======================== УТИЛИТЫ ========================

def get_setting(key: str, default=None):
    """Возвращает значение настройки по ключу."""
    settings = load_settings()
    if default is None:
        default = DEFAULT_SETTINGS.get(key)
    return settings.get(key, default)


def set_setting(key: str, value) -> bool:
    """Устанавливает значение настройки."""
    settings = load_settings()
    settings[key] = value
    return save_settings(settings)


def toggle_setting(key: str) -> bool:
    """Переключает boolean-настройку. Возвращает новое значение."""
    settings = load_settings()
    current = bool(settings.get(key, DEFAULT_SETTINGS.get(key, False)))
    new_value = not current
    settings[key] = new_value
    save_settings(settings)
    return new_value


def reset_settings() -> bool:
    """Сбрасывает настройки к дефолтным."""
    return save_settings(dict(DEFAULT_SETTINGS))


# ======================== УДОБНЫЕ ОБЁРТКИ ========================

def get_messages_norm() -> int:
    """Возвращает норму сообщений в неделю."""
    return int(get_setting('messages_norm', 70))


def get_max_role_changes() -> int:
    """Возвращает лимит смен роли."""
    return int(get_setting('max_role_changes', 1))