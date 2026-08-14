import asyncio
import logging
import sys
import datetime
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
# ПРОКСИ - ПРОВЕРЯЕМ РАЗНЫЕ ПОРТЫ (НЕ МЕНЯТЬ!)
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
# Обратите внимание: убедитесь, что имена импортов совпадают с вашей структурой папок
try:
    from handlers.commands import router as commands_router
    from handlers.chat_member import router as chat_member_router
    from handlers.apply_handlers import router as apply_router
    # Импорт функции проверки рестов
    from handlers.commands import check_expired_rests
except ImportError as e:
    log.error(f"❌ Ошибка импорта модулей: {e}")
    sys.exit(1)

from utils.file_utils import ensure_dirs, get_creation_date
from utils.sync_utils import sync_users_with_group
from utils.user_utils import load_users, sync_unsubscribed_with_users

ensure_dirs()
get_creation_date()

dp = Dispatcher()
dp.include_router(commands_router)
dp.include_router(chat_member_router)
dp.include_router(apply_router)


# ============================================================
# ПЕРИОДИЧЕСКАЯ СИНХРОНИЗАЦИЯ И ПРОВЕРКИ
# ============================================================

async def periodic_sync_and_checks(bot: Bot):
    """Фоновая задача: синхронизирует пользователей, отписки и проверяет ресты."""
    while True:
        await asyncio.sleep(1800)  # 30 минут
        try:
            # 1. Синхронизация users.txt
            removed = await sync_users_with_group(bot)
            if removed > 0:
                log.info(f"🔄 Синхронизация: удалено {removed} отсутствующих пользователей")

            # 2. Синхронизация отписок от калов
            users = load_users()
            user_ids = [u['id'] for u in users]
            unsub_removed = sync_unsubscribed_with_users(user_ids)
            if unsub_removed > 0:
                log.info(f"🔄 Синхронизация отписок: очищено {unsub_removed} записей")

            # 3. Проверка истекших рестов (дополнительно к расписанию ниже, для надежности)
            now = datetime.datetime.now()
            if now.hour == 0 and now.minute == 0:
                log.info("⏰ Проверка рестов (в рамках синхронизации)")
                await check_expired_rests(bot)

        except Exception as e:
            log.error(f"❌ Ошибка в фоновой задаче: {e}")


async def schedule_rests_check(bot: Bot):
    """Отдельная задача для точного времени проверки рестов (Суббота 18:00)."""
    while True:
        now = datetime.datetime.now()
        # Проверка каждый день в 00:00
        if now.hour == 0 and now.minute == 0:
            log.info("⏰ Время проверки истекших рестов (ежедневная)")
            await check_expired_rests(bot)
        # Дополнительная проверка в субботу в 18:00
        elif now.weekday() == 5 and now.hour == 18 and now.minute == 0:  # 5 = Суббота
            log.info("⏰ Время проверки истекших рестов (субботняя)")
            await check_expired_rests(bot)

        await asyncio.sleep(60)  # Проверяем каждую минуту


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

        # Запускаем фоновые задачи
        asyncio.create_task(periodic_sync_and_checks(bot))
        asyncio.create_task(schedule_rests_check(bot))

        log.info("🔄 Запущены фоновые задачи: синхронизация и проверка рестов")

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