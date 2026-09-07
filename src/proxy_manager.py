import os
import glob
import logging
import asyncio
import aiohttp
import ssl
import time
import json
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class ProxyManager:
    def __init__(self, proxy_dir: str = None, test_url: str = "https://api.telegram.org/bot"):
        """
        Менеджер прокси с пингованием через Telegram API
        
        Args:
            proxy_dir: папка с файлами good_proxies*.txt
            test_url: URL для проверки задержки (Telegram API)
        """
        self.proxy_dir = proxy_dir
        self.test_url = test_url
        self.proxies: List[str] = []
        self.proxy_pings: Dict[str, float] = {}
        self.current_index = 0
        self.current_proxy: Optional[str] = None
        self.used_proxies: set = set()
        self.cache_file = os.path.join(proxy_dir or "", "proxy_pings_cache.json") if proxy_dir else "proxy_pings_cache.json"
        
        logger.info(f"📂 ProxyManager инициализирован. Папка: {proxy_dir}")
    
    def load_proxies(self) -> int:
        """Загружает прокси из последнего файла good_proxies*.txt"""
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
    
    def _create_ssl_context(self):
        """Создаёт SSL-контекст с отключённой проверкой"""
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context
    
    def clean_proxy(self, proxy: str) -> str:
        """Очищает прокси от дат и лишних символов"""
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
    
    async def ping_proxy(self, proxy: str, timeout: int = 5) -> Optional[float]:
        """
        Проверяет задержку прокси через Telegram API
        
        Args:
            proxy: прокси-адрес (ip:port)
            timeout: таймаут в секундах (5 секунд)
        
        Returns:
            Задержка в секундах или None, если прокси не отвечает
        """
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
                    # ✅ Telegram API возвращает 404 для /bot без токена, но это значит, что API доступен!
                    if response.status in [200, 404]:
                        ping = time.time() - start_time
                        return ping
                    else:
                        return None
        except asyncio.TimeoutError:
            return None
        except Exception:
            return None
    
    async def ping_all_proxies(self, max_concurrent: int = 100) -> Dict[str, float]:
        """
        Проверяет задержку всех прокси через Telegram API
        
        Args:
            max_concurrent: максимальное количество одновременных проверок (100)
        
        Returns:
            Словарь {proxy: ping} только для работающих прокси
        """
        if not self.proxies:
            logger.warning("⚠️ Нет прокси для пингования")
            return {}
        
        # Проверяем кэш
        cached_pings = self._load_cache()
        if cached_pings:
            self.proxy_pings = cached_pings
            logger.info(f"✅ Загружено {len(self.proxy_pings)} прокси из кэша")
            return self.proxy_pings
        
        logger.info(f"🏓 Пингую {len(self.proxies)} прокси через Telegram API...")
        start_time = time.time()
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def ping_with_semaphore(proxy):
            async with semaphore:
                ping = await self.ping_proxy(proxy)
                return proxy, ping
        
        tasks = [ping_with_semaphore(proxy) for proxy in self.proxies]
        
        # Прогресс-бар
        total = len(tasks)
        completed = 0
        
        results = []
        for task in asyncio.as_completed(tasks):
            result = await task
            results.append(result)
            completed += 1
            if completed % 50 == 0 or completed == total:
                elapsed = int(time.time() - start_time)
                logger.info(f"📊 Прогресс: {completed}/{total} (прошло {elapsed} сек)")
        
        self.proxy_pings = {}
        for proxy, ping in results:
            if ping is not None:
                clean = self.clean_proxy(proxy)
                if clean:
                    self.proxy_pings[clean] = round(ping, 3)
        
        elapsed = int(time.time() - start_time)
        logger.info(f"✅ Из {len(self.proxies)} прокси работают {len(self.proxy_pings)} (за {elapsed} сек)")
        
        # Сохраняем в кэш
        self._save_cache(self.proxy_pings)
        
        sorted_pings = sorted(self.proxy_pings.items(), key=lambda x: x[1])
        if sorted_pings:
            fastest = sorted_pings[0]
            logger.info(f"🏆 Самый быстрый прокси: {fastest[0]} ({fastest[1]:.3f}с)")
            for proxy, ping in sorted_pings[:5]:
                logger.info(f"   • {proxy}: {ping:.3f}с")
        
        return self.proxy_pings
    
    def _load_cache(self) -> Optional[Dict[str, float]]:
        """Загружает кэш пингов из файла"""
        if not os.path.exists(self.cache_file):
            return None
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Проверяем, не устарел ли кэш (храним 10 минут)
            cache_time = data.get('timestamp', 0)
            if time.time() - cache_time > 600:  # 10 минут
                logger.info("🔄 Кэш устарел, обновляем...")
                return None
            
            return data.get('pings', {})
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки кэша: {e}")
            return None
    
    def _save_cache(self, pings: Dict[str, float]):
        """Сохраняет кэш пингов в файл"""
        try:
            data = {
                'timestamp': time.time(),
                'pings': pings
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            logger.info(f"💾 Кэш пингов сохранён ({len(pings)} прокси)")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения кэша: {e}")
    
    async def get_fastest_proxy(self) -> Optional[str]:
        """Возвращает самый быстрый прокси (с кэшированием)"""
        await self.ping_all_proxies()
        
        if not self.proxy_pings:
            logger.warning("⚠️ Нет рабочих прокси")
            return None
        
        fastest = min(self.proxy_pings.items(), key=lambda x: x[1])
        self.current_proxy = fastest[0]
        self.current_index = 0
        
        logger.info(f"🏆 Выбран самый быстрый прокси: {fastest[0]} ({fastest[1]:.3f}с)")
        return fastest[0]
    
    def get_next_proxy(self) -> Optional[str]:
        """Возвращает следующий прокси из списка"""
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
        """Возвращает следующий прокси, отсортированный по пингу"""
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
    
    def mark_proxy_bad(self, proxy: str):
        """Удаляет неработающий прокси"""
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
        """Отмечает прокси как использованный"""
        clean = self.clean_proxy(proxy)
        if clean:
            self.used_proxies.add(clean)
    
    def reset_used_proxies(self):
        """Сбрасывает список использованных прокси"""
        self.used_proxies = set()
        logger.info("🔄 Список использованных прокси сброшен")
    
    def get_current_proxy(self) -> Optional[str]:
        return self.current_proxy
    
    def get_proxy_count(self) -> int:
        return len(self.proxies)
    
    def get_proxy_pings(self) -> Dict[str, float]:
        return self.proxy_pings
    
    def format_proxy(self, proxy: str) -> str:
        if not proxy:
            return None
        
        if proxy.startswith(('http://', 'https://', 'socks5://', 'socks4://')):
            return proxy
        
        return f"http://{proxy}"
    
    def reload(self) -> int:
        logger.info("🔄 Перезагрузка списка прокси...")
        self.used_proxies = set()
        return self.load_proxies()


# Создаём глобальный экземпляр
proxy_manager = ProxyManager()