import sys
import io
import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from config import (
    BOT_TOKEN, USE_PROXY, PROXY_DIR,
    DATA_DIR, LOG_FILE_PATH, LOG_LEVEL, LOG_FORMAT,
    ensure_directories,
)
from database import db
from handlers import routers
from proxy_manager import proxy_manager

# ═══════════════════════════════════════════════════════════════════
# КЛАСС ИСКЛЮЧЕНИЯ ДЛЯ SSL-ОШИБОК ПРОКСИ
# ═══════════════════════════════════════════════════════════════════

class ProxySSLException(Exception):
    """Исключение для SSL-ошибок при работе через прокси"""
    pass

# ═══════════════════════════════════════════════════════════════════
# ⚠️  ВАЖНОЕ ПРЕДУПРЕЖДЕНИЕ О СИСТЕМЕ ПОДКЛЮЧЕНИЯ
# ═══════════════════════════════════════════════════════════════════
# 
#  Данная система подключения (AiohttpSession(proxy=proxy_url))
#  является РАБОЧЕЙ и СТАБИЛЬНОЙ.
# 
#  ЗАПРЕЩАЕТСЯ:
#  1. Добавлять connector, ssl_context или другие параметры в AiohttpSession
#  2. Использовать aiohttp.ClientSession для подмены сессии
#  3. Менять способ создания сессии на любой другой
# 
#  Причина: все попытки "улучшить" подключение приводили к ошибкам:
#  - BaseSession.__init__() got an unexpected keyword argument
#  - SSL: CERTIFICATE_VERIFY_FAILED
#  - ProxyConnectionError
# 
#  ЕСЛИ ВАМ КАЖЕТСЯ, ЧТО НУЖНО ЧТО-ТО ИЗМЕНИТЬ — 
#  СНАЧАЛА ПРОВЕРЬТЕ РАБОТОСПОСОБНОСТЬ НА ТЕСТОВОМ БОТЕ!
# 
#  Рабочая версия: aiogram 3.17+, aiohttp 3.8.5
#  Дата проверки: 13.09.2026
# ═══════════════════════════════════════════════════════════════════

# Исправление кодировки для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ✅ Гарантируем, что все папки существуют (включая data/logs)
ensure_directories()

# ✅ Настройка логирования с АБСОЛЮТНЫМ путём к data/logs/bot.log
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE_PATH, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Глобальная переменная для бота
bot = None
RESTART_DELAY = 5


async def create_bot_with_proxy() -> Bot:
    """
    Создаёт экземпляр бота с прокси.
    
    ⚠️ НЕ МЕНЯТЬ СПОСОБ ПОДКЛЮЧЕНИЯ!
    Используется только AiohttpSession(proxy=proxy_url).
    Любые другие варианты (connector, ssl_context, ClientSession) — ЗАПРЕЩЕНЫ!
    """
    if not USE_PROXY:
        logger.info("ℹ️ Прокси отключены в настройках")
        return Bot(token=BOT_TOKEN)
    
    from config import PRIORITY_PROXY

    proxy_manager.proxy_dir = PROXY_DIR

    # ✅ Приоритетный прокси
    if PRIORITY_PROXY:
        proxy_manager.priority_proxy = PRIORITY_PROXY
        logger.info(f"⭐ Приоритетный прокси: {PRIORITY_PROXY}")
    else:
        logger.info("ℹ️ Приоритетный прокси не задан — пингование всех")

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
    
    # ✅ ЕДИНСТВЕННОЕ РАБОЧЕЕ ПОДКЛЮЧЕНИЕ — НЕ ТРОГАТЬ!
    session = AiohttpSession(proxy=proxy_url)
    return Bot(token=BOT_TOKEN, session=session)


async def switch_to_next_proxy():
    """
    Переключается на следующий по пингу прокси.
    
    ⚠️ НЕ МЕНЯТЬ СПОСОБ ПОДКЛЮЧЕНИЯ!
    """
    global bot
    
    if not USE_PROXY:
        return False
    
    current = proxy_manager.get_current_proxy()
    if current:
        proxy_manager.mark_proxy_used(current)
        proxy_manager.mark_proxy_bad(current)
        logger.info(f"❌ Прокси {current} помечен как нерабочий")
    
    next_proxy = proxy_manager.get_next_fastest_proxy()
    if not next_proxy:
        logger.warning("⚠️ Нет доступных прокси, работаем без прокси")
        bot = Bot(token=BOT_TOKEN)
        return False
    
    try:
        if bot and bot.session:
            await bot.session.close()
        
        proxy_url = proxy_manager.format_proxy(next_proxy)
        ping = proxy_manager.proxy_pings.get(next_proxy, 0)
        logger.info(f"🔄 Переключение на прокси: {proxy_url} (пинг: {ping:.3f}с)")
        
        # ✅ ЕДИНСТВЕННОЕ РАБОЧЕЕ ПОДКЛЮЧЕНИЕ — НЕ ТРОГАТЬ!
        session = AiohttpSession(proxy=proxy_url)
        bot = Bot(token=BOT_TOKEN, session=session)
        logger.info(f"✅ Переключено на прокси: {next_proxy}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка переключения: {e}")
        return False


async def set_bot_commands():
    """Установка команд для меню бота"""
    commands = [
        BotCommand(command="start", description="Приветствие"),
        BotCommand(command="help", description="Справка"),
        BotCommand(command="about", description="Информация о флуд-чате"),
        BotCommand(command="aboutme", description="Ваши данные"),
        BotCommand(command="members", description="Список участников"),
        BotCommand(command="roles", description="Список ролей"),
        BotCommand(command="apply", description="Подать заявку (ТОЛЬКО В ЛС)"),
        BotCommand(command="free", description="Освободить роль (ТОЛЬКО В ЛС)"),
        BotCommand(command="rest", description="Подать заявку на рест (ТОЛЬКО В ЛС)"),
        BotCommand(command="cancel_request", description="Отменить заявку (ТОЛЬКО В ЛС)"),
        BotCommand(command="regc", description="Подписаться на калы"),
        BotCommand(command="unregc", description="Отписаться от калов"),
        BotCommand(command="update", description="Обновить данные / зарегистрироваться"),
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("📋 Команды бота установлены")
    except Exception as e:
        error_str = str(e).lower()
        
        # ✅ SSL-ОШИБКА — ВЫБРАСЫВАЕМ ИСКЛЮЧЕНИЕ ДЛЯ ПЕРЕЗАПУСКА
        is_ssl_error = (
            'ssl' in error_str or
            'certificate' in error_str or
            'certificate_verify_failed' in error_str or
            'clientoserror' in error_str
        )
        
        if is_ssl_error:
            logger.warning(f"⚠️ SSL-ошибка при установке команд: {e}")
            raise ProxySSLException(f"SSL error: {e}")
        elif "400" in str(e):
            logger.info("📋 Команды уже установлены (пропускаем)")
        else:
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
                            logger.warning(f"⚠️ Ошибка прокси, переключаюсь...")
                            await switch_to_next_proxy()
                        else:
                            logger.error(f"❌ Не удалось уведомить пользователя {role['owner_id']}: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка в планировщике: {e}")
        
        await asyncio.sleep(60)


async def run_bot():
    """Запускает бота с текущим прокси"""
    global bot

    dp = Dispatcher()

    for router in routers:
        dp.include_router(router)
    logger.info(f"✅ Зарегистрировано {len(routers)} роутеров")

    while True:
        try:
            if bot is None:
                bot = await create_bot_with_proxy()

            await on_startup()

            try:
                logger.info("🔄 Начинаю поллинг...")
                await dp.start_polling(bot, skip_updates=True)
            except ProxySSLException as ssl_error:
                # ✅ ОБРАБОТКА SSL-ОШИБКИ — СБРОС КЭША + ПЕРЕКЛЮЧЕНИЕ ПРОКСИ
                logger.error(f"❌ SSL-ошибка прокси: {ssl_error}")
                logger.info("🗑️ Сбрасываю кэш прокси...")
                
                try:
                    from proxy_manager import clear_pings_cache
                    clear_pings_cache()
                except Exception as cache_error:
                    logger.error(f"❌ Ошибка сброса кэша: {cache_error}")
                
                logger.info("🔄 Переключаюсь на следующий прокси...")
                if await switch_to_next_proxy():
                    logger.info("🔄 Перезапускаю бота с новым прокси...")
                    await asyncio.sleep(2)
                    continue
                else:
                    logger.warning("⚠️ Не удалось переключить прокси. Перезапуск через 5 сек...")
                    await asyncio.sleep(RESTART_DELAY)
                    bot = None
                    continue
            except Exception as e:
                logger.error(f"❌ Критическая ошибка в поллинге: {e}")
                error_msg = str(e).lower()
                if ("connection" in error_msg or "timeout" in error_msg or "proxy" in error_msg) and USE_PROXY:
                    logger.info("🔄 Пробую переключить прокси...")
                    if await switch_to_next_proxy():
                        logger.info("🔄 Перезапускаю поллинг...")
                        continue
                raise
            finally:
                if bot and bot.session:
                    await bot.session.close()
                logger.info("🛑 Бот остановлен")
            break

        except ProxySSLException as ssl_error:
            # ✅ ОБРАБОТКА SSL-ОШИБКИ НА УРОВНЕ RUN_BOT (если выброшена из on_startup)
            logger.error(f"❌ SSL-ошибка: {ssl_error}")
            logger.info("🗑️ Сбрасываю кэш прокси...")
            
            try:
                from proxy_manager import clear_pings_cache
                clear_pings_cache()
            except Exception as cache_error:
                logger.error(f"❌ Ошибка сброса кэша: {cache_error}")
            
            logger.info("🔄 Переключаюсь на следующий прокси...")
            if await switch_to_next_proxy():
                logger.info("🔄 Перезапускаю бота...")
                await asyncio.sleep(2)
                continue
            else:
                logger.warning("⚠️ Не удалось переключить прокси. Жду 5 сек...")
                await asyncio.sleep(RESTART_DELAY)
                bot = None
                continue

        except Exception as e:
            logger.error(f"❌ Необработанная ошибка: {e}")
            logger.info(f"⏳ Перезапуск через {RESTART_DELAY} секунд...")
            await asyncio.sleep(RESTART_DELAY)
            bot = None
            continue


async def on_startup():
    """Действия при запуске бота"""
    logger.info("🚀 Запуск бота...")
    
    await db.init()
    logger.info("✅ База данных инициализирована")
    
    asyncio.create_task(check_rests_loop())
    logger.info("🔄 Планировщик рестов запущен")
    
    await set_bot_commands()
    
    logger.info("✅ Бот успешно запущен!")


async def main():
    """Главная функция запуска бота"""
    global bot
    
    try:
        await run_bot()
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Необработанная ошибка: {e}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Необработанная ошибка: {e}")
        raise
