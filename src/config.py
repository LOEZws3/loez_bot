import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# --- Базовые пути (АБСОЛЮТНЫЕ) ---
BASE_DIR = Path(__file__).parent.parent.resolve()
SRC_PATH = Path(__file__).parent.resolve()
DATA_DIR = str(BASE_DIR / 'data')
DATA_PATH = DATA_DIR

# --- Токены и ID (из .env) ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
OWNER_ID = int(os.getenv('OWNER_ID', 0))
GENERAL_CHAT_ID = int(os.getenv('GENERAL_CHAT_ID', 0))

# --- ID чатов и ссылки ---
ADMIN_GROUP_ID = int(os.getenv('ADMIN_GROUP_ID', 0))
CHAT_INVITE_LINK = os.getenv('CHAT_INVITE_LINK', 'https://t.me/joinchat/your_chat_link')
ROLES_PER_PAGE = int(os.getenv('ROLES_PER_PAGE', 5))

# --- Настройки прокси ---
USE_PROXY = os.getenv('USE_PROXY', 'false').lower() == 'true'
PROXY_DIR = os.getenv('PROXY_DIR', str(SRC_PATH / 'proxies'))
PROXY_ENABLED = USE_PROXY
PRIORITY_PROXY = os.getenv('PRIORITY_PROXY', '')

# --- Логирование ---
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE_PATH = os.getenv('LOG_FILE_PATH', str(Path(DATA_DIR) / 'logs' / 'bot.log'))
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# --- База данных ---
DATABASE_PATH = os.getenv('DATABASE_PATH', str(SRC_PATH / 'bot.db'))

# --- Пути к файлам данных (JSON — ОСНОВНЫЕ) ---
USERS_FILE_JSON = os.path.join(DATA_DIR, 'users', 'users.json')
ADMINS_FILE_JSON = os.path.join(DATA_DIR, 'admins', 'admins.json')

# --- Бэкапы (старые .txt) ---
ADMINS_FILE = os.path.join(DATA_DIR, 'admins', 'admins.txt')
USERS_FILE = os.path.join(DATA_DIR, 'users', 'users.txt')

# --- Системные файлы ---
CREATION_FILE = os.path.join(DATA_DIR, 'system', 'creation_date.txt')
FORWARD_FILE = os.path.join(DATA_DIR, 'system', 'forward_map.json')
REQUESTS_FILE = os.path.join(DATA_DIR, 'system', 'requests.json')
SYSTEM_SETTINGS_FILE = os.path.join(DATA_DIR, 'system', 'system_settings.json')

# --- Роли (ПЕРЕНЕСЕНО В data/roles/) ---
ROLES_STATUS_FILE = os.path.join(DATA_DIR, 'roles', 'roles_status.json')
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
        os.path.join(DATA_DIR, 'logs'),
        PROXY_DIR,
    ]

    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"📁 Создана папка: {directory}")

ensure_directories()

# --- Экспорт для других модулей ---
__all__ = [
    'BOT_TOKEN', 'OWNER_ID', 'GENERAL_CHAT_ID',
    'ADMIN_GROUP_ID', 'CHAT_INVITE_LINK', 'ROLES_PER_PAGE',
    'USE_PROXY', 'PROXY_DIR', 'PROXY_ENABLED', 'PRIORITY_PROXY',
    'DATA_DIR', 'DATA_PATH', 'SRC_PATH', 'DATABASE_PATH',
    'LOG_LEVEL', 'LOG_FILE_PATH', 'LOG_FORMAT',
    'USERS_FILE_JSON', 'ADMINS_FILE_JSON',
    'ADMINS_FILE', 'USERS_FILE',
    'CREATION_FILE', 'FORWARD_FILE',
    'REQUESTS_FILE', 'SYSTEM_SETTINGS_FILE',
    'ROLES_STATUS_FILE', 'ROLES_DIR', 'USERS_HISTORY_DIR',
    'ensure_directories',
]