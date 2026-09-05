import sys
import io
import asyncio
import logging
import os
import ssl
import aiohttp
from aiohttp import ClientTimeout
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from config import BOT_TOKEN, USE_PROXY, PROXY_DIR
from database import db
from handlers import routers
from proxy_manager import proxy_manager

# Исправление кодировки для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Создаём папку для логов
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'bot.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Глобальная переменная для бота
bot = None


def create_ssl_context():
    """Создаёт SSL-контекст с отключённой проверкой сертификатов"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context


async def create_bot_with_session(proxy_url: str) -> Bot:
    """Создаёт бота с заданным прокси и таймаутом 30 секунд"""
    ssl_context = create_ssl_context()
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    
    # ✅ Таймаут 30 секунд
    timeout = ClientTimeout(
        total=30,
        connect=30,
        sock_read=30
    )
    
    aiohttp_session = aiohttp.ClientSession(
        connector=connector,
        timeout=timeout,
        trust_env=True
    )
    
    session = AiohttpSession()
    session._session = aiohttp_session
    
    bot = Bot(token=BOT_TOKEN, session=session)
    bot._aiohttp_session = aiohttp_session
    bot._proxy_url = proxy_url
    
    return bot


async def create_bot_with_proxy() -> Bot:
    """Создаёт экземпляр бота с самым быстрым прокси"""
    if not USE_PROXY:
        logger.info("ℹ️ Прокси отключены в настройках")
        return Bot(token=BOT_TOKEN)
    
    proxy_manager.proxy_dir = PROXY_DIR
    count = proxy_manager.load_proxies()
    
    if count == 0:
        logger.warning("⚠️ Нет доступных прокси, работаем без прокси")
        return Bot(token=BOT_TOKEN)
    
    fastest_proxy = await proxy_manager.get_fastest_proxy()
    
    if not fastest_proxy:
        logger.warning("⚠️ Не удалось найти рабочий прокси, работаем без прокси")
        return Bot(token=BOT_TOKEN)
    
    proxy_url = proxy_manager.format_proxy(fastest_proxy)
    ping = proxy_manager.proxy_pings.get(fastest_proxy, 0)
    logger.info(f"🌐 Используется прокси: {proxy_url} (пинг: {ping:.3f}с)")
    
    return await create_bot_with_session(proxy_url)


async def reconnect_with_next_proxy():
    """Переподключается к следующему по пингу прокси"""
    global bot
    
    if not USE_PROXY:
        return False
    
    current = proxy_manager.get_current_proxy()
    if current:
        proxy_manager.mark_proxy_bad(current)
        logger.info(f"❌ Прокси {current} помечен как нерабочий")
    
    proxy = proxy_manager.get_next_fastest_proxy()
    if not proxy:
        logger.warning("⚠️ Нет доступных прокси, работаем без прокси")
        bot = Bot(token=BOT_TOKEN)
        return False
    
    proxy_url = proxy_manager.format_proxy(proxy)
    ping = proxy_manager.proxy_pings.get(proxy, 0)
    logger.info(f"🔄 Переключение на прокси: {proxy_url} (пинг: {ping:.3f}с)")
    
    try:
        if bot and bot.session:
            await bot.session.close()
        if hasattr(bot, '_aiohttp_session'):
            await bot._aiohttp_session.close()
        
        bot = await create_bot_with_session(proxy_url)
        
        await bot.me()
        logger.info(f"✅ Успешно переключено на прокси: {proxy_url}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Новый прокси {proxy_url} тоже не работает: {e}")
        return await reconnect_with_next_proxy()


async def set_bot_commands():
    """Установка команд для меню бота"""
    commands = [
        BotCommand(command="start", description="Приветствие"),
        BotCommand(command="help", description="Справка"),
        BotCommand(command="about", description="Информация о флуд-чате"),
        BotCommand(command="aboutme", description="Ваши данные"),
        BotCommand(command="members", description="Список участников"),
        BotCommand(command="roles", description="Список ролей"),
        BotCommand(command="apply", description="Подать заявку"),
        BotCommand(command="free", description="Освободить роль"),
        BotCommand(command="rest", description="Подать заявку на рест"),
        BotCommand(command="cancel_request", description="Отменить заявку"),
        BotCommand(command="regc", description="Подписаться на калы"),
        BotCommand(command="unregc", description="Отписаться от калов"),
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("📋 Команды бота установлены")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось установить команды бота: {e}")


async def check_rests_loop():
    """Планировщик проверки рестов каждую минуту"""
    global bot
    while True:
        try:
            expired = await db.check_expired_rests()
            for role in expired:
                if role['owner_id'] and bot:
                    try:
                        await bot.send_message(
                            role['owner_id'],
                            f"🔔 Ваш рест для роли **{role['name']}** закончился! Теперь вы снова активны.",
                            parse_mode="Markdown"
                        )
                        logger.info(f"✅ Уведомление о снятии реста отправлено пользователю {role['owner_id']}")
                    except Exception as e:
                        error_msg = str(e).lower()
                        if "proxy" in error_msg or "connection" in error_msg or "timeout" in error_msg:
                            logger.warning(f"⚠️ Ошибка прокси, меняем: {str(e)[:100]}")
                            await reconnect_with_next_proxy()
                        else:
                            logger.error(f"❌ Не удалось уведомить пользователя {role['owner_id']}: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка в планировщике: {e}")
        
        await asyncio.sleep(60)


async def on_startup():
    """Действия при запуске бота"""
    logger.info("🚀 Запуск бота...")
    
    await db.init()
    logger.info("✅ База данных инициализирована")
    
    asyncio.create_task(check_rests_loop())
    logger.info("🔄 Планировщик рестов запущен")
    
    await set_bot_commands()
    logger.info("📋 Команды бота установлены")
    
    logger.info("✅ Бот успешно запущен!")


async def main():
    """Главная функция запуска бота"""
    global bot
    
    bot = await create_bot_with_proxy()
    
    dp = Dispatcher()
    
    for router in routers:
        dp.include_router(router)
    logger.info(f"✅ Зарегистрировано {len(routers)} роутеров")
    
    await on_startup()
    
    try:
        logger.info("🔄 Начинаю поллинг...")
        await dp.start_polling(bot, skip_updates=True)
    except TelegramNetworkError as e:
        logger.error(f"❌ Ошибка сети: {e}")
        if USE_PROXY:
            logger.info("🔄 Пробую переключить прокси...")
            await reconnect_with_next_proxy()
            logger.info("🔄 Перезапускаю поллинг...")
            await dp.start_polling(bot, skip_updates=True)
        else:
            raise
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        error_msg = str(e).lower()
        if ("connection" in error_msg or "timeout" in error_msg or "proxy" in error_msg) and USE_PROXY:
            logger.info("🔄 Пробую переключить прокси...")
            await reconnect_with_next_proxy()
            logger.info("🔄 Перезапускаю поллинг...")
            await dp.start_polling(bot, skip_updates=True)
        else:
            raise
    finally:
        if hasattr(bot, '_aiohttp_session'):
            await bot._aiohttp_session.close()
        await bot.session.close()
        logger.info("🛑 Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Необработанная ошибка: {e}")
        raise