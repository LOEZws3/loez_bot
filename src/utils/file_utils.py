import os
import json
import logging
from config import DATA_DIR, ADMINS_FILE, USERS_FILE, CREATION_FILE, FORWARD_FILE

logger = logging.getLogger(__name__)


def ensure_dirs():
    """Создаёт все необходимые директории"""
    dirs = [
        DATA_DIR,
        os.path.dirname(ADMINS_FILE),
        os.path.dirname(USERS_FILE),
        os.path.dirname(CREATION_FILE),
        os.path.dirname(FORWARD_FILE),
    ]
    
    for dir_path in dirs:
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"📁 Создана папка: {dir_path}")


def ensure_file(file_path):
    """Создаёт файл, если его нет"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            pass
        logger.info(f"📄 Создан файл: {file_path}")


# ============================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ФАЙЛАМИ
# ============================================================

def load_json(file_path, default=None):
    """Загружает JSON из файла"""
    if not os.path.exists(file_path):
        return default if default is not None else {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return default if default is not None else {}


def save_json(file_path, data):
    """Сохраняет JSON в файл"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_txt(file_path, default=None):
    """Загружает текстовый файл (построчно)"""
    if not os.path.exists(file_path):
        return default if default is not None else []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except (FileNotFoundError):
        return default if default is not None else []


def save_txt(file_path, lines):
    """Сохраняет список строк в текстовый файл"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        for line in lines:
            f.write(f"{line}\n")


def days_since_creation(creation_file=None):
    """Возвращает количество дней с даты создания"""
    if creation_file is None:
        creation_file = CREATION_FILE
    
    if not os.path.exists(creation_file):
        return 0
    
    try:
        with open(creation_file, 'r', encoding='utf-8') as f:
            date_str = f.read().strip()
            from datetime import datetime
            creation_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            return (datetime.now().date() - creation_date).days
    except:
        return 0