import asyncio
import logging
import sys
from pathlib import Path

# Исправлено: __file__ вместо file
sys.path.insert(0, str(Path(__file__).parent))

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from dotenv import load_dotenv
import os
import aiohttp

# ============================================================
# ЛОГИ
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
# Исправлено: __name__ вместо name
log = logging.getLogger(__name__)

# ============================================================
# ЗАГРУЗКА ТОКЕНА
# ============================================================
# Исправлено: __file__ вместо file
load_dotenv(Path(__file__).parent.parent / ".env")
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    log.error("❌ Токен не найден!")
    sys.exit(1)

# ============================================================
# ПРОКСИ - ПРОВЕРЯЕМ РАЗНЫЕ ПОРТЫ
# ============================================================
PROXY_OPTIONS = [
    "socks5://127.0.0.1:3066",
    "socks5://127.0.0.1:1080",
    "socks5://127.0.0.1:7890",
    "socks5://localhost:3066",
    "http://127.0.0.1:3066",
    "http://127.0.0.1:1080",
]


async def find_working_proxy():
    """Находит рабочий прокси из списка"""
    log.info("🔍 Ищу рабочий прокси...")
    for proxy in PROXY_OPTIONS:
        try:
            log.info(f"📡 Пробую: {proxy}")
            connector = aiohttp.TCPConnector()
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(
                        'https://api.telegram.org',
                        proxy=proxy,
                        timeout=5
                ) as resp:
                    if resp.status == 200:
                        log.info(f"✅ НАЙДЕН РАБОЧИЙ ПРОКСИ: {proxy}")
                        return proxy
        except asyncio.TimeoutError:
            log.warning(f"⏰ Таймаут: {proxy}")
        except Exception as e:
            log.warning(f"❌ Ошибка: {proxy} - {str(e)[:50]}")

    log.error("❌ НЕ НАЙДЕНО РАБОЧЕГО ПРОКСИ!")
    log.info("💡 Проверьте в Karing:")
    log.info("   1. Какой порт указан в настройках?")
    log.info("   2. Включен ли режим 'Все идёт через прокси'?")
    log.info("   3. Попробуйте переключить сервер")
    return None


# ============================================================
# ИМПОРТЫ ХЕНДЛЕРОВ
# ============================================================
from handlers import router
from handlers.chat_member import router as chat_member_router
from handlers.apply_handlers import router as apply_router
from utils.file_utils import ensure_dirs, get_creation_date

ensure_dirs()
get_creation_date()

dp = Dispatcher()
dp.include_router(router)
dp.include_router(chat_member_router)
dp.include_router(apply_router)


# ============================================================
# ПЕРИОДИЧЕСКАЯ СИНХРОНИЗАЦИЯ USERS.TXT
# ============================================================
async def sync_users_periodically(bot: Bot):
    """Фоновая задача: синхронизирует users.txt каждые 30 минут."""
    while True:
        await asyncio.sleep(1800)  # 30 минут
        try:
            from utils.sync_utils import sync_users_with_group
            removed = await sync_users_with_group(bot)
            if removed > 0:
                log.info(f"🔄 Синхронизация: удалено {removed} отсутствующих пользователей")
        except Exception as e:
            log.error(f"❌ Ошибка синхронизации: {e}")


# ============================================================
# ЗАПУСК
# ============================================================
async def main():
    # Ищем рабочий прокси
    working_proxy = await find_working_proxy()
    if not working_proxy:
        log.error("❌ Нет рабочего прокси! Бот не может запуститься.")
        log.info("💡 Решения:")
        log.info("   1. Проверьте Karing (включен?)")
        log.info("   2. Узнайте порт в настройках Karing")
        log.info("   3. Добавьте правильный порт в PROXY_OPTIONS")
        sys.exit(1)

    log.info(f"🔗 Использую прокси: {working_proxy}")

    # Создаем сессию с найденным прокси
    session = AiohttpSession(
        proxy=working_proxy,
        timeout=180
    )

    bot = Bot(token=BOT_TOKEN, session=session)

    # Проверяем подключение
    try:
        me = await bot.get_me()
        log.info("=" * 50)
        log.info("🚀 БОТ УСПЕШНО ЗАПУЩЕН!")
        log.info(f"🤖 @{me.username}")
        log.info(f"🔗 Прокси: {working_proxy}")
        log.info("=" * 50)

        # Запускаем фоновую задачу синхронизации
        asyncio.create_task(sync_users_periodically(bot))
        log.info("🔄 Запущена фоновая синхронизация users.txt (каждые 30 минут)")

        await dp.start_polling(bot)
    except Exception as e:
        log.error(f"❌ Ошибка подключения: {e}")
        raise


# Исправлено: __name__ и "__main__"
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("👋 Бот остановлен")