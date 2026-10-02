"""
Централизованный модуль для работы с настройками бота.
Единственный источник истины для system_settings.json.
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

    # Нормы и чистка
    "messages_norm": 70,
    "messages_norm_low": 10,
    "warns_accumulate": False,
    "warns_to_ban": 3,
    "warn_notify_admin": True,
    "norm_auto_message_enabled": True,

    # Окно чистки (БАГ 9, 02.10.2026)
    # ВКЛ → /checknorm только с 20:00 до 21:00 МСК
    # ВЫКЛ → без ограничений
    "checknorm_time_window_enabled": True,
}

# ======================== ЗАГРУЗКА / СОХРАНЕНИЕ ========================

def load_settings() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Ошибка чтения настроек: {e}")
        return dict(DEFAULT_SETTINGS)

    if not isinstance(data, dict):
        return dict(DEFAULT_SETTINGS)

    changed = False
    for key, default_value in DEFAULT_SETTINGS.items():
        if key not in data:
            data[key] = default_value
            changed = True

    if changed:
        save_settings(data)

    return data

def save_settings(settings: dict) -> bool:
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
    settings = load_settings()
    if default is None:
        default = DEFAULT_SETTINGS.get(key)
    return settings.get(key, default)

def set_setting(key: str, value) -> bool:
    settings = load_settings()
    settings[key] = value
    return save_settings(settings)

def toggle_setting(key: str) -> bool:
    settings = load_settings()
    current = bool(settings.get(key, DEFAULT_SETTINGS.get(key, False)))
    new_value = not current
    settings[key] = new_value
    save_settings(settings)
    return new_value

def reset_settings() -> bool:
    return save_settings(dict(DEFAULT_SETTINGS))

# ======================== ОБЁРТКИ ========================

def get_messages_norm() -> int:
    return int(get_setting('messages_norm', 70))

def get_messages_norm_low() -> int:
    return int(get_setting('messages_norm_low', 10))

def get_max_role_changes() -> int:
    return int(get_setting('max_role_changes', 1))

def get_warns_accumulate() -> bool:
    return bool(get_setting('warns_accumulate', False))

def get_warns_to_ban() -> int:
    return int(get_setting('warns_to_ban', 3))

def get_warn_notify_admin() -> bool:
    return bool(get_setting('warn_notify_admin', True))

def get_checknorm_time_window_enabled() -> bool:
    """БАГ 9: ограничение времени запуска /checknorm."""
    return bool(get_setting('checknorm_time_window_enabled', True))