import asyncio
import logging
import sys
import os
import time
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, executor

load_dotenv()
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("❌ Токен не найден в .env файле!")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Подключаем роутеры
from handlers import routers
for router in routers:
    dp.include_router(router)

# ============================================================
# ЗАПУСК
# ============================================================
if __name__ == '__main__':
    while True:
        try:
            logger.info("🚀 Бот запущен через системный VPN!")
            executor.start_polling(dp, skip_updates=True)
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            logger.info("🔄 Перезапуск через 10 секунд...")
            time.sleep(10)
            os.execl(sys.executable, sys.executable, *sys.argv)