import sys
import io
import asyncio
import logging
import os
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
RESTART_DELAY = 5
# ✅ Храним уже использованные прокси, чтобы не возвращаться к ним
used_proxies = set()


def clean_proxy(proxy: str) -> str:
    """Очищает прокси от лишних данных (дат, пробелов)"""
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


async def create_bot_with_proxy(proxy: str = None) -> Bot:
    """Создаёт экземпляр бота с прокси"""
    global used_proxies
    
    if not USE_PROXY:
        logger.info("ℹ️ Прокси отключены в настройках")
        return Bot(token=BOT_TOKEN)
    
    if proxy is None:
        proxy_manager.proxy_dir = PROXY_DIR
        count = proxy_manager.load_proxies()
        
        if count == 0:
            logger.warning("⚠️ Нет доступных прокси, работаем без прокси")
            return Bot(token=BOT_TOKEN)
        
        # ✅ Пропускаем уже использованные прокси
        max_attempts = 20
        attempts = 0
        while attempts < max_attempts:
            proxy = proxy_manager.get_next_proxy()
            if not proxy:
                break
            clean = clean_proxy(proxy)
            if clean and clean not in used_proxies:
                break
            attempts += 1
            logger.info(f"⏭️ Пропускаем уже использованный прокси: {clean}")
        
        if not proxy:
            logger.warning("⚠️ Не удалось найти новый прокси, работаем без прокси")
            return Bot(token=BOT_TOKEN)
    
    clean = clean_proxy(proxy)
    if not clean:
        logger.warning(f"⚠️ Прокси {proxy} невалидный, пропускаем")
        if proxy_manager.proxies:
            proxy_manager.mark_proxy_bad(proxy)
        return await create_bot_with_proxy()
    
    proxy_url = proxy_manager.format_proxy(clean)
    logger.info(f"🌐 Используется прокси: {proxy_url}")
    
    session = AiohttpSession(proxy=proxy_url)
    return Bot(token=BOT_TOKEN, session=session)


async def switch_to_next_proxy():
    """Переключается на следующий прокси"""
    global bot, used_proxies
    
    if not USE_PROXY:
        return False
    
    current = proxy_manager.get_current_proxy()
    if current:
        clean = clean_proxy(current)
        if clean:
            used_proxies.add(clean)
            logger.info(f"❌ Прокси {clean} добавлен в список использованных")
        proxy_manager.mark_proxy_bad(current)
        logger.info(f"❌ Прокси {current} помечен как нерабочий")
    
    # ✅ Пропускаем уже использованные прокси
    max_attempts = 20
    attempts = 0
    next_proxy = None
    while attempts < max_attempts:
        next_proxy = proxy_manager.get_next_proxy()
        if not next_proxy:
            break
        clean = clean_proxy(next_proxy)
        if clean and clean not in used_proxies:
            break
        attempts += 1
        logger.info(f"⏭️ Пропускаем уже использованный прокси: {clean}")
        proxy_manager.mark_proxy_bad(next_proxy)
    
    if not next_proxy:
        logger.warning("⚠️ Нет доступных новых прокси, работаем без прокси")
        bot = Bot(token=BOT_TOKEN)
        return False
    
    clean = clean_proxy(next_proxy)
    if not clean:
        logger.warning(f"⚠️ Прокси {next_proxy} невалидный, пропускаем")
        return await switch_to_next_proxy()
    
    try:
        if bot and bot.session:
            await bot.session.close()
        
        bot = await create_bot_with_proxy(clean)
        logger.info(f"✅ Переключено на прокси: {clean}")
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
        # ✅ Игнорируем ошибку 400 Bad Request (команды уже установлены)
        if "400" in str(e):
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
    global bot, used_proxies
    
    # Создаём диспетчер один раз
    dp = Dispatcher()
    
    # Регистрируем роутеры один раз
    for router in routers:
        dp.include_router(router)
    logger.info(f"✅ Зарегистрировано {len(routers)} роутеров")
    
    while True:
        try:
            # ✅ Сбрасываем список использованных прокси при каждом запуске
            used_proxies = set()
            
            if bot is None:
                bot = await create_bot_with_proxy()
            
            await on_startup()
            
            try:
                logger.info("🔄 Начинаю поллинг...")
                await dp.start_polling(bot, skip_updates=True)
            except TelegramNetworkError as e:
                logger.error(f"❌ Ошибка сети: {e}")
                if USE_PROXY:
                    logger.info("🔄 Пробую переключить прокси...")
                    if await switch_to_next_proxy():
                        logger.info("🔄 Перезапускаю поллинг...")
                        continue
                    else:
                        raise
                else:
                    raise
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
                
        except Exception as e:
            logger.error(f"❌ Необработанная ошибка: {e}")
            logger.info(f"⏳ Перезапуск через {RESTART_DELAY} секунд...")
            await asyncio.sleep(RESTART_DELAY)
            # При перезапуске создаём нового бота
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