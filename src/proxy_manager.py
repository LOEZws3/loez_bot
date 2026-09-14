import os
import glob
import logging
import asyncio
import aiohttp
import ssl
import time
import json
import sys
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class ProxyManager:
    def __init__(self, proxy_dir: str = None, test_url: str = "https://api.telegram.org/bot"):
        self.proxy_dir = proxy_dir
        self.test_url = test_url
        self.proxies: List[str] = []
        self.proxy_pings: Dict[str, float] = {}
        self.current_index = 0
        self.current_proxy: Optional[str] = None
        self.used_proxies: set = set()
        self.cache_file = os.path.join(proxy_dir or "", "proxy_pings_cache.json") if proxy_dir else "proxy_pings_cache.json"

        # ✅ Приоритетный прокси (устанавливается из main.py)
        self.priority_proxy: Optional[str] = None

        # ✅ Настройки пинга
        self.PING_COUNT = 3              # 3 пинга на прокси
        self.MAX_CONCURRENT = 500        # 500 одновременных
        self.CACHE_TTL = 1200            # 20 минут (1200 сек)

        logger.info(f"📂 ProxyManager инициализирован. Папка: {proxy_dir}")
        logger.info(f"⚙️ PING_COUNT={self.PING_COUNT}, MAX_CONCURRENT={self.MAX_CONCURRENT}, CACHE_TTL={self.CACHE_TTL}с")

    # ==================== ЗАГРУЗКА ПРОКСИ ====================

    def load_proxies(self) -> int:
        if not os.path.exists(self.proxy_dir):
            logger.warning(f"⚠️ Папка {self.proxy_dir} не найдена")
            return 0

        pattern = os.path.join(self.proxy_dir, "good_proxies*.txt")
        files = glob.glob(pattern)

        if not files:
            logger.warning(f"⚠️ Файлы good_proxies*.txt не найдены в {self.proxy_dir}")
            return 0

        latest_file = max(files, key=os.path.getctime)

        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                self.proxies = [line.strip() for line in f if line.strip() and not line.startswith('#')]

            self.current_index = 0
            self.current_proxy = self.proxies[0] if self.proxies else None

            logger.info(f"✅ Загружено {len(self.proxies)} прокси из {os.path.basename(latest_file)}")
            return len(self.proxies)
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки прокси: {e}")
            return 0

    # ==================== SSL / ФОРМАТ ====================

    def _create_ssl_context(self):
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context

    def clean_proxy(self, proxy: str) -> Optional[str]:
        if not proxy:
            return None
        proxy = proxy.strip()
        if '|' in proxy:
            proxy = proxy.split('|')[0].strip()
        if ':' not in proxy:
            return None
        parts = proxy.split(':')
        if len(parts) >= 2:
            try:
                int(parts[-1])
                return proxy
            except ValueError:
                return None
        return proxy

    def format_proxy(self, proxy: str) -> Optional[str]:
        if not proxy:
            return None
        if proxy.startswith(('http://', 'https://', 'socks5://', 'socks4://')):
            return proxy
        return f"http://{proxy}"

    # ==================== ПИНГ ОДНОГО ПРОКСИ ====================

    async def ping_proxy_once(self, proxy: str, timeout: int = 5) -> Optional[float]:
        """Один пинг прокси. Возвращает время или None."""
        clean = self.clean_proxy(proxy)
        if not clean:
            return None

        proxy_url = self.format_proxy(clean)
        start_time = time.time()

        try:
            ssl_context = self._create_ssl_context()
            connector = aiohttp.TCPConnector(ssl=ssl_context)

            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(
                    self.test_url,
                    proxy=proxy_url,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status in [200, 404]:
                        return time.time() - start_time
                    return None
        except asyncio.TimeoutError:
            return None
        except Exception:
            return None

    async def ping_proxy_triple(self, proxy: str, timeout: int = 5) -> Optional[float]:
        """
        ✅ 3 пинга прокси. Возвращает среднее арифметическое.
        Если меньше 2 успешных — считаем прокси плохим.
        """
        results = []
        for i in range(self.PING_COUNT):
            ping = await self.ping_proxy_once(proxy, timeout=timeout)
            if ping is not None:
                results.append(ping)

        if len(results) < 2:
            return None  # Меньше 2 успешных — плохой прокси

        return round(sum(results) / len(results), 3)

    # ==================== ПИНГ ВСЕХ ПРОКСИ ====================

    async def ping_all_proxies(self, max_concurrent: int = None) -> Dict[str, float]:
        """
        ✅ Пингует ВСЕ прокси сразу (с ограничением MAX_CONCURRENT).
        ✅ 3 пинга на каждый прокси.
        ✅ Анимация прогресса в консоли.
        ✅ Приоритетный прокси проверяется первым.
        """
        if not self.proxies:
            logger.warning("⚠️ Нет прокси для пингования")
            return {}

        # Проверяем кэш
        cached_pings = self._load_cache()
        if cached_pings:
            self.proxy_pings = cached_pings
            logger.info(f"✅ Загружено {len(self.proxy_pings)} прокси из кэша (TTL {self.CACHE_TTL}с)")
            return self.proxy_pings

        # ✅ Приоритетный прокси
        if self.priority_proxy:
            clean = self.clean_proxy(self.priority_proxy)
            if clean:
                logger.info(f"⭐ Проверяю приоритетный прокси: {clean}")
                ping = await self.ping_proxy_triple(clean)
                if ping is not None:
                    logger.info(f"✅ Приоритетный прокси работает: {clean} (ср. пинг: {ping:.3f}с)")
                    self.proxy_pings = {clean: ping}
                    self._save_cache(self.proxy_pings)
                    return self.proxy_pings
                else:
                    logger.warning(f"❌ Приоритетный прокси {clean} не работает — иду по пингу")

        # ✅ Пингуем все прокси
        max_conc = max_concurrent or self.MAX_CONCURRENT
        logger.info(f"🏓 Пингую {len(self.proxies)} прокси (×{self.PING_COUNT} пинга, {max_conc} одновременно)...")
        start_time = time.time()

        semaphore = asyncio.Semaphore(max_conc)

        async def ping_with_semaphore(proxy):
            async with semaphore:
                ping = await self.ping_proxy_triple(proxy)
                return proxy, ping

        tasks = [ping_with_semaphore(proxy) for proxy in self.proxies]

        total = len(tasks)
        completed = 0
        results = []

        for task in asyncio.as_completed(tasks):
            result = await task
            results.append(result)
            completed += 1
            self._print_progress(completed, total, start_time)

        # Финальная строка
        sys.stdout.write("\n")
        sys.stdout.flush()

        self.proxy_pings = {}
        for proxy, ping in results:
            if ping is not None:
                clean = self.clean_proxy(proxy)
                if clean:
                    self.proxy_pings[clean] = ping

        elapsed = int(time.time() - start_time)
        logger.info(f"✅ Из {len(self.proxies)} прокси работают {len(self.proxy_pings)} (за {elapsed} сек)")

        self._save_cache(self.proxy_pings)

        sorted_pings = sorted(self.proxy_pings.items(), key=lambda x: x[1])
        if sorted_pings:
            fastest = sorted_pings[0]
            logger.info(f"🏆 Самый быстрый: {fastest[0]} ({fastest[1]:.3f}с)")
            for proxy, ping in sorted_pings[:5]:
                logger.info(f"   • {proxy}: {ping:.3f}с")

        return self.proxy_pings

    def _print_progress(self, completed: int, total: int, start_time: float):
        """✅ Анимация прогресса в консоли"""
        percent = int(completed / total * 100)
        bar_length = 30
        filled = int(bar_length * completed / total)
        bar = "█" * filled + "░" * (bar_length - filled)
        elapsed = int(time.time() - start_time)

        line = f"\r🏓 [{bar}] {completed}/{total} ({percent}%) — {elapsed} сек"
        sys.stdout.write(line)
        sys.stdout.flush()

    # ==================== КЭШ ====================

    def _load_cache(self) -> Optional[Dict[str, float]]:
        if not os.path.exists(self.cache_file):
            return None
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cache_time = data.get('timestamp', 0)
            if time.time() - cache_time > self.CACHE_TTL:  # 20 минут
                logger.info(f"🔄 Кэш устарел (>{self.CACHE_TTL}с), обновляем...")
                return None
            return data.get('pings', {})
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки кэша: {e}")
            return None

    def _save_cache(self, pings: Dict[str, float]):
        try:
            data = {'timestamp': time.time(), 'pings': pings}
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            logger.info(f"💾 Кэш пингов сохранён ({len(pings)} прокси)")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения кэша: {e}")

    # ==================== ВЫБОР ПРОКСИ ====================

    async def get_fastest_proxy(self) -> Optional[str]:
        await self.ping_all_proxies()
        if not self.proxy_pings:
            logger.warning("⚠️ Нет рабочих прокси")
            return None
        fastest = min(self.proxy_pings.items(), key=lambda x: x[1])
        self.current_proxy = fastest[0]
        self.current_index = 0
        logger.info(f"🏆 Выбран: {fastest[0]} ({fastest[1]:.3f}с)")
        return fastest[0]

    def get_next_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        attempts = 0
        max_attempts = len(self.proxies)
        while attempts < max_attempts:
            if self.current_index >= len(self.proxies):
                self.current_index = 0
            proxy = self.proxies[self.current_index]
            self.current_index += 1
            clean = self.clean_proxy(proxy)
            if clean and clean not in self.used_proxies:
                self.current_proxy = clean
                logger.info(f"🔄 Используется прокси: {clean} ({self.current_index}/{len(self.proxies)})")
                return clean
            attempts += 1
        logger.warning("⚠️ Нет доступных новых прокси")
        return None

    def get_next_fastest_proxy(self) -> Optional[str]:
        if not self.proxy_pings:
            logger.info("🏓 Пинги не загружены, выполняю проверку...")
            asyncio.create_task(self.ping_all_proxies())
            return self.get_next_proxy()
        sorted_proxies = sorted(self.proxy_pings.keys(), key=lambda p: self.proxy_pings[p])
        for proxy in sorted_proxies:
            if proxy not in self.used_proxies:
                self.current_proxy = proxy
                ping = self.proxy_pings.get(proxy, 0)
                logger.info(f"🔄 Используется прокси: {proxy} (пинг: {ping:.3f}с)")
                return proxy
        logger.warning("⚠️ Нет доступных новых прокси")
        return None

    # ==================== УТИЛИТЫ ====================

    def mark_proxy_bad(self, proxy: str):
        clean = self.clean_proxy(proxy)
        if not clean:
            return
        if clean in self.proxies:
            self.proxies.remove(clean)
            logger.warning(f"❌ Прокси {clean} удалён из списка")
        if clean in self.proxy_pings:
            del self.proxy_pings[clean]
        self.used_proxies.add(clean)
        self._save_cache(self.proxy_pings)

    def mark_proxy_used(self, proxy: str):
        clean = self.clean_proxy(proxy)
        if clean:
            self.used_proxies.add(clean)

    def reset_used_proxies(self):
        self.used_proxies = set()
        logger.info("🔄 Список использованных прокси сброшен")

    def get_current_proxy(self) -> Optional[str]:
        return self.current_proxy

    def get_proxy_count(self) -> int:
        return len(self.proxies)

    def get_proxy_pings(self) -> Dict[str, float]:
        return self.proxy_pings

    def reload(self) -> int:
        logger.info("🔄 Перезагрузка списка прокси...")
        self.used_proxies = set()
        return self.load_proxies()


# ==================== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР ====================

proxy_manager = ProxyManager()


# ==================== ФУНКЦИЯ ОЧИСТКИ КЭША ====================

def clear_pings_cache() -> bool:
    try:
        cache_file = proxy_manager.cache_file
        if os.path.exists(cache_file):
            os.remove(cache_file)
            logger.info(f"🗑️ Кэш пингов очищен: {cache_file}")
            return True
        logger.info(f"ℹ️ Файл кэша не найден: {cache_file}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка очистки кэша: {e}")
        return False