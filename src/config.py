import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# --- Базовые пути ---
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = os.path.join(BASE_DIR, 'data')
DATA_PATH = DATA_DIR  # Добавлено для совместимости с chat_member.py
SRC_PATH = Path(__file__).parent

# --- Токены и ID (из .env) ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
OWNER_ID = int(os.getenv('OWNER_ID', 0))
GENERAL_CHAT_ID = int(os.getenv('GENERAL_CHAT_ID', 0))

# --- ID чатов и ссылки (значения по умолчанию) ---
ADMIN_GROUP_ID = int(os.getenv('ADMIN_GROUP_ID', 0))
CHAT_INVITE_LINK = os.getenv('CHAT_INVITE_LINK', 'https://t.me/joinchat/your_chat_link')
ROLES_PER_PAGE = int(os.getenv('ROLES_PER_PAGE', 5))

# --- Настройки прокси ---
USE_PROXY = os.getenv('USE_PROXY', 'false').lower() == 'true'
PROXY_DIR = os.getenv('PROXY_DIR', os.path.join(SRC_PATH, 'proxies'))
PROXY_ENABLED = USE_PROXY

# --- Остальные настройки ---
DATABASE_PATH = os.getenv('DATABASE_PATH', os.path.join(SRC_PATH, 'bot.db'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE_PATH = os.getenv('LOG_FILE_PATH', os.path.join(SRC_PATH, 'logs', 'bot.log'))
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# --- Пути к файлам данных ---
ADMINS_FILE = os.path.join(DATA_DIR, 'admins', 'admins.txt')
USERS_FILE = os.path.join(DATA_DIR, 'users', 'users.txt')
CREATION_FILE = os.path.join(DATA_DIR, 'system', 'creation_date.txt')
FORWARD_FILE = os.path.join(DATA_DIR, 'system', 'forward_map.json')
REQUESTS_FILE = os.path.join(DATA_DIR, 'system', 'requests.json')
ROLES_STATUS_FILE = os.path.join(DATA_DIR, 'roles_status.json')
SYSTEM_SETTINGS_FILE = os.path.join(DATA_DIR, 'system_settings.json')
ROLES_DIR = os.path.join(DATA_DIR, 'roles')
USERS_HISTORY_DIR = os.path.join(DATA_DIR, 'users_history')

# --- Проверка обязательных переменных ---
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env файле!")

if not GENERAL_CHAT_ID:
    print("⚠️ ВНИМАНИЕ: GENERAL_CHAT_ID не задан в .env файле!")

# --- Создание папок ---
def ensure_directories():
    directories = [
        DATA_DIR,
        os.path.join(DATA_DIR, 'users'),
        os.path.join(DATA_DIR, 'admins'),
        os.path.join(DATA_DIR, 'roles'),
        os.path.join(DATA_DIR, 'system'),
        os.path.join(DATA_DIR, 'users_history'),
        os.path.join(SRC_PATH, 'logs'),
        PROXY_DIR,
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"📁 Создана папка: {directory}")

ensure_directories()

# --- Экспорт для других модулей ---
__all__ = [
    'BOT_TOKEN',
    'OWNER_ID',
    'GENERAL_CHAT_ID',
    'ADMIN_GROUP_ID',
    'CHAT_INVITE_LINK',
    'ROLES_PER_PAGE',
    'USE_PROXY',
    'PROXY_DIR',
    'PROXY_ENABLED',
    'DATA_DIR',
    'DATA_PATH',  # Добавлено для chat_member.py
    'SRC_PATH',
    'DATABASE_PATH',
    'LOG_LEVEL',
    'LOG_FILE_PATH',
    'LOG_FORMAT',
    'ADMINS_FILE',
    'USERS_FILE',
    'CREATION_FILE',
    'FORWARD_FILE',
    'REQUESTS_FILE',
    'ROLES_STATUS_FILE',
    'SYSTEM_SETTINGS_FILE',
    'ROLES_DIR',
    'USERS_HISTORY_DIR',
    'ensure_directories',
]