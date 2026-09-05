import os
import sys

print("="*60)
print("🔍 ДИАГНОСТИКА ПУТИ К ПРОКСИ")
print("="*60)

# Путь из config.py
path = r"C:\Users\olika\PyCharmMiscProject\proxy_manadger"

print(f"\n📁 Путь: {path}")
print(f"📁 Существует: {os.path.exists(path)}")

if os.path.exists(path):
    files = os.listdir(path)
    print(f"📁 Файлов в папке: {len(files)}")
    
    # Ищем good_proxies файлы
    good_files = [f for f in files if f.startswith('good_proxies')]
    print(f"📁 Файлов good_proxies*.txt: {len(good_files)}")
    
    for f in good_files:
        full_path = os.path.join(path, f)
        size = os.path.getsize(full_path)
        print(f"   • {f} ({size} байт)")
    
    # Проверяем конкретный файл
    good_file = os.path.join(path, "good_proxies.txt")
    print(f"\n📄 good_proxies.txt существует: {os.path.exists(good_file)}")
    
    if os.path.exists(good_file):
        with open(good_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            print(f"📄 Найдено прокси в файле: {len(lines)}")
            if lines:
                print("📄 Первые 5 прокси:")
                for p in lines[:5]:
                    print(f"   • {p}")
else:
    print("❌ ПАПКА НЕ СУЩЕСТВУЕТ!")
    print("\n💡 Возможные причины:")
    print("   • Неправильный путь в config.py")
    print("   • Бот запускается из другой папки")
    print(f"   • Текущая папка: {os.getcwd()}")

print("\n" + "="*60)