import os
from pathlib import Path

# Пути
# Исправлено: __file__ вместо file
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

# Исправлено: убраны лишние пробелы в названиях папок и файлов
ADMINS_FILE = DATA_DIR / "admins" / "admins.txt"
USERS_FILE = DATA_DIR / "users" / "users.txt"
CREATION_FILE = DATA_DIR / "system" / "creation_date.txt"
FORWARD_FILE = DATA_DIR / "system" / "forward_map.json"
REQUESTS_FILE = DATA_DIR / "system" / "requests.json"
HISTORY_DIR = DATA_DIR / "users_history"

# === НОВЫЕ ПУТИ ДЛЯ РОЛЕЙ ===
ROLES_DIR = DATA_DIR / "roles"
ROLES_STATUS_FILE = DATA_DIR / "roles_status.json"

# Пароли
ADMIN_PASSWORD = "cold shine"
USER_PASSWORD = "errorr"

# ID владельца
OWNER_ID = None

# === ССЫЛКА НА ЧАТ ===
CHAT_INVITE_LINK = "https://t.me/+8Y8VGr_J2qBkMjcy"

# Токен
BOT_TOKEN = os.getenv("BOT_TOKEN")

# === ID ГРУПП ===
ADMIN_GROUP_ID = -1004426618768  # Группа для админов (пересылка сообщений)
GENERAL_CHAT_ID = -1003761245669  # Флуд-чат (ЗАМЕНИТЕ НА РЕАЛЬНЫЙ ID)

# === ССЫЛКИ ===
MODERATOR_LINK = "https://example.com/moderator_link"
ADMIN_LINK = "https://example.com/admin_link"

# Количество ролей на одной странице
ROLES_PER_PAGE = 10