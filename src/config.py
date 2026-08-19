import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# БАЗОВЫЕ ПУТИ
# ============================================================
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

# ============================================================
# ФАЙЛЫ ДАННЫХ
# ============================================================
ADMINS_FILE = DATA_DIR / "admins" / "admins.txt"
USERS_FILE = DATA_DIR / "users" / "users.txt"
CREATION_FILE = DATA_DIR / "system" / "creation_date.txt"
FORWARD_FILE = DATA_DIR / "system" / "forward_map.json"
REQUESTS_FILE = DATA_DIR / "system" / "requests.json"
HISTORY_DIR = DATA_DIR / "users_history"

ROLES_DIR = DATA_DIR / "roles"
ROLES_STATUS_FILE = DATA_DIR / "roles_status.json"

# ============================================================
# ОСНОВНЫЕ НАСТРОЙКИ
# ============================================================
# Токен бота (из .env)
BOT_TOKEN = os.getenv("TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ Токен не найден в .env файле!")

# Пароли и ссылки (из старого конфига)
ADMIN_PASSWORD = "cold shine"
USER_PASSWORD = "errorr"
OWNER_ID = None
CHAT_INVITE_LINK = "https://t.me/+8Y8VGr_J2qBkMjcy"
ADMIN_GROUP_ID = -1004426618768
GENERAL_CHAT_ID = -1003761245669
MODERATOR_LINK = "https://example.com/moderator_link"
ADMIN_LINK = "https://example.com/admin_link"
ROLES_PER_PAGE = 10

# ============================================================
# НАСТРОЙКИ ПРОКСИ-МЕНЕДЖЕРА
# ============================================================
PROXY_CONFIG = {
    # Путь к папке с данными прокси
    "DATA_DIR": str(DATA_DIR / "proxies"),

    # Источники прокси (можно добавлять/удалять/менять)
    "SOURCES": [
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/socks5.txt",
        "https://raw.githubusercontent.com/LoneKingCode/free-proxy-db/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/Argh94/Proxy-List/main/socks5.txt",
        "https://raw.githubusercontent.com/hookzof/socks5_list/refs/heads/master/tg/socks.json"
    ],

    # Лимиты и пороги для рейтинговой системы
    "RATING": {
        "WHITELIST_MIN": 70,      # Минимальный рейтинг для whitelist
        "RESERVE_MIN": 100,       # Минимальный рейтинг для reserve
        "QUARANTINE_MIN": -25,    # Рейтинг, при котором прокси уходит в карантин
        "WHITELIST_DECREASE": 10, # На сколько падает рейтинг в whitelist при ошибке
        "SUSPICIOUS_DECREASE": 5, # На сколько падает рейтинг в suspicious при ошибке
        "TEMP_DECREASE": 5,       # На сколько падает рейтинг в temp при ошибке
        "RESERVE_DECREASE": 5,    # На сколько падает рейтинг в reserve при ошибке
        "WHITELIST_INCREASE": 5,  # На сколько растёт рейтинг в whitelist при успехе
        "SUSPICIOUS_INCREASE": 15, # На сколько растёт рейтинг в suspicious при успехе
        "TEMP_INCREASE": 20,       # На сколько растёт рейтинг в temp при успехе
        "RESERVE_INCREASE": 2,    # На сколько растёт рейтинг в reserve при успехе
        "TEMP_START": 85,         # Стартовый рейтинг при перемещении в temp из других списков
        "RESERVE_START": 100,     # Стартовый рейтинг при перемещении в reserve
        "QUARANTINE_DAYS": 3,     # Количество дней в карантине
        "QUARANTINE_START": -10,  # Стартовый рейтинг при выходе из карантина
    },

    # Настройки проверки прокси
    "CHECK": {
        "TIMEOUT": 30,            # Таймаут на проверку прокси (сек)
        "MAX_PROXIES_PER_SOURCE": 900,  # Максимум прокси, добавляемых из одного источника
        "AUTO_UPDATE_INTERVAL": 1800,  # Интервал автоматического обновления (сек)
    },

    # Настройки белого списка (можно добавлять свои прокси)
    "WHITELIST_PROXIES": [
        "socks5://127.0.0.1:3066",
        "socks5://127.0.0.1:1080",
    ]
}

# ============================================================
# НАСТРОЙКИ ДЛЯ ПРОВЕРКИ ПРОКСИ
# ============================================================
PROXY_CHECK_CONFIG = {
    "TIMEOUT": PROXY_CONFIG["CHECK"]["TIMEOUT"],
}

# ============================================================
# НАСТРОЙКИ БОТА
# ============================================================
BOT_CONFIG = {
    "SKIP_UPDATES": True,
}

# ============================================================
# СОВМЕСТИМОСТЬ СО СТАРЫМ КОДОМ
# ============================================================
# Для обратной совместимости (если где-то используется BOT_TOKEN)
TOKEN = BOT_TOKEN