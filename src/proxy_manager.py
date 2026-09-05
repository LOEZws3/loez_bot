import os
import glob
import logging
import asyncio
import aiohttp
import ssl
import time
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class ProxyManager:
    def __init__(self, proxy_dir: str = None, test_url: str = "http://httpbin.org/ip"):
        """
        Менеджер прокси с пингованием
        
        Args:
            proxy_dir: папка с файлами good_proxies*.txt
            test_url: URL для проверки задержки
        """
        self.proxy_dir = proxy_dir
        self.test_url = test_url
        self.proxies: List[str] = []
        self.proxy_pings: Dict[str, float] = {}  # proxy -> ping (в секундах)
        self.current_index = 0
        self.current_proxy: Optional[str] = None
        
        # ✅ Приоритетные прокси (которые работают в Telegram Desktop)
        self.priority_proxies = [
            "178.212.144.7:80",
            "137.66.1.45:80",
            "210.211.113.35:80",
            "202.133.88.173:80",
            "140.99.255.67:8080",
            "45.43.60.220:8080",
            "103.95.34.186:3128",
            "14.139.235.82:3128",
            "199.7.149.96:3128",
        ]
        
        logger.info(f"📂 ProxyManager инициализирован. Папка: {proxy_dir}")
        logger.info(f"⭐ Приоритетных прокси: {len(self.priority_proxies)}")
    
    def load_proxies(self) -> int:
        """Загружает прокси из последнего файла good_proxies*.txt и добавляет приоритетные"""
        if not os.path.exists(self.proxy_dir):
            logger.warning(f"⚠️ Папка {self.proxy_dir} не найдена")
            return 0
        
        pattern = os.path.join(self.proxy_dir, "good_proxies*.txt")
        files = glob.glob(pattern)
        
        all_proxies = []
        
        # ✅ Сначала добавляем приоритетные прокси
        for proxy in self.priority_proxies:
            if proxy not in all_proxies:
                all_proxies.append(proxy)
        
        # ✅ Затем загружаем из файла
        if files:
            latest_file = max(files, key=os.path.getctime)
            try:
                with open(latest_file, 'r', encoding='utf-8') as f:
                    file_proxies = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                
                for proxy in file_proxies:
                    if proxy not in all_proxies:
                        all_proxies.append(proxy)
                
                logger.info(f"📂 Загружено {len(file_proxies)} прокси из {os.path.basename(latest_file)}")
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки прокси: {e}")
        
        self.proxies = all_proxies
        self.current_index = 0
        self.current_proxy = self.proxies[0] if self.proxies else None
        
        logger.info(f"✅ Всего загружено {len(self.proxies)} прокси (включая {len(self.priority_proxies)} приоритетных)")
        return len(self.proxies)
    
    def _create_ssl_context(self):
        """Создаёт SSL-контекст с отключённой проверкой"""
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context
    
    async def ping_proxy(self, proxy: str, timeout: int = 5) -> Optional[float]:
        """Проверяет задержку прокси"""
        proxy_url = self.format_proxy(proxy)
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
                    if response.status == 200:
                        ping = time.time() - start_time
                        logger.debug(f"🏓 Пинг {proxy}: {ping:.3f}с")
                        return ping
                    else:
                        logger.debug(f"❌ {proxy} вернул статус {response.status}")
                        return None
        except asyncio.TimeoutError:
            logger.debug(f"⏰ {proxy} таймаут")
            return None
        except Exception as e:
            logger.debug(f"❌ {proxy} ошибка: {str(e)[:50]}")
            return None
    
    async def ping_all_proxies(self, max_concurrent: int = 10) -> Dict[str, float]:
        """Проверяет задержку всех прокси"""
        if not self.proxies:
            logger.warning("⚠️ Нет прокси для пингования")
            return {}
        
        logger.info(f"🏓 Пингую {len(self.proxies)} прокси...")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def ping_with_semaphore(proxy):
            async with semaphore:
                ping = await self.ping_proxy(proxy)
                return proxy, ping
        
        tasks = [ping_with_semaphore(proxy) for proxy in self.proxies]
        results = await asyncio.gather(*tasks)
        
        self.proxy_pings = {}
        for proxy, ping in results:
            if ping is not None:
                self.proxy_pings[proxy] = ping
        
        logger.info(f"✅ Из {len(self.proxies)} прокси работают {len(self.proxy_pings)}")
        
        sorted_pings = sorted(self.proxy_pings.items(), key=lambda x: x[1])
        if sorted_pings:
            fastest = sorted_pings[0]
            logger.info(f"🏆 Самый быстрый прокси: {fastest[0]} ({fastest[1]:.3f}с)")
            for proxy, ping in sorted_pings[:5]:
                logger.info(f"   • {proxy}: {ping:.3f}с")
        
        return self.proxy_pings
    
    async def get_fastest_proxy(self, timeout: int = 5) -> Optional[str]:
        """
        Возвращает самый быстрый прокси (сначала проверяет приоритетные)
        """
        # ✅ Сначала проверяем приоритетные прокси отдельно
        priority_pings = {}
        for proxy in self.priority_proxies:
            if proxy in self.proxies:
                ping = await self.ping_proxy(proxy, timeout)
                if ping is not None:
                    priority_pings[proxy] = ping
                    logger.info(f"⭐ Приоритетный прокси {proxy}: {ping:.3f}с")
        
        if priority_pings:
            fastest = min(priority_pings.items(), key=lambda x: x[1])
            self.current_proxy = fastest[0]
            self.current_index = self.proxies.index(fastest[0]) if fastest[0] in self.proxies else 0
            self.proxy_pings = priority_pings
            logger.info(f"🏆 Выбран приоритетный прокси: {fastest[0]} ({fastest[1]:.3f}с)")
            return fastest[0]
        
        # ✅ Если приоритетные не работают — проверяем все остальные
        await self.ping_all_proxies()
        
        if not self.proxy_pings:
            logger.warning("⚠️ Нет рабочих прокси")
            return None
        
        fastest = min(self.proxy_pings.items(), key=lambda x: x[1])
        self.current_proxy = fastest[0]
        self.current_index = self.proxies.index(fastest[0]) if fastest[0] in self.proxies else 0
        
        logger.info(f"🏆 Выбран самый быстрый прокси: {fastest[0]} ({fastest[1]:.3f}с)")
        return fastest[0]
    
    def get_next_proxy(self) -> Optional[str]:
        """Возвращает следующий прокси из списка (без пингования)"""
        if not self.proxies:
            return None
        
        if self.current_index >= len(self.proxies):
            self.current_index = 0
        
        proxy = self.proxies[self.current_index]
        self.current_index += 1
        self.current_proxy = proxy
        
        logger.info(f"🔄 Используется прокси: {proxy} ({self.current_index}/{len(self.proxies)})")
        return proxy
    
    def get_next_fastest_proxy(self) -> Optional[str]:
        """Возвращает следующий прокси, отсортированный по пингу"""
        if not self.proxy_pings:
            logger.info("🏓 Пинги не загружены, выполняю проверку...")
            asyncio.create_task(self.ping_all_proxies())
            return self.get_next_proxy()
        
        sorted_proxies = sorted(self.proxy_pings.keys(), key=lambda p: self.proxy_pings[p])
        
        if not sorted_proxies:
            return self.get_next_proxy()
        
        if self.current_index >= len(sorted_proxies):
            self.current_index = 0
        
        proxy = sorted_proxies[self.current_index]
        self.current_index += 1
        self.current_proxy = proxy
        
        ping = self.proxy_pings.get(proxy, 0)
        logger.info(f"🔄 Используется прокси: {proxy} (пинг: {ping:.3f}с, {self.current_index}/{len(sorted_proxies)})")
        return proxy
    
    def mark_proxy_bad(self, proxy: str):
        """Удаляет неработающий прокси из списка"""
        if proxy in self.proxies:
            self.proxies.remove(proxy)
            logger.warning(f"❌ Прокси {proxy} удалён из списка (не работает)")
            if self.current_proxy == proxy:
                self.current_proxy = self.get_next_proxy()
        
        if proxy in self.proxy_pings:
            del self.proxy_pings[proxy]
    
    def get_current_proxy(self) -> Optional[str]:
        """Возвращает текущий прокси"""
        return self.current_proxy
    
    def get_proxy_count(self) -> int:
        """Возвращает количество прокси в списке"""
        return len(self.proxies)
    
    def get_proxy_pings(self) -> Dict[str, float]:
        """Возвращает словарь {proxy: ping}"""
        return self.proxy_pings
    
    def format_proxy(self, proxy: str) -> str:
        """Форматирует прокси для aiohttp"""
        if not proxy:
            return None
        
        if proxy.startswith(('http://', 'https://', 'socks5://', 'socks4://')):
            return proxy
        
        return f"http://{proxy}"
    
    def reload(self) -> int:
        """Перезагружает список прокси (для обновления)"""
        logger.info("🔄 Перезагрузка списка прокси...")
        return self.load_proxies()


# Создаём глобальный экземпляр
proxy_manager = ProxyManager()