import os
import sys
import json
import logging

# ⚠️ Добавляем папку src в путь, чтобы импорты работали
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config import DATA_DIR
from utils.role_utils import load_roles_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USERS_FILE = os.path.join(DATA_DIR, 'users', 'users.json')



def migrate():
    if not os.path.exists(USERS_FILE):
        logger.error(f"Файл {USERS_FILE} не найден")
        return

    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        users = json.load(f)

    status_data = load_roles_status()
    changes = 0

    for uid_str, info in users.items():
        if not isinstance(info, dict):
            continue
        uid = int(uid_str)

        # Ищем роль в roles_status.json
        role_key = None
        for key, r_info in status_data.items():
            if isinstance(r_info, dict) and r_info.get('owner_id') == uid:
                role_key = key
                break

        if role_key:
            # Роль есть — ставим флаги и записываем роль
            from utils.role_utils import format_role_display
            role_name = format_role_display(role_key)
            if info.get('role') != role_name:
                info['role'] = role_name
                changes += 1
            if not info.get('is_fully_registered', False):
                info['is_fully_registered'] = True
                changes += 1
            if not info.get('apply_sent', False):
                info['apply_sent'] = True
                changes += 1
            logger.info(f"✅ Юзер {uid} обновлён: роль={role_name}, is_fully_registered=True, apply_sent=True")
        else:
            # Роли нет — оставляем как есть, но проверяем agreed_to_privacy
            if info.get('agreed_to_privacy', False):
                # Если согласился, но нет роли — не трогаем is_fully_registered
                pass
            logger.info(f"ℹ️ Юзер {uid} без роли — пропущен")

    if changes > 0:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        logger.info(f"🔄 Миграция завершена: {changes} изменений")
    else:
        logger.info("✅ Миграция не требуется (все данные актуальны)")

if __name__ == "__main__":
    migrate()