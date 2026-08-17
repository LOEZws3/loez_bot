import asyncio
import logging
import sys
import os
import time
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from proxy_manager import ProxyManager

# Загружаем переменные окружения из .env
load_dotenv()
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("❌ Токен не найден в .env файле!")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создаём объект бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Инициализируем менеджер прокси
proxy_manager = ProxyManager(token=TOKEN, data_dir="data/proxies")

# Импортируем и подключаем роутеры из папки handlers
try:
    from handlers import routers
    for router in routers:
        dp.include_router(router)
    logger.info("✅ Роутеры успешно загружены")
except ImportError as e:
    logger.warning(f"⚠️ Не удалось загрузить роутеры: {e}")

# ============================================================
# ФУНКЦИЯ ЗАПУСКА БОТА С ПЕРЕБОРОМ ПРОКСИ
# ============================================================
async def run_bot_with_proxy():
    while True:
        proxy = await proxy_manager.get_working_proxy()
        if proxy:
            logger.info(f"🟢 Запускаем бота через прокси: {proxy}")
            # Создаём нового бота с этим прокси
            bot_instance = Bot(token=TOKEN, proxy=proxy)
            # Запускаем поллинг
            await dp.start_polling(bot_instance, skip_updates=True)
        else:
            logger.warning("🔴 Нет рабочих прокси, перезапуск цикла через 10 секунд...")
            await asyncio.sleep(10)
            continue

# ============================================================
# ТОЧКА ВХОДА
# ============================================================
async def main():
    await run_bot_with_proxy()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        time.sleep(10)
        # Перезапускаем скрипт
        os.execl(sys.executable, sys.executable, *sys.argv)