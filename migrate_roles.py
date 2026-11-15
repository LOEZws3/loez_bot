import json
import os
import shutil
import datetime
from pathlib import Path

# Пути
BASE_DIR = Path(__file__).parent.resolve()
USERS_FILE = BASE_DIR / 'data' / 'users' / 'users.json'

# Словарь с дефолтными значениями для КАЖДОГО юзера
DEFAULT_USER_FIELDS = {
    "username": "",
    "full_name": "",
    "role": "",
    "extra": "",
    "changes_count": 0,
    "birthday": None,
    "notify_norm": True,
    "grace_until": None,
    "rest": False,
    "rest_end_date": None,
    "agreed_to_privacy": False,
    "is_fully_registered": False,
    "apply_sent": False, # По дефолту False, но ниже мы это перезапишем
    "invite_link": None,
    "invite_expire": None,
    "rating": 50  # 🚀 НОВОЕ ПОЛЕ: от 0 до 100 (дефолт 50)
}

def migrate_users():
    if not USERS_FILE.exists():
        print(f"❌ Файл {USERS_FILE} не найден!")
        return

    print(f"🔄 Начинаем миграцию пользователей из {USERS_FILE}...")

    # Читаем текущие данные
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        users = json.load(f)

    updated_count = 0
    apply_sent_fixed = 0

    # Проходим по каждому юзеру
    for user_id, user_data in users.items():
        changed = False
        
        # 🚀 СРОЧНЫЙ ФИКС: Если есть роль, значит юзер уже принят -> apply_sent = True
        role = user_data.get("role")
        if role and role not in ["", "0", "None", None]:
            if not user_data.get("apply_sent"):
                user_data["apply_sent"] = True
                apply_sent_fixed += 1
                changed = True

        # Добиваем остальные дефолтные поля
        for key, default_value in DEFAULT_USER_FIELDS.items():
            if key not in user_data:
                user_data[key] = default_value
                changed = True
        
        if changed:
            updated_count += 1

    # Атомарная запись (tmp + os.replace + .bak)
    tmp_file = str(USERS_FILE) + '.tmp'
    bak_file = str(USERS_FILE) + f'.bak_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}'

    try:
        # Делаем бэкап
        shutil.copy2(USERS_FILE, bak_file)
        
        # Пишем в tmp
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
            
        # Заменяем оригинал
        os.replace(tmp_file, USERS_FILE)
        
        print(f"✅ Миграция завершена!")
        print(f"👥 Всего обновлено юзеров: {updated_count}")
        print(f"🔧 Исправлено apply_sent (были с ролью, но без флага): {apply_sent_fixed}")
        print(f"📦 Бэкап сохранен: {bak_file}")
    except Exception as e:
        print(f"❌ Ошибка при записи: {e}")
        if os.path.exists(tmp_file):
            os.remove(tmp_file)

if __name__ == "__main__":
    migrate_users()