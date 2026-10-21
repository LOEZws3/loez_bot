import json
import os
import logging
from config import SYSTEM_SETTINGS_FILE

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = {
    'closed_mode': False,
    'reminder_enabled': True,
    'max_rest_days': 14,
    'call_cooldown': 20,
    'callfal_cooldown': 30,
    'welcome_enabled': True,
    'auto_rest_removal': True,
    'forward_enabled': False,
    'anonymous_mode': False,
    'max_role_changes': 3,
    'messages_norm': 70,
    'messages_norm_low': 10,
    'warns_accumulate': False,
    'warns_to_ban': 3,
    'warn_notify_admin': True,
    'checknorm_time_window_enabled': True,
    'require_profile_completeness': True, # ⚠️ НОВОЕ
}

def load_settings() -> dict:
    if not os.path.exists(SYSTEM_SETTINGS_FILE):
        return DEFAULT_SETTINGS.copy()
    try:
        with open(SYSTEM_SETTINGS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return DEFAULT_SETTINGS.copy()
        
        # Нормализация: если новых ключей нет, добавляем
        for key, value in DEFAULT_SETTINGS.items():
            if key not in data:
                data[key] = value
        return data
    except Exception as e:
        logger.error(f"Ошибка загрузки настроек: {e}")
        return DEFAULT_SETTINGS.copy()

def save_settings(settings: dict) -> bool:
    try:
        with open(SYSTEM_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения настроек: {e}")
        return False

def reset_settings() -> bool:
    return save_settings(DEFAULT_SETTINGS.copy())