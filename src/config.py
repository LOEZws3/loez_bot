import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

# Исправлено: убраны пробелы
ADMINS_FILE = DATA_DIR / "admins" / "admins.txt"
USERS_FILE = DATA_DIR / "users" / "users.txt"
CREATION_FILE = DATA_DIR / "system" / "creation_date.txt"
FORWARD_FILE = DATA_DIR / "system" / "forward_map.json"
REQUESTS_FILE = DATA_DIR / "system" / "requests.json"
HISTORY_DIR = DATA_DIR / "users_history"

ROLES_DIR = DATA_DIR / "roles"
ROLES_STATUS_FILE = DATA_DIR / "roles_status.json"

ADMIN_PASSWORD = "cold shine"
USER_PASSWORD = "errorr"
OWNER_ID = None
CHAT_INVITE_LINK = "https://t.me/+8Y8VGr_J2qBkMjcy"
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_GROUP_ID = -1004426618768
GENERAL_CHAT_ID = -1003761245669
MODERATOR_LINK = "https://example.com/moderator_link"
ADMIN_LINK = "https://example.com/admin_link"
ROLES_PER_PAGE = 10