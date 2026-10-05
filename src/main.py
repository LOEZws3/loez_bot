import sys
import io
import asyncio
import logging
import os
import json
import datetime
import time
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from config import (
    BOT_TOKEN, USE_PROXY, PROXY_DIR,
    DATA_DIR, LOG_FILE_PATH, LOG_LEVEL, LOG_FORMAT,
    ensure_directories, LEFTOVER_FILE, GENERAL_CHAT_ID,
)
from database import db
from handlers import routers
from proxy_manager import proxy_manager
from middlewares import RegistrationCheckMiddleware

class ProxySSLException(Exception):
    pass

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ensure_directories()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE_PATH, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

bot = None
RESTART_DELAY = 5

# ======================== ⚠️ НОВОЕ: leftdata.json ========================

def _save_leftdata(user_id: int, full_name: str, role: str, reason: str = "left"):
    """Сохраняет ушедшего юзера в leftdata.json."""
    try:
        if os.path.exists(LEFTOVER_FILE):
            with open(LEFTOVER_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
        else:
            data = {}

        data[str(user_id)] = {
            'full_name': full_name or f"ID {user_id}",
            'role': role or '',
            'left_at': datetime.datetime.now().isoformat(),
            'reason': reason,
        }

        os.makedirs(os.path.dirname(LEFTOVER_FILE), exist_ok=True)
        with open(LEFTOVER_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"📝 {user_id} добавлен в leftdata.json ({reason})")
    except Exception as e:
        logger.error(f"❌ Ошибка leftdata.json для {user_id}: {e}")

async def create_bot_with_proxy() -> Bot:
    if not USE_PROXY:
        logger.info("ℹ️ Прокси отключены в настройках")
        return Bot(token=BOT_TOKEN)

    from config import PRIORITY_PROXY

    proxy_manager.proxy_dir = PROXY_DIR

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

    session = AiohttpSession(proxy=proxy_url)
    return Bot(token=BOT_TOKEN, session=session)

async def switch_to_next_proxy():
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

        session = AiohttpSession(proxy=proxy_url)
        bot = Bot(token=BOT_TOKEN, session=session)
        logger.info(f"✅ Переключено на прокси: {next_proxy}")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка переключения: {e}")
        return False

async def set_bot_commands():
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
        BotCommand(command="userstats", description="Статистика пользователя (админ)"),
        BotCommand(command="findrole", description="Поиск роли (админ)"),
        # ⚠️ НОВОЕ (05.10.2026)
        BotCommand(command="setbirthday", description="Установить дату рождения"),
        BotCommand(command="subnorm", description="Подписаться на уведомления о норме"),
        BotCommand(command="unsubnorm", description="Отписаться от уведомлений о норме"),
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("📋 Команды бота установлены")
    except Exception as e:
        error_str = str(e).lower()

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
    """Планировщик рестов."""
    global bot
    from utils.role_utils import load_roles_status, save_roles_status

    while True:
        try:
            today = datetime.date.today().isoformat()
            roles = load_roles_status()
            expired = []

            for role_name, role_data in roles.items():
                if not isinstance(role_data, dict):
                    continue
                if role_data.get('status') != 'рест':
                    continue
                extra = role_data.get('extra', '')
                if not extra:
                    continue
                if extra <= today:
                    expired.append(role_name)

            if expired:
                status_data = load_roles_status()
                for role_name in expired:
                    status_data[role_name]['status'] = 'занята'
                    status_data[role_name]['extra'] = ''
                save_roles_status(status_data)
                logger.info(f"🔔 Снято рестов: {len(expired)} — {', '.join(expired)}")

                for role_name in expired:
                    owner_id = status_data[role_name].get('owner_id')
                    if owner_id and bot:
                        try:
                            await bot.send_message(
                                owner_id,
                                f"🔔 <b>Ваш рест закончился!</b>\n\n"
                                f"🎭 Роль: <b>{role_name}</b>\n"
                                f"Теперь вы снова активны.",
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            error_msg = str(e).lower()
                            if "proxy" in error_msg or "connection" in error_msg or "timeout" in error_msg:
                                await switch_to_next_proxy()
        except Exception as e:
            logger.error(f"❌ Ошибка в планировщике рестов: {e}")

        await asyncio.sleep(60)

async def sync_roles_loop():
    """Синхронизация ролей из папки data/roles/*.txt (03:33 МСК)."""
    from utils.role_utils import sync_roles_from_files

    while True:
        try:
            now_utc = datetime.datetime.now(datetime.UTC)
            now_msk = now_utc + datetime.timedelta(hours=3)
            target = now_msk.replace(hour=3, minute=33, second=0, microsecond=0)
            if now_msk >= target:
                target += datetime.timedelta(days=1)
            wait_seconds = (target - now_msk).total_seconds()
            if wait_seconds < 60:
                wait_seconds = 60

            logger.info(f"🔄 Синхронизация ролей: через {int(wait_seconds / 60)} мин")
            await asyncio.sleep(wait_seconds)

            result = sync_roles_from_files()
            logger.info(f"✅ Синхронизация завершена: {result}")
        except Exception as e:
            logger.error(f"❌ Ошибка в синхронизации ролей: {e}")
            await asyncio.sleep(3600)

async def expire_warns_loop():
    """Удаление истёкших варнов (раз в час)."""
    from utils.warns_utils import expire_old_warns

    while True:
        try:
            removed = expire_old_warns()
            if removed > 0:
                logger.info(f"🕐 Удалено истёкших варнов: {removed}")
        except Exception as e:
            logger.error(f"❌ Ошибка в планировщике варнов: {e}")

        await asyncio.sleep(3600)

async def norm_reminder_loop():
    """Напоминание админам о чистке (сб 19:00 МСК)."""
    global bot
    from utils.admin_utils import load_admins
    from config import ADMIN_GROUP_ID

    while True:
        try:
            now_utc = datetime.datetime.now(datetime.UTC)
            now_msk = now_utc + datetime.timedelta(hours=3)
            days_until_saturday = (5 - now_msk.weekday()) % 7
            target = now_msk.replace(hour=19, minute=0, second=0, microsecond=0) + datetime.timedelta(days=days_until_saturday)

            if now_msk >= target:
                target += datetime.timedelta(days=7)

            wait_seconds = (target - now_msk).total_seconds()
            if wait_seconds < 60:
                wait_seconds = 60

            await asyncio.sleep(wait_seconds)

            text = "🕖 <b>19:00 — время чистки!</b>\n\nЗапустите /checknorm чтобы проверить норму."

            sent = False
            if ADMIN_GROUP_ID and bot:
                try:
                    await bot.send_message(ADMIN_GROUP_ID, text, parse_mode="HTML")
                    sent = True
                except Exception as e:
                    logger.error(f"❌ Не удалось отправить в группу: {e}")

            if not sent and bot:
                admins = load_admins()
                for admin in admins:
                    if admin.get('rank') not in [1, 2]:
                        continue
                    try:
                        await bot.send_message(admin['id'], text, parse_mode="HTML")
                    except Exception as e:
                        logger.error(f"❌ Не удалось уведомить {admin['id']}: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка в напоминании о чистке: {e}")
            await asyncio.sleep(3600)

async def norm_reset_loop():
    """Сброс счётчиков (21:00 МСК, с ожиданием чисток)."""
    from utils.counters import reset_all_counters
    from handlers.checknorm_commands import _has_active_sessions

    while True:
        try:
            now_utc = datetime.datetime.now(datetime.UTC)
            now_msk = now_utc + datetime.timedelta(hours=3)
            days_until_saturday = (5 - now_msk.weekday()) % 7
            target_21 = now_msk.replace(hour=21, minute=0, second=0, microsecond=0) + datetime.timedelta(days=days_until_saturday)

            if now_msk >= target_21:
                target_21 += datetime.timedelta(days=7)

            wait_seconds = (target_21 - now_msk).total_seconds()
            if wait_seconds < 60:
                wait_seconds = 60

            await asyncio.sleep(wait_seconds)

            waited = 0
            while _has_active_sessions() and waited < 900:
                logger.info("⏳ Активная чистка — ждём...")
                await asyncio.sleep(60)
                waited += 60

            reset_all_counters()
            logger.info("✅ Счётчики сброшены (21:00 МСК)")
        except Exception as e:
            logger.error(f"❌ Ошибка в сбросе счётчиков: {e}")
            await asyncio.sleep(3600)

async def check_kicked_loop():
    """Проверка кикнутых (раз в минуту). + сохранение в leftdata.json"""
    global bot

    while True:
        try:
            await asyncio.sleep(60)

            if not bot:
                continue

            from utils.user_utils import load_users, remove_user
            from utils.admin_utils import load_admins, save_admins
            from utils.role_utils import load_roles_status, save_roles_status

            users = load_users()
            if not users:
                continue

            kicked = []  # [(uid, full_name, role)]

            for u in users:
                uid = u.get('id')
                if not uid:
                    continue
                try:
                    member = await bot.get_chat_member(GENERAL_CHAT_ID, uid)
                    if member.status in ['left', 'kicked']:
                        reason = 'kicked' if member.status == 'kicked' else 'left'
                        kicked.append((uid, u.get('full_name', ''), u.get('role', ''), reason))
                except Exception:
                    pass
                await asyncio.sleep(0.05)

            if not kicked:
                continue

            for uid, full_name, role, reason in kicked:
                _save_leftdata(uid, full_name, role, reason)
                # ⚠️ НОВОЕ: пишем в users_history
                try:
                    from utils.user_history import set_left
                    set_left(uid, reason)
                except Exception as e:
                    logger.error(f"❌ set_left для {uid}: {e}")
                remove_user(uid)

            kicked_ids = [k[0] for k in kicked]

            admins = load_admins()
            new_admins = [a for a in admins if a['id'] not in kicked_ids]
            if len(new_admins) != len(admins):
                save_admins(new_admins)

            status_data = load_roles_status()
            changed = False
            for role_key, role_info in status_data.items():
                if isinstance(role_info, dict) and role_info.get('owner_id') in kicked_ids:
                    role_info['status'] = 'свободна'
                    role_info['owner_id'] = None
                    role_info['username'] = None
                    changed = True
            if changed:
                save_roles_status(status_data)

            logger.info(f"🧹 Кикнуты/ушли: {kicked_ids}")
        except Exception as e:
            logger.error(f"❌ Ошибка проверки кикнутых: {e}")

# ======================== ⚠️ НОВОЕ: ДНИ РОЖДЕНИЯ ========================

async def _send_birthday_messages(mode: str):
    """
    mode = 'personal' (00:00 ЛС) или 'group' (12:00 во флуд).
    """
    global bot

    if not bot:
        return

    try:
        now_utc = datetime.datetime.now(datetime.UTC)
        now_msk = now_utc + datetime.timedelta(hours=3)
        day = now_msk.day
        month = now_msk.month

        from utils.user_utils import get_users_with_birthday
        users = get_users_with_birthday(day, month)

        if not users:
            return

        logger.info(f"🎂 ДР сегодня у {len(users)}: {[u['id'] for u in users]}")

        if mode == 'personal':
            # ЛС каждому
            for u in users:
                try:
                    await bot.send_message(
                        u['id'],
                        f"🎂 <b>Поздравляю вас с вашим днём рождения, {u['full_name']}!</b>\n\n"
                        f"Желаем удачи!\n\n"
                        f"— LOeZ team",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"❌ ЛС {u['id']}: {e}")

        elif mode == 'group':
            # Одно сообщение во флуд со всеми
            lines = []
            for u in users:
                role = u.get('role') or ''
                if role and role != '0':
                    lines.append(f"• {u['full_name']} ({role})")
                else:
                    lines.append(f"• {u['full_name']}")

            text = (
                "🎂 <b>Сегодня день рождения у:</b>\n\n"
                + "\n".join(lines)
                + "\n\n🎉 Поздравляем!"
            )
            try:
                await bot.send_message(GENERAL_CHAT_ID, text, parse_mode="HTML")
            except Exception as e:
                logger.error(f"❌ Поздравление во флуд: {e}")

    except Exception as e:
        logger.error(f"❌ Ошибка ДР ({mode}): {e}")

async def birthday_personal_loop():
    """ЛС-поздравления в 00:00 МСК."""
    while True:
        try:
            now_utc = datetime.datetime.now(datetime.UTC)
            now_msk = now_utc + datetime.timedelta(hours=3)
            target = now_msk.replace(hour=0, minute=0, second=0, microsecond=0)
            if now_msk >= target:
                target += datetime.timedelta(days=1)
            wait = (target - now_msk).total_seconds()
            if wait < 60:
                wait = 60
            logger.info(f"🎂 ЛС-поздравления через {int(wait/60)} мин (00:00 МСК)")
            await asyncio.sleep(wait)
            await _send_birthday_messages('personal')
        except Exception as e:
            logger.error(f"❌ birthday_personal_loop: {e}")
            await asyncio.sleep(3600)

async def birthday_group_loop():
    """Поздравление во флуд в 12:00 МСК."""
    while True:
        try:
            now_utc = datetime.datetime.now(datetime.UTC)
            now_msk = now_utc + datetime.timedelta(hours=3)
            target = now_msk.replace(hour=12, minute=0, second=0, microsecond=0)
            if now_msk >= target:
                target += datetime.timedelta(days=1)
            wait = (target - now_msk).total_seconds()
            if wait < 60:
                wait = 60
            logger.info(f"🎂 Поздравление во флуд через {int(wait/60)} мин (12:00 МСК)")
            await asyncio.sleep(wait)
            await _send_birthday_messages('group')
        except Exception as e:
            logger.error(f"❌ birthday_group_loop: {e}")
            await asyncio.sleep(3600)

# ======================== RUN ========================

async def run_bot():
    global bot
    dp = Dispatcher()
    dp.message.middleware(RegistrationCheckMiddleware())
    logger.info("✅ Middleware стартового режима подключен")

    for router in routers:
        dp.include_router(router)
    logger.info(f"✅ Зарегистрировано {len(routers)} роутеров")

    while True:
        try:
            if bot is None:
                bot = await create_bot_with_proxy()
            await on_startup()
            try:
                await dp.start_polling(bot, skip_updates=True)
            except ProxySSLException as ssl_error:
                logger.error(f"❌ SSL: {ssl_error}")
                try:
                    from proxy_manager import clear_pings_cache
                    clear_pings_cache()
                except Exception:
                    pass
                if await switch_to_next_proxy():
                    await asyncio.sleep(2)
                    continue
                else:
                    await asyncio.sleep(RESTART_DELAY)
                    bot = None
                    continue
            except Exception as e:
                logger.error(f"❌ Критическая ошибка: {e}")
                error_msg = str(e).lower()
                if ("connection" in error_msg or "timeout" in error_msg or "proxy" in error_msg) and USE_PROXY:
                    if await switch_to_next_proxy():
                        continue
                raise
            finally:
                if bot and bot.session:
                    await bot.session.close()
            break
        except ProxySSLException as ssl_error:
            logger.error(f"❌ SSL: {ssl_error}")
            try:
                from proxy_manager import clear_pings_cache
                clear_pings_cache()
            except Exception:
                pass
            if await switch_to_next_proxy():
                await asyncio.sleep(2)
                continue
            else:
                await asyncio.sleep(RESTART_DELAY)
                bot = None
                continue
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            await asyncio.sleep(RESTART_DELAY)
            bot = None
            continue

async def on_startup():
    logger.info("🚀 Запуск...")
    await db.init()

    try:
        from utils.role_utils import sync_roles_from_files
        result = sync_roles_from_files()
        logger.info(f"🔄 Синхронизация ролей: {result}")
    except Exception as e:
        logger.error(f"❌ Ошибка синхронизации: {e}")

    asyncio.create_task(check_rests_loop())
    logger.info("🔄 check_rests_loop запущен")
    asyncio.create_task(sync_roles_loop())
    logger.info("🔄 sync_roles_loop запущен (03:33 МСК)")
    asyncio.create_task(expire_warns_loop())
    logger.info("🔄 expire_warns_loop запущен (раз в час)")
    asyncio.create_task(norm_reminder_loop())
    logger.info("🔄 norm_reminder_loop запущен (сб 19:00 МСК)")
    asyncio.create_task(norm_reset_loop())
    logger.info("🔄 norm_reset_loop запущен (сб 21:00 МСК)")
    asyncio.create_task(check_kicked_loop())
    logger.info("🔄 check_kicked_loop запущен (раз в мин)")
    # ⚠️ НОВОЕ:
    asyncio.create_task(birthday_personal_loop())
    logger.info("🔄 birthday_personal_loop запущен (00:00 МСК)")
    asyncio.create_task(birthday_group_loop())
    logger.info("🔄 birthday_group_loop запущен (12:00 МСК)")

    await set_bot_commands()
    logger.info("✅ Бот запущен!")

async def main():
    global bot
    try:
        await run_bot()
    except KeyboardInterrupt:
        logger.info("🛑 Остановлен")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Остановлен")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        raise