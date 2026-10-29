import sys
import io
import asyncio
import logging
import os
import json
import datetime
import re
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.types import ErrorEvent

# ⚠️ НОВОЕ: Импорт для системных уведомлений Windows
try:
    from winotify import Notification, audio
except ImportError:
    Notification = None
    audio = None

from config import (
    BOT_TOKEN, USE_PROXY, PROXY_DIR,
    DATA_DIR, LOG_FILE_PATH, LOG_LEVEL, LOG_FORMAT,
    ensure_directories, LEFTOVER_FILE, GENERAL_CHAT_ID, ADMIN_GROUP_ID
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

# ======================== ЛОГИРОВАНИЕ ========================
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE_PATH, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ⚠️ НОВОЕ: Логгер только для ошибок (errors.txt)
error_log_path = os.path.join(DATA_DIR, 'logs', 'errors.txt')
os.makedirs(os.path.dirname(error_log_path), exist_ok=True)
error_logger = logging.getLogger('errors')
error_logger.setLevel(logging.ERROR)
error_logger.propagate = False
error_handler = logging.FileHandler(error_log_path, encoding='utf-8')
error_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(exc_info)s'))
error_logger.addHandler(error_handler)

bot = None
RESTART_DELAY = 5
_background_tasks = []  # ⚠️ НОВОЕ: Храним ссылки на таски, чтобы не плодить дубли


# ======================== ⚠️ МАСКИРОВКА ПАРОЛЕЙ В ЛОГАХ ========================
def _mask_proxy(proxy_url: str) -> str:
    """Маскирует логин:пароль в URL прокси."""
    if not proxy_url:
        return proxy_url
    # Заменяем user:pass@host на ***:***@host
    return re.sub(r'://[^:]+:[^@]+@', '://***:***@', proxy_url)


# ======================== leftdata.json ========================
def _save_leftdata(user_id: int, full_name: str, role: str, reason: str = "left"):
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
    from config import PRIORITY_PROXY, PRIORITY_PROXY_FALSE_PROTOCOL, PRIORITY_PROXY_FALSE_PROTOCOL_2

    if not USE_PROXY:
        proxies = []
        if PRIORITY_PROXY_FALSE_PROTOCOL:
            proxies.append(PRIORITY_PROXY_FALSE_PROTOCOL)
        if PRIORITY_PROXY_FALSE_PROTOCOL_2:
            proxies.append(PRIORITY_PROXY_FALSE_PROTOCOL_2)

        if not proxies:
            logger.info("ℹ️ Прокси отключены — прямое подключение")
            return Bot(token=BOT_TOKEN)

        for proxy_url in proxies:
            logger.info(f"🌐 Пробуем прокси: {_mask_proxy(proxy_url)}")
            try:
                session = AiohttpSession(proxy=proxy_url)
                test_bot = Bot(token=BOT_TOKEN, session=session)
                await test_bot.get_me()
                logger.info(f"✅ Прокси работает: {_mask_proxy(proxy_url)}")
                return test_bot
            except Exception as e:
                logger.warning(f"⚠️ Прокси {_mask_proxy(proxy_url)} не работает: {e}")
                try:
                    await test_bot.session.close()
                except Exception:
                    pass

        logger.warning("⚠️ Все прокси не работают — прямое подключение")
        return Bot(token=BOT_TOKEN)

    # ======================== ЛОГИКА ДЛЯ USE_PROXY=TRUE ========================
    proxy_manager.proxy_dir = PROXY_DIR

    if PRIORITY_PROXY:
        proxy_manager.priority_proxy = PRIORITY_PROXY
        logger.info(f"⭐ Приоритетный прокси: {_mask_proxy(PRIORITY_PROXY)}")
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
    logger.info(f"🌐 Используется прокси: {_mask_proxy(proxy_url)} (пинг: {ping:.3f}с)")

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
        logger.info(f"❌ Прокси {_mask_proxy(current)} помечен как нерабочий")

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
        logger.info(f"🔄 Переключение на прокси: {_mask_proxy(proxy_url)} (пинг: {ping:.3f}с)")

        session = AiohttpSession(proxy=proxy_url)
        bot = Bot(token=BOT_TOKEN, session=session)
        logger.info(f"✅ Переключено на прокси: {_mask_proxy(next_proxy)}")
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


# ======================== ФОНОВЫЕ ЦИКЛЫ ========================

async def check_rests_loop():
    global bot
    from utils.role_utils import load_roles_status, save_roles_status
    from utils.user_utils import load_users, set_rest_status, get_user_by_id

    while True:
        try:
            today = datetime.date.today().isoformat()
            users = load_users()
            expired_rest_users = []

            for u in users:
                uid = u.get('id')
                if not uid:
                    continue
                if u.get('rest') and u.get('rest_end_date'):
                    if u['rest_end_date'] <= today:
                        expired_rest_users.append(uid)

            if expired_rest_users:
                for uid in expired_rest_users:
                    set_rest_status(uid, False)
                    logger.info(f"🔔 Рест снят у юзера {uid} (истекла дата)")

                status_data = load_roles_status()
                changed = False
                for role_key, role_info in status_data.items():
                    if not isinstance(role_info, dict):
                        continue
                    owner_id = role_info.get('owner_id')
                    if owner_id in expired_rest_users and role_info.get('status') == 'рест':
                        role_info['status'] = 'занята'
                        role_info['extra'] = ''
                        changed = True

                if changed:
                    save_roles_status(status_data)
                    logger.info(f"🔔 В roles_status.json обновлены роли для {len(expired_rest_users)} юзеров")

                if bot:
                    for uid in expired_rest_users:
                        try:
                            import html
                            role_name = "ваша роль"
                            for role_key, role_info in status_data.items():
                                if isinstance(role_info, dict) and role_info.get('owner_id') == uid:
                                    from utils.role_utils import format_role_display
                                    role_name = format_role_display(role_key)
                                    break

                            await bot.send_message(
                                uid,
                                f"🔔 <b>Ваш рест закончился!</b>\n\n"
                                f"🎭 Роль: <b>{html.escape(role_name)}</b>\n"
                                f"Теперь вы снова активны.",
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            logger.error(f"❌ Не удалось уведомить {uid}: {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в планировщике рестов: {e}")

        await asyncio.sleep(60)


async def sync_roles_loop():
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


async def norm_reminder_low_loop():
    global bot

    while True:
        try:
            now_utc = datetime.datetime.now(datetime.UTC)
            now_msk = now_utc + datetime.timedelta(hours=3)
            days_until_friday = (4 - now_msk.weekday()) % 7
            target = now_msk.replace(hour=19, minute=0, second=0, microsecond=0) + datetime.timedelta(days=days_until_friday)

            if now_msk >= target:
                target += datetime.timedelta(days=7)

            wait_seconds = (target - now_msk).total_seconds()
            if wait_seconds < 60:
                wait_seconds = 60

            await asyncio.sleep(wait_seconds)

            from utils.user_utils import load_users
            from utils.counters import get_message_count
            from utils.settings_utils import get_messages_norm

            norm = get_messages_norm()
            threshold = norm // 2

            users = load_users()
            sent_count = 0

            for u in users:
                uid = u.get('id')
                if not uid:
                    continue
                if not u.get('agreed_to_privacy', False) or not u.get('apply_sent', False):
                    continue
                if u.get('rest', False):
                    continue

                count = get_message_count(uid)
                if count < threshold:
                    try:
                        await bot.send_message(
                            uid,
                            f"📊 <b>Напоминание о норме</b>\n\n"
                            f"Привет! Ты набрал <b>{count}</b> из <b>{norm}</b> сообщений за неделю.\n"
                            f"Завтра (в субботу) ты можешь получить варн или бан!\n\n"
                            f"Успей набрать норму! Каждое сообщение в чате — это шаг к цели. 💪",
                            parse_mode="HTML"
                        )
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"❌ Не удалось отправить напоминание {uid}: {e}")
                    await asyncio.sleep(0.05)

            logger.info(f"📊 Напоминание о норме отправлено {sent_count} юзерам")

        except Exception as e:
            logger.error(f"❌ Ошибка в norm_reminder_low_loop: {e}")
            await asyncio.sleep(3600)


async def norm_reset_loop():
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

            from utils.counters import save_weekly_norm_history
            save_weekly_norm_history()
            reset_all_counters()
            logger.info("✅ Счётчики сброшены, история нормы сохранена (21:00 МСК)")
        except Exception as e:
            logger.error(f"❌ Ошибка в сбросе счётчиков: {e}")
            await asyncio.sleep(3600)


async def check_kicked_loop():
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

            kicked = []

            for u in users:
                uid = u.get('id')
                if not uid:
                    continue
                if not u.get('apply_sent', False):
                    continue

                grace_until = u.get('grace_until')
                if grace_until:
                    try:
                        grace_dt = datetime.datetime.fromisoformat(grace_until)
                        if datetime.datetime.now() < grace_dt:
                            continue
                    except (ValueError, TypeError):
                        pass

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

            logger.info(f"🧹 Кикнуты/ушли (после льготного периода): {kicked_ids}")
        except Exception as e:
            logger.error(f"❌ Ошибка проверки кикнутых: {e}")


# ======================== ДНИ РОЖДЕНИЯ ========================

async def _send_birthday_messages(mode: str):
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
            for u in users:
                try:
                    import html
                    await bot.send_message(
                        u['id'],
                        f"🎂 <b>Поздравляю вас с вашим днём рождения, {html.escape(u['full_name'])}!</b>\n\n"
                        f"Желаем удачи!\n\n"
                        f"— LOeZ team",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"❌ ЛС {u['id']}: {e}")

        elif mode == 'group':
            import html
            lines = []
            for u in users:
                role = u.get('role') or ''
                if role and role != '0':
                    lines.append(f"• {html.escape(u['full_name'])} ({html.escape(role)})")
                else:
                    lines.append(f"• {html.escape(u['full_name'])}")

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


# ======================== ГЛОБАЛЬНЫЙ ERROR HANDLER ========================

async def on_error(event: ErrorEvent):
    exception = event.exception
    logger.exception(f"🔥 Необработанная ошибка в событии: {exception}")
    error_logger.exception(f"🔥 Ошибка: {exception}")

    if Notification and sys.platform == 'win32':
        try:
            toast = Notification(
                app_id="LoEzF_Bot",
                title="🔥 Ошибка в боте!",
                msg=f"{type(exception).__name__}: {str(exception)[:100]}...",
                duration="short"
            )
            toast.set_audio(audio.Default, loop=False)
            toast.show()
        except Exception as e:
            logger.error(f"❌ Не удалось показать уведомление Windows: {e}")

    update = event.update
    if update.message:
        try:
            await update.message.answer("⚠️ Произошла внутренняя ошибка. Попробуйте позже.")
        except Exception:
            pass
    elif update.callback_query:
        try:
            await update.callback_query.answer("⚠️ Произошла внутренняя ошибка.", show_alert=True)
        except Exception:
            pass


# ======================== GRACEFUL SHUTDOWN ========================

async def on_shutdown(bot: Bot):
    logger.info("🛑 Получен сигнал завершения. Останавливаю polling...")
    for task in _background_tasks:
        task.cancel()
    await bot.session.close()
    logger.info("✅ Бот успешно остановлен.")


# ======================== ПРОВЕРКА ЧАТОВ ========================

async def check_bot_in_chats(bot: Bot):
    chats_to_check = [
        (GENERAL_CHAT_ID, "Флуд-чат"),
        (ADMIN_GROUP_ID, "Админ-группа")
    ]
    for chat_id, name in chats_to_check:
        if chat_id == 0 or chat_id is None:
            continue
        try:
            member = await bot.get_chat_member(chat_id, bot.id)
            status = member.status
            if status in ['creator', 'administrator']:
                logger.info(f"✅ Бот является админом в чате '{name}' ({chat_id})")
            else:
                logger.warning(f"⚠️ Бот НЕ админ в чате '{name}' ({chat_id}). Статус: {status}")
        except Exception as e:
            logger.error(f"❌ Ошибка проверки чата '{name}' ({chat_id}): {e}")


# ======================== RUN ========================

async def run_bot():
    global bot
    dp = Dispatcher()
    dp.message.middleware(RegistrationCheckMiddleware())
    logger.info("✅ Middleware стартового режима подключен")

    for router in routers:
        dp.include_router(router)
    logger.info(f"✅ Зарегистрировано {len(routers)} роутеров")

    dp.errors.register(on_error)
    dp.shutdown.register(on_shutdown)

    while True:
        try:
            if bot is None:
                bot = await create_bot_with_proxy()
            await on_startup()
            try:
                await dp.start_polling(bot, skip_updates=False)
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
    global _background_tasks
    logger.info("🚀 Запуск...")
    await db.init()

    if bot:
        await check_bot_in_chats(bot)

    try:
        from utils.role_utils import sync_roles_from_files
        result = sync_roles_from_files()
        logger.info(f"🔄 Синхронизация ролей: {result}")
    except Exception as e:
        logger.error(f"❌ Ошибка синхронизации: {e}")

    # ⚠️ НОВОЕ: Запускаем фоновые циклы ОДИН раз, сохраняя ссылки
    if not _background_tasks:
        _background_tasks.append(asyncio.create_task(norm_reminder_low_loop()))
        logger.info("🔄 norm_reminder_low_loop запущен (пятница 19:00 МСК)")
        _background_tasks.append(asyncio.create_task(check_rests_loop()))
        logger.info("🔄 check_rests_loop запущен")
        _background_tasks.append(asyncio.create_task(sync_roles_loop()))
        logger.info("🔄 sync_roles_loop запущен (03:33 МСК)")
        _background_tasks.append(asyncio.create_task(expire_warns_loop()))
        logger.info("🔄 expire_warns_loop запущен (раз в час)")
        _background_tasks.append(asyncio.create_task(norm_reminder_loop()))
        logger.info("🔄 norm_reminder_loop запущен (сб 19:00 МСК)")
        _background_tasks.append(asyncio.create_task(norm_reset_loop()))
        logger.info("🔄 norm_reset_loop запущен (сб 21:00 МСК)")
        _background_tasks.append(asyncio.create_task(check_kicked_loop()))
        logger.info("🔄 check_kicked_loop запущен (раз в мин)")
        _background_tasks.append(asyncio.create_task(birthday_personal_loop()))
        logger.info("🔄 birthday_personal_loop запущен (00:00 МСК)")
        _background_tasks.append(asyncio.create_task(birthday_group_loop()))
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