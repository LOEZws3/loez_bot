import asyncio
import logging
import sys
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
import time
dp = Dispatcher()
# --- ЗАГРУЖАЕМ ПЕРЕМЕННЫЕ ИЗ .env ---
load_dotenv()
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("❌ Токен не найден в .env файле!")

# --- НАСТРОЙКА ЛОГОВ ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- ИМПОРТ МЕНЕДЖЕРА ПРОКСИ ---
from proxy_manager import ProxyManager

# --- СОЗДАЁМ МЕНЕДЖЕР ---
proxy_manager = ProxyManager(token=TOKEN, data_dir="data/proxies")

# --- СОЗДАЁМ БОТА И ДИСПЕТЧЕРА ---
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ОБРАБОТЧИК КОМАНДЫ /start ---
@dp.message(Command("start"))
async def start_command(message: Message):
    await message.reply("Привет! Я бот, который работает через умную систему прокси!")

# --- ОБРАБОТЧИК ВСЕХ СООБЩЕНИЙ (пример) ---
@dp.message()
async def echo_message(message: Message):
    await message.reply(f"Эхо: {message.text}")

# --- ФУНКЦИЯ ЗАПУСКА БОТА С ПЕРЕБОРОМ ПРОКСИ ---
async def run_bot_with_proxy():
    while True:
        proxy = proxy_manager.get_working_proxy()
        if proxy:
            logger.info(f"🟢 Запускаем бота через прокси: {proxy}")
            # Создаём нового бота с прокси
            bot_instance = Bot(token=TOKEN, proxy=proxy)
            # Перезапускаем диспетчер с новым ботом
            await dp.start_polling(bot_instance, skip_updates=True)
        else:
            logger.warning("🔴 Нет рабочих прокси, перезапуск цикла через 10 секунд...")
            await asyncio.sleep(10)
            continue

# --- ТОЧКА ВХОДА ---
if __name__ == '__main__':
    try:
        asyncio.run(run_bot_with_proxy())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        # Перезапускаем скрипт при падении
        time.sleep(10)
        os.execl(sys.executable, sys.executable, *sys.argv)
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())        