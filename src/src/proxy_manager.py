import json
import time
import logging
import requests
from datetime import datetime, timedelta
from aiogram import Bot

class ProxyManager:
    def __init__(self, token, data_dir="data/proxies"):
        self.token = token
        self.data_dir = data_dir
        self.whitelist = {}
        self.suspicious = {}
        self.temp = {}
        self.reserve = {}
        self.blacklist = []
        self.quarantine = {}
        self.load_all()
        self.log = logging.getLogger(__name__)

    def load_all(self):
        self.whitelist = self._load_json("whitelist.json")
        self.suspicious = self._load_json("suspicious.json")
        self.temp = self._load_json("temp.json")
        self.reserve = self._load_json("reserve.json")
        self.blacklist = self._load_json("blacklist.json")
        self.quarantine = self._load_json("quarantine.json")

    def save_all(self):
        self._save_json("whitelist.json", self.whitelist)
        self._save_json("suspicious.json", self.suspicious)
        self._save_json("temp.json", self.temp)
        self._save_json("reserve.json", self.reserve)
        self._save_json("blacklist.json", self.blacklist)
        self._save_json("quarantine.json", self.quarantine)

    def _load_json(self, filename):
        try:
            with open(f"{self.data_dir}/{filename}", "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {} if "blacklist" not in filename else []

    def _save_json(self, filename, data):
        with open(f"{self.data_dir}/{filename}", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def check_proxy(self, proxy):
        try:
            bot = Bot(token=self.token, proxy=proxy)
            bot.get_me()
            return True
        except:
            return False

    def refresh_all(self):
        self.log.info("🔄 Запущено обновление всех списков прокси...")
        new_whitelist = {}
        new_suspicious = {}
        new_temp = {}
        new_reserve = {}

        # 1. WHITELIST
        for proxy, rating in self.whitelist.items():
            if self.check_proxy(proxy):
                new_whitelist[proxy] = rating
            else:
                new_rating = rating - 10
                if new_rating < 70 and new_rating >= 0:
                    new_suspicious[proxy] = new_rating
                    self.log.warning(f"🔶 {proxy} стал сомнительным (рейтинг: {new_rating})")
                else:
                    new_whitelist[proxy] = new_rating

        # 2. SUSPICIOUS
        for proxy, rating in self.suspicious.items():
            if self.check_proxy(proxy):
                new_rating = rating + 5
                if new_rating >= 70:
                    new_whitelist[proxy] = new_rating
                    self.log.info(f"⬆️ {proxy} вернулся в белый список (рейтинг: {new_rating})")
                else:
                    new_suspicious[proxy] = new_rating
            else:
                new_rating = rating - 5
                if new_rating < 0:
                    new_temp[proxy] = 85
                    self.log.warning(f"🔽 {proxy} ушёл в текучку (рейтинг: 85)")
                else:
                    new_suspicious[proxy] = new_rating

        # 3. TEMP
        for proxy, rating in self.temp.items():
            if self.check_proxy(proxy):
                new_rating = rating + 5
                if new_rating >= 100:
                    new_reserve[proxy] = 100
                    self.log.info(f"🎉 {proxy} перешёл в резерв!")
                else:
                    new_temp[proxy] = new_rating
            else:
                new_rating = rating - 5
                if new_rating <= -25:
                    self.quarantine[proxy] = datetime.now().isoformat()
                    self.log.warning(f"⛔ {proxy} в карантине до {datetime.now() + timedelta(days=3)}")
                else:
                    new_temp[proxy] = new_rating

        # 4. RESERVE
        for proxy, rating in self.reserve.items():
            if self.check_proxy(proxy):
                new_rating = rating + 2
                if new_rating >= 100:
                    new_reserve[proxy] = new_rating
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

        # 5. КАРАНТИН
        current_time = datetime.now()
        for proxy, date_str in list(self.quarantine.items()):
            try:
                quarantine_date = datetime.fromisoformat(date_str)
                if current_time - quarantine_date >= timedelta(days=3):
                    new_temp[proxy] = -10
                    del self.quarantine[proxy]
                    self.log.info(f"🔄 {proxy} вышел из карантина с рейтингом -10")
            except:
                pass

        # 6. ЧЁРНЫЙ СПИСОК
        for proxy in list(new_temp.keys()):
            if proxy in self.blacklist:
                del new_temp[proxy]
                self.log.warning(f"🚫 {proxy} в чёрном списке — удалён из текучки")

        self.whitelist = new_whitelist
        self.suspicious = new_suspicious
        self.temp = new_temp
        self.reserve = new_reserve
        self.save_all()
        self.log.info("✅ Обновление завершено, списки сохранены")

    def fetch_fresh_proxies(self):
        self.log.info("🌐 Парсинг новых прокси с GitHub...")
        try:
            url = "https://raw.githubusercontent.com/kort0881/telegram-proxy-collector/main/socks5.txt"
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                self.log.warning("❌ Не удалось получить список прокси")
                return

            proxies = response.text.strip().splitlines()
            added = 0
            for proxy in proxies[:10]:
                proxy = proxy.strip()
                if proxy and proxy not in self.blacklist and proxy not in self.temp:
                    self.temp[proxy] = 0
                    added += 1
            self.log.info(f"✅ Добавлено {added} новых прокси в текучку (старт: 0)")
            self.save_all()
        except Exception as e:
            self.log.error(f"❌ Ошибка парсинга: {e}")

    def get_working_proxy(self):
        self.log.info("🔍 Подбор рабочего прокси для запуска...")

        for proxy, rating in self.whitelist.items():
            if self.check_proxy(proxy):
                self.log.info(f"✅ Найден рабочий прокси в whitelist: {proxy} (рейтинг: {rating})")
                return proxy
            else:
                new_rating = rating - 10
                self.whitelist[proxy] = new_rating
                if new_rating < 70:
                    self.suspicious[proxy] = new_rating
                    del self.whitelist[proxy]
                    self.log.warning(f"🔶 {proxy} перемещён в сомнительные (рейтинг: {new_rating})")
                self.save_all()

        if self.reserve:
            best_proxy = max(self.reserve, key=self.reserve.get)
            if self.check_proxy(best_proxy):
                self.log.info(f"✅ Найден рабочий прокси в резерве: {best_proxy} (рейтинг: {self.reserve[best_proxy]})")
                return best_proxy
            else:
                self.reserve[best_proxy] -= 5
                if self.reserve[best_proxy] < 100:
                    self.temp[best_proxy] = 85
                    del self.reserve[best_proxy]
                    self.log.warning(f"⬇️ {best_proxy} вылетел из резерва в текучку (85)")
                self.save_all()

        self.log.error("💀 Все прокси мертвы! Запрашиваю новые...")
        self.fetch_fresh_proxies()
        time.sleep(30)
        return None

    def run_auto_update(self):
        while True:
            self.refresh_all()
            self.fetch_fresh_proxies()
            time.sleep(3600)