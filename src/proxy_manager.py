import json
import os
import time
import logging
import requests
from datetime import datetime, timedelta
from aiogram import Bot

class ProxyManager:
    def __init__(self, token, data_dir="data/proxies"):
        self.token = token
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_dir = os.path.join(base_dir, data_dir)
        self.log = logging.getLogger(__name__)
        self.whitelist = {}
        self.suspicious = {}
        self.temp = {}
        self.reserve = {}
        self.blacklist = []
        self.quarantine = {}
        self.load_all()

    def load_all(self):
        self.whitelist = self._load_json("whitelist.json", default={})
        self.suspicious = self._load_json("suspicious.json", default={})
        self.temp = self._load_json("temp.json", default={})
        self.reserve = self._load_json("reserve.json", default={})
        self.blacklist = self._load_json("blacklist.json", default=[])
        self.quarantine = self._load_json("quarantine.json", default={})

    def save_all(self):
        self._save_json("whitelist.json", self.whitelist)
        self._save_json("suspicious.json", self.suspicious)
        self._save_json("temp.json", self.temp)
        self._save_json("reserve.json", self.reserve)
        self._save_json("blacklist.json", self.blacklist)
        self._save_json("quarantine.json", self.quarantine)

    def _load_json(self, filename, default):
        full_path = os.path.join(self.data_dir, filename)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if type(data) != type(default):
                    self.log.warning(f"⚠️ {filename} имеет неверный тип. Ожидался {type(default)}, получен {type(data)}. Использую значение по умолчанию.")
                    return default
                return data
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.log.warning(f"⚠️ Ошибка загрузки {filename}: {e}. Создаю файл со значением по умолчанию.")
            self._save_json(filename, default)
            return default

    def _save_json(self, filename, data):
        full_path = os.path.join(self.data_dir, filename)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        try:
            with open(full_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log.error(f"❌ Ошибка сохранения {filename}: {e}")

    async def check_proxy(self, proxy):
        try:
            bot = Bot(token=self.token, proxy=proxy)
            await bot.get_me()
            return True
        except Exception:
            return False

    async def refresh_all(self):
        self.log.info("🔄 Запущено обновление всех списков прокси...")
        new_whitelist = {}
        new_suspicious = {}
        new_temp = {}
        new_reserve = {}

        # 1. Проверяем WHITELIST
        self.log.info("📋 Проверка WHITELIST...")
        for proxy, rating in self.whitelist.items():
            if await self.check_proxy(proxy):
                new_whitelist[proxy] = rating
                self.log.info(f"✅ Белый прокси {proxy} работает (рейтинг: {rating})")
            else:
                new_rating = rating - 10
                if new_rating < 70 and new_rating >= 0:
                    new_suspicious[proxy] = new_rating
                    self.log.warning(f"🔶 {proxy} стал сомнительным (рейтинг: {new_rating})")
                else:
                    new_whitelist[proxy] = new_rating
                    self.log.warning(f"🔽 {proxy} потерял 10 баллов (теперь: {new_rating})")

        # 2. Проверяем SUSPICIOUS
        self.log.info("📋 Проверка SUSPICIOUS...")
        for proxy, rating in self.suspicious.items():
            if await self.check_proxy(proxy):
                new_rating = rating + 5
                if new_rating >= 70:
                    new_whitelist[proxy] = new_rating
                    self.log.info(f"⬆️ {proxy} вернулся в белый список (рейтинг: {new_rating})")
                else:
                    new_suspicious[proxy] = new_rating
                    self.log.info(f"📈 {proxy} набрал +5 баллов (теперь: {new_rating})")
            else:
                new_rating = rating - 5
                if new_rating < 0:
                    new_temp[proxy] = 85
                    self.log.warning(f"🔽 {proxy} ушёл в текучку (рейтинг: 85)")
                else:
                    new_suspicious[proxy] = new_rating
                    self.log.warning(f"📉 {proxy} потерял 5 баллов (теперь: {new_rating})")

        # 3. Проверяем TEMP (текучку) — С РАСШИРЕННЫМ ЛОГИРОВАНИЕМ
        self.log.info("📋 Проверка TEMP (текучка)...")
        temp_count = len(self.temp)
        self.log.info(f"📊 В текучке {temp_count} прокси")

        for proxy, rating in list(self.temp.items()):
            self.log.info(f"🔍 Проверяю прокси из текучки: {proxy} (текущий рейтинг: {rating})")
            
            if await self.check_proxy(proxy):
                new_rating = rating + 5
                self.log.info(f"✅ Прокси {proxy} РАБОТАЕТ! +5 баллов (было: {rating}, стало: {new_rating})")
                
                if new_rating >= 100:
                    new_reserve[proxy] = 100
                    self.log.info(f"🎉 {proxy} перешёл в РЕЗЕРВ (набрал 100 баллов)!")
                else:
                    new_temp[proxy] = new_rating
                    self.log.info(f"📈 {proxy} остаётся в текучке (теперь: {new_rating})")
            else:
                new_rating = rating - 5
                self.log.warning(f"❌ Прокси {proxy} НЕ РАБОТАЕТ! -5 баллов (было: {rating}, стало: {new_rating})")
                
                if new_rating <= -25:
                    self.quarantine[proxy] = datetime.now().isoformat()
                    self.log.warning(f"⛔ {proxy} ОТПРАВЛЕН В КАРАНТИН на 3 дня (рейтинг: {new_rating})")
                else:
                    new_temp[proxy] = new_rating
                    self.log.warning(f"📉 {proxy} остаётся в текучке (теперь: {new_rating})")

        # 4. Проверяем RESERVE
        self.log.info("📋 Проверка RESERVE...")
        for proxy, rating in self.reserve.items():
            if await self.check_proxy(proxy):
                new_rating = rating + 2
                if new_rating >= 100:
                    new_reserve[proxy] = new_rating
                    self.log.info(f"✅ {proxy} остаётся в резерве (рейтинг: {new_rating})")
                else:
                    new_temp[proxy] = 85
                    self.log.warning(f"⬇️ {proxy} вылетел из резерва в текучку (85)")
            else:
                new_rating = rating - 5
                if new_rating < 100:
                    new_temp[proxy] = 85
                    self.log.warning(f"⬇️ {proxy} вылетел из резерва в текучку (85)")
                else:
                    new_reserve[proxy] = new_rating
                    self.log.warning(f"📉 {proxy} потерял 5 баллов в резерве (теперь: {new_rating})")

        # 5. КАРАНТИН
        self.log.info("📋 Проверка КАРАНТИНА...")
        current_time = datetime.now()
        for proxy, date_str in list(self.quarantine.items()):
            try:
                quarantine_date = datetime.fromisoformat(date_str)
                if current_time - quarantine_date >= timedelta(days=3):
                    new_temp[proxy] = -10
                    del self.quarantine[proxy]
                    self.log.info(f"🔄 {proxy} вышел из карантина с рейтингом -10")
                else:
                    days_left = (quarantine_date + timedelta(days=3) - current_time).days
                    self.log.info(f"⏳ {proxy} ещё в карантине (осталось {days_left} дн.)")
            except Exception as e:
                self.log.error(f"❌ Ошибка обработки карантина для {proxy}: {e}")

        # 6. ЧЁРНЫЙ СПИСОК
        self.log.info("📋 Проверка ЧЁРНОГО СПИСКА...")
        for proxy in list(new_temp.keys()):
            if proxy in self.blacklist:
                del new_temp[proxy]
                self.log.warning(f"🚫 {proxy} в чёрном списке — удалён из текучки")

        # Обновляем списки
        self.whitelist = new_whitelist
        self.suspicious = new_suspicious
        self.temp = new_temp
        self.reserve = new_reserve
        self.save_all()
        
        self.log.info("✅ Обновление завершено, списки сохранены")
        self.log.info(f"📊 Итог: WHITELIST={len(self.whitelist)}, SUSPICIOUS={len(self.suspicious)}, TEMP={len(self.temp)}, RESERVE={len(self.reserve)}")

    def fetch_fresh_proxies(self):
        self.log.info("🌐 Парсинг новых прокси с GitHub...")
        try:
            url = "https://raw.githubusercontent.com/kort0881/telegram-proxy-collector/main/socks5.txt"
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                self.log.warning(f"❌ Ошибка HTTP: {response.status_code}")
                return

            lines = response.text.strip().splitlines()
            added = 0
            for line in lines:
                line = line.strip()
                if not line or ":" not in line:
                    continue
                if not line.startswith("socks5://"):
                    proxy = f"socks5://{line}"
                else:
                    proxy = line
                if proxy not in self.blacklist and proxy not in self.temp:
                    self.temp[proxy] = 0
                    added += 1
                    self.log.info(f"➕ Добавлен новый прокси в текучку: {proxy} (старт: 0)")
                    if added >= 10:
                        break
            self.log.info(f"✅ Добавлено {added} новых прокси в текучку (старт: 0)")
            self.save_all()
        except Exception as e:
            self.log.error(f"❌ Ошибка парсинга: {e}")

    async def get_working_proxy(self):
        self.log.info("🔍 Подбор рабочего прокси для запуска...")

        # Проверяем WHITELIST
        self.log.info("📋 Проверка WHITELIST...")
        for proxy in list(self.whitelist.keys()):
            self.log.info(f"🔍 Проверяю белый прокси: {proxy} (рейтинг: {self.whitelist[proxy]})")
            if await self.check_proxy(proxy):
                self.log.info(f"✅ Найден рабочий прокси в whitelist: {proxy} (рейтинг: {self.whitelist[proxy]})")
                return proxy
            else:
                current_rating = self.whitelist.get(proxy, 100)
                new_rating = current_rating - 10
                self.log.warning(f"❌ {proxy} не работает. Снимаю 10 баллов (было: {current_rating}, стало: {new_rating})")
                if new_rating < 70:
                    self.suspicious[proxy] = new_rating
                    del self.whitelist[proxy]
                    self.log.warning(f"🔶 {proxy} перемещён в сомнительные (рейтинг: {new_rating})")
                else:
                    self.whitelist[proxy] = new_rating
                self.save_all()

        # Проверяем RESERVE
        self.log.info("📋 Проверка RESERVE...")
        if self.reserve:
            for proxy in list(self.reserve.keys()):
                self.log.info(f"🔍 Проверяю резервный прокси: {proxy} (рейтинг: {self.reserve[proxy]})")
                if await self.check_proxy(proxy):
                    self.log.info(f"✅ Найден рабочий прокси в резерве: {proxy} (рейтинг: {self.reserve[proxy]})")
                    return proxy
                else:
                    new_rating = self.reserve[proxy] - 5
                    self.log.warning(f"❌ {proxy} не работает. Снимаю 5 баллов (было: {self.reserve[proxy]}, стало: {new_rating})")
                    if new_rating < 100:
                        self.temp[proxy] = 85
                        del self.reserve[proxy]
                        self.log.warning(f"⬇️ {proxy} вылетел из резерва в текучку (85)")
                    else:
                        self.reserve[proxy] = new_rating
                    self.save_all()

        self.log.error("💀 Все прокси мертвы! Запрашиваю новые...")
        self.fetch_fresh_proxies()
        time.sleep(30)
        return None

    async def run_auto_update(self):
        while True:
            await self.refresh_all()
            self.fetch_fresh_proxies()
            time.sleep(3600)