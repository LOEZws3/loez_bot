import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Убедитесь, что путь к файлу settings правильный
# SETTINGS_FILE = Path(__file__).parent / ".." / ".." / "data" / "system_settings.json" # Если utils внутри src
SETTINGS_FILE = Path(__file__).parent.parent.parent / "data" / "system_settings.json" # Абсолютный путь от utils

def ensure_settings_file():
    """Создаёт файл настроек с значениями по умолчанию, если он не существует."""
    default_settings = {
        "reminders_enabled": True
    }
    if not SETTINGS_FILE.exists():
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        save_settings(default_settings)
        logger.info(f"📁 Файл настроек {SETTINGS_FILE} создан с настройками по умолчанию.")
    else:
        logger.info(f"📁 Файл настроек {SETTINGS_FILE} уже существует.")

def load_settings():
    """Загружает настройки из JSON-файла."""
    ensure_settings_file()
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            # Убедимся, что все ключи существуют
            if "reminders_enabled" not in settings:
                settings["reminders_enabled"] = True
                save_settings(settings)
                logger.warning("🔧 Ключ 'reminders_enabled' добавлен в файл настроек.")
            return settings
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"❌ Ошибка чтения файла настроек: {e}. Использую настройки по умолчанию.")
        return {"reminders_enabled": True}


def save_settings(settings):
    """Сохраняет настройки в JSON-файл."""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
        logger.info(f"💾 Настройки сохранены в {SETTINGS_FILE}")
    except Exception as e:
        logger.error(f"❌ Ошибка записи файла настроек: {e}")


def is_reminders_enabled():
    """Возвращает True, если напоминания включены."""
    settings = load_settings()
    return settings.get("reminders_enabled", True)

def toggle_reminders():
    """Переключает состояние напоминаний."""
    settings = load_settings()
    current_state = settings.get("reminders_enabled", True)
    new_state = not current_state
    settings["reminders_enabled"] = new_state
    save_settings(settings)
    logger.info(f"🔄 Состояние напоминаний изменено на: {'Включены' if new_state else 'Выключены'}")
    return new_state
