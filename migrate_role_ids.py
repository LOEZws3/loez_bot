#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт миграции: присвоение уникальных ID всем ролям.
Запускается ОДИН РАЗ.

Что делает:
1. Читает data/roles/roles_status.json
2. Для каждой роли без поля "id" — присваивает следующий ID (1, 2, 3, ...)
3. Создаёт пустой data/system/free_role_ids.json
4. Бэкап старого roles_status.json

Запуск: python migrate_role_ids.py
"""

import os
import sys
import io
import json
import shutil
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    roles_file = os.path.join(base_dir, 'data', 'roles', 'roles_status.json')
    free_ids_file = os.path.join(base_dir, 'data', 'system', 'free_role_ids.json')

    if not os.path.exists(roles_file):
        print(f"❌ Файл {roles_file} не найден!")
        return

    # Загружаем
    with open(roles_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, dict):
        print("❌ roles_status.json — не словарь!")
        return

    # Бэкап
    backup = roles_file + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(roles_file, backup)
    print(f"💾 Бэкап: {os.path.basename(backup)}")

    # Считаем существующие ID
    existing_ids = set()
    for role_key, info in data.items():
        if isinstance(info, dict):
            rid = info.get('id')
            if isinstance(rid, int) and rid > 0:
                existing_ids.add(rid)

    print(f"📊 Ролей: {len(data)}")
    print(f"📊 Уже с ID: {len(existing_ids)}")
    print(f"📊 Без ID: {len(data) - len(existing_ids)}")

    # Присваиваем ID
    next_id = max(existing_ids) + 1 if existing_ids else 1
    assigned = 0

    for role_key, info in data.items():
        if not isinstance(info, dict):
            continue
        if 'id' in info and isinstance(info['id'], int) and info['id'] > 0:
            continue
        info['id'] = next_id
        next_id += 1
        assigned += 1

    # Сохраняем
    with open(roles_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Создаём пустой free_role_ids.json
    os.makedirs(os.path.dirname(free_ids_file), exist_ok=True)
    with open(free_ids_file, 'w', encoding='utf-8') as f:
        json.dump([], f, indent=2)

    print()
    print(f"✅ Готово!")
    print(f"   Присвоено ID: {assigned}")
    print(f"   Всего ID:     {next_id - 1}")
    print(f"   Бэкап: {backup}")


if __name__ == "__main__":
    main()