#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт миграции roles_status.json.

Что делает:
1. Читает data/roles/roles_status.json
2. Для каждого ключа БЕЗ "(" (скобок): берёт season из данных и переименовывает в "Имя (Сезон)"
3. Если ключ УЖЕ содержит "(" — оставляет как есть
4. Сохраняет результат
5. Делает бэкап старого файла

Запуск: python migrate_roles.py
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
    # Пути
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, 'data', 'roles')
    roles_file = os.path.join(data_dir, 'roles_status.json')

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
    backup_file = roles_file + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(roles_file, backup_file)
    print(f"💾 Бэкап создан: {os.path.basename(backup_file)}")

    # Миграция
    new_data = {}
    renamed = 0
    skipped = 0

    for key, value in data.items():
        if not isinstance(value, dict):
            # Странная запись — оставляем как есть
            new_data[key] = value
            continue

        # Уже с сезоном в скобках?
        if '(' in key and ')' in key:
            new_data[key] = value
            skipped += 1
            continue

        # Берём сезон из данных
        season = value.get('season', '').strip()

        if not season:
            # Нет сезона — оставляем как есть
            new_data[key] = value
            skipped += 1
            continue

        # Новый ключ
        new_key = f"{key} ({season})"

        # Проверка на конфликт
        if new_key in new_data:
            print(f"⚠️ Конфликт: '{new_key}' уже существует. Оставляю '{key}'")
            new_data[key] = value
            skipped += 1
            continue

        new_data[new_key] = value
        renamed += 1
        print(f"🔄 '{key}' → '{new_key}'")

    # Сохраняем
    with open(roles_file, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    print()
    print(f"✅ Готово!")
    print(f"   Переименовано: {renamed}")
    print(f"   Пропущено:     {skipped}")
    print(f"   Всего записей: {len(new_data)}")
    print()
    print(f"💾 Бэкап: {backup_file}")


if __name__ == "__main__":
    main()