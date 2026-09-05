import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# ТОКЕН БОТА
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ============================================================
# ID ВЛАДЕЛЬЦА (ВАШ)
# ============================================================
OWNER_ID = 8076284478

# ============================================================
# ID ЧАТОВ
# ============================================================
GENERAL_CHAT_ID = int(os.getenv("GENERAL_CHAT_ID", -1001234567890))
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", -1001234567890))

# ============================================================
# ПАРОЛИ
# ============================================================
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
USER_PASSWORD = os.getenv("USER_PASSWORD", "user123")

# ============================================================
# ССЫЛКИ
# ============================================================
CHAT_INVITE_LINK = os.getenv("CHAT_INVITE_LINK", "https://t.me/your_chat")
MODERATOR_LINK = os.getenv("MODERATOR_LINK", "https://t.me/mod")
ADMIN_LINK = os.getenv("ADMIN_LINK", "https://t.me/admin")

# ============================================================
# БАЗОВЫЕ ПУТИ
# ============================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

# ============================================================
# ПУТИ К ФАЙЛАМ (ВСЕ)
# ============================================================

# --- Администраторы ---
ADMINS_FILE = os.path.join(DATA_DIR, "admins", "admins.txt")

# --- Пользователи ---
USERS_FILE = os.path.join(DATA_DIR, "users", "users.txt")
UNSUBSCRIBED_FILE = os.path.join(DATA_DIR, "users", "unsubscribed_calls.txt")

# --- Система ---
CREATION_FILE = os.path.join(DATA_DIR, "system", "creation_date.txt")
FORWARD_FILE = os.path.join(DATA_DIR, "system", "forward.txt")
REQUESTS_FILE = os.path.join(DATA_DIR, "system", "requests.json")
SYSTEM_SETTINGS_FILE = os.path.join(DATA_DIR, "system_settings.json")

# --- Роли (ВАЖНО!) ---
ROLES_DIR = os.path.join(DATA_DIR, "roles")                # <-- Папка с файлами ролей
ROLES_FILE = os.path.join(DATA_DIR, "roles_status.json")   # <-- Основной файл статусов
ROLES_STATUS_FILE = ROLES_FILE                             # <-- Алиас для обратной совместимости

# --- Заявки на рест ---
REST_REQUESTS_FILE = os.path.join(DATA_DIR, "requests", "rest_requests.json")

# --- История пользователей ---
USERS_HISTORY_DIR = os.path.join(DATA_DIR, "users_history")

# ============================================================
# НАСТРОЙКИ ПРОКСИ
# ============================================================
USE_PROXY = os.getenv("USE_PROXY", "True").lower() == "true"
PROXY_DIR = os.getenv("PROXY_DIR", "../proxy_manadger")
# ============================================================
# НАСТРОЙКИ ИНТЕРФЕЙСА
# ============================================================
ROLES_PER_PAGE = 10  # Количество ролей на одной странице
# ============================================================
# РЕЗЕРВНЫЙ СПИСОК ПРОВЕРЕННЫХ ПРОКСИ (РАБОТАЮТ С TELEGRAM)
# ============================================================
# Эти прокси проверены вручную и работают с Telegram API.
# Используются как резерв, если good_proxies.txt пуст или недоступен.
# Формат: ip:port или socks5://ip:port

BACKUP_PROXIES = [
   " 103.135.189.193:83"
    # Добавляйте новые проверенные прокси сюда
    # "ip:port",
]