# 📋 История изменений проекта LoezF_Bot

## [11.1.0] - 2026-10-30

### 🚀 Глобальный апдейт: Диагностика, Статистика и Чистка кода

**📊 Продвинутый `/diag`:**
- Теперь показывает: Uptime, Downtime, Bugtime (сетевые лаги), нагрузку на RAM/CPU, статус фоновых задач, целостность связей ролей и юзеров.
- **Меню статистики:** кнопка «Подробнее о Downtime» строит красивый столбчатый график (Uptime, Bugtime, Downtime) за день, неделю, месяц, год или кастомный период.
- Добавлено время последнего обновления отчёта.

**💾 Бэкапы и Управление:**
- Кнопка «📦 Сделать БЭКАП (ZIP)» собирает все базы в архив и сохраняет в `C:\Users\olika\PyCharmMiscProject\backup`.
- Автоматическая очистка старых бэкапов (старше 3 месяцев).
- Кнопки «🔄 Перезапустить бота» и «🛑 Экстренное отключение».
- Логирование того, кто именно (ID и @username) нажал кнопку рестарта/оффа.
- Красивые ASCII-плашки при рестарте и отключении.
- После рестарта бот присылает владельцу в ЛС сообщение «RESTART SUCCESSFUL!».

**🛠️ Рефакторинг и чистка (Этап 3):**
- Удалён мертвый файл `src/database.py` и зависимость `aiosqlite`.
- Логика заявок унифицирована в `utils/requests_utils.py` с атомарной записью.
- В `counters.py` добавлено кэширование в оперативной памяти (скорость выросла).
- В `base_commands.py` команды `/users` и `/members` переведены на пагинацию (кнопки с юзернеймами и ролями).

**🐛 Исправлено:**
- **Кринж-спам:** `chat_member.py` больше не спамит сообщениями «Я не вижу вас в системе» старым юзерам, у которых просто не было флага `is_fully_registered`.
- **Кринж-напоминалка:** `norm_reminder_low_loop` больше не присылает напоминания всем подряд. Теперь только тем, кто реально в категориях WARN или BAN.
- **`query is too old`:** Добавлены `safe_answer` во все колбэки, чтобы бот не крашился при долгих нажатиях кнопок.

## [11.0.0] - 2026-10-28

### 🚀 Глобальный апдейт: Политика, Кэш, Ссылки, Каскад прокси

**📝 Политика конфиденциальности:**
- При `/start` бот требует согласия с политикой и правилами (ссылки берутся из `.env`).
- Новое поле в `users.json`: `"agreed_to_privacy": true`.
- Без согласия доступ к остальным командам заблокирован.

**🧹 Кэш JSON (Write-Through Cache):**
- Реализован в `src/utils/parsers.py` для ускорения чтения/записи.
- Кнопка «🧹 Сбросить кэш» в `/settings` для ручной очистки.

**🔗 Персональные ссылки:**
- Бот создаёт персональную ссылку (`create_chat_invite_link`) на 1 вход, живёт 2 дня.
- Кэшируется в `users.json`: `invite_link`, `invite_link_expires_at`.

**🌐 Каскад прокси:**
- Happ (`socks5://127.0.0.1:10808`) → Karing (`socks5://127.0.0.1:3066`) → напрямую.
- Если прокси не работает — бот автоматически пробует следующий.

**🛡️ Стабильность и защита:**
- Атомарная запись JSON: `tmp` + `os.replace` + `.bak` (защита от потери данных).
- Маскировка паролей прокси в логах (`***:***@`).
- `on_error` переписан под `ErrorEvent`, ошибки пишутся в `errors.txt`.

**🛏️ Ресты:**
- Хранятся в `users.json` (`rest`, `rest_end_date`), авто-снятие по истечении.
- `/unrest` работает по ID.

**📅 Неделя по МСК:**
- `counters.py` использует `ZoneInfo("Europe/Moscow")`. Неделя начинается в сб 21:00.
- Требуется `tzdata` на Windows.

**👋 Юзеры:**
- Приветствие перенесено на `@router.chat_member()` (было `my_chat_member`).
- Парсер варнов поддерживает склонения («30 минут», «2 дня», «3 недели»).
- «С возвращением» при `/start`.

**🔐 Middleware:**
- Обход для владельца и админов.
- Логирование команд админов в `admin_actions.log`.

**📊 Статистика:**
- `/mynorm` (личный график), `/stats` (365 дней), Топ-5.
- `/sync_norm` — ручное начисление нормы.

**🛡️ Безопасность:**
- Rate-limit на `/apply` (1 минута).
- Защита от двойного клика при одобрении/отклонении заявок.
- Логирование повышений, понижений, `/setrank`.

**🐛 Исправлено:**
- `query is too old` в `help_back_callback` → добавлен try/except на `callback.answer()`.

## [10.0.0] - 2026-10-24

### 🚀 Глобальный апдейт: Ресты, Синхронизация, Топ-5

**🛏️ Ресты:**
- Ресты теперь хранятся в `users.json` (поля `rest` и `rest_end_date`).
- Авто-снятие реста проверяет `users.json` и снимает рест, когда дата истекает, с уведомлением юзера.
- Команда `/unrest` теперь работает по ID роли или ID юзера (а не по названию).
- Исправлен баг с сохранением реста в `roles_status.json`.

**📊 Статистика:**
- Команда `/sync_norm [дни] [сообщений]` — ручное начисление нормы всем юзерам.
- Кнопка «🏆 Топ недели» в `/stats` — показывает 5 самых активных юзеров за неделю.

**👋 Пользователи:**
- При `/start` бот проверяет историю и пишет «С возвращением» для тех, кто уже был.

**🛡️ Безопасность и стабильность:**
- Middleware `registration_check` больше не вызывает `is_admin` (это вызывало циклический импорт и ломало команды).
- Исправлен баг с `format_role_display` в `rest_commands.py`.

## [9.0.0] - 2026-10-22

### 🚀 Глобальный рефакторинг и защита (Этапы 1-4)

**🛡️ Безопасность и стабильность (Этап 1):**
- **Глобальный Error Handler**: теперь все ошибки пишутся в `data/logs/errors.txt` и вызывают системные уведомления Windows (через `winotify`).
- **Graceful Shutdown**: корректное завершение работы бота при остановке (безопасное закрытие сессий).
- **Проверка чатов при старте**: бот проверяет, является ли он админом в `GENERAL_CHAT_ID` и `ADMIN_GROUP_ID`.

**👥 Защита пользователей (Этап 2):**
- **Проверка профиля**: если у юзера не заполнена дата рождения или роль, бот напоминает ему во флуде (нью — раз в 1 час, остальные — раз в 12 часов) с кнопкой перехода в ЛС.
- **Сбор алиасов**: старые никнеймы и имена сохраняются в `data/users/aliases.json`.
- **Rate-limit на `/apply`**: защита от спама (1 минута между заявками).
- **Автосвобождение ролей**: если заявка висит в статусе `pending` более 48 часов, она отклоняется, а роль освобождается.
- **Причина отклонения**: при отклонении заявки через инлайн-кнопку бот запрашивает причину и отправляет её юзеру в ЛС.
- **Сообщение после одобрения**: юзеру отправляется капс-инструкция по завершению регистрации.

**📊 Статистика и графики (Этап 3):**
- **Графики**: команда `/mynorm` (личный график активности) и кнопка «📈 График активности» в `/stats` (на основе истории норм).
- **История норм**: при сбросе счётчиков данные сохраняются в `data/system/norm_history.json`.
- **Команда `/giverest`**: админ может отправить юзера в рест за другого (на N дней).

**🧹 Рефакторинг (Этап 4):**
- **Рефакторинг `admin_commands.py`**: файл удалён, логика разделена на `admin_stats.py` (статистика), `admin_roles.py` (поиск/удаление ролей, `/giverest`) и `admin_users.py` (управление юзерами, регистрация).
- **Обновлены библиотеки**: `aiogram` до `3.23.0`, `pydantic` до `2.12.0`, `matplotlib` до `3.10.8`, `scipy` до `1.16.1` (для поддержки Python 3.14 и графиков).
- **Настройки**: в `/settings` добавлена кнопка «Проверка профиля» (вкл/выкл).

**🐛 Исправлено:**
- **Кнопка удаления в `/findrole`**: исправлен конфликт префиксов колбэков (теперь используются строгие regex-фильтры).
- **`/diag`**: исправлены пути к файлам `roles_status.json` и `system_settings.json`.
- **Ошибка с рангами**: владельцы (ранг 1) теперь корректно проходят проверки `is_owner`.
- **`get_category_label`**: добавлен недостающий импорт в `admin_users.py`.
- **Импорты после рефакторинга**: исправлены ссылки на `admin_commands` в `keyboards.py` и `base_commands.py`.

## [8.1.0] - 2026-10-06

### 🌍 Глобальный апдейт — ДР, подписка на норму, расширенный /stats

**🎂 Дни рождения (Функция 9):**
- `/setbirthday` — FSM (кнопки: день → месяц, без года)
- Формат хранения: `users.json` → `"birthday": "15.03"`
- Дублирование в `users_history/{id}.json` → `"birthday": "15.03"`
- **Планировщик 1:** `birthday_personal_loop` (00:00 МСК) — ЛС каждому имениннику
- **Планировщик 2:** `birthday_group_loop` (12:00 МСК) — одно сообщение во флуд со всеми
- Шаблон ЛС: «Поздравляю вас с вашим днём рождения, {full_name}! Желаем удачи! — LOeZ team»
- Шаблон во флуд: список «• {full_name} ({role})»

**📩 Подписка на уведомления о норме (Функция 7):**
- Новое поле в `users.json`: `"notify_norm": true` (по умолчанию — все подписаны)
- `/subnorm` — подписаться
- `/unsubnorm` — отписаться
- Триггер в `chat_member.py`: при `count >= messages_norm` → ЛС
- Флаг `norm_notified` в `message_counts.json` (сбрасывается при reset)
- Глобальная настройка `norm_auto_message_enabled` (вкл по умолчанию)
- Текст: «🎉 Поздравляю! Ты набрал норму за эту неделю!»

**📊 Расширенный `/stats` (Функция 2):**
- Кнопки: «📊 База», «📅 День», «📆 Неделя», «📈 Месяц»
- База: роли / участники / админы (без прокси)
- Периоды: нью за период / хороших / варн / бан / рест / активных / ушло
- В флуде — краткая версия без кнопок

**📁 Новый файл `data/system/leftdata.json`:**
- Хранит ушедших юзеров: `{user_id: {full_name, role, left_at, reason}}`
- Заполняется в `check_kicked_loop` при `status in ['left', 'kicked']`
- Используется в `/stats` для подсчёта «ушло за период»

**🔄 Обновление `users_history/{id}.json`:**
- Добавлены поля: `role_id`, `role_key`, `birthday`, `last_message_at`
- Новые обёртки: `set_role`, `set_birthday`, `set_last_message_at`, `set_left`

**🔄 Обновление `message_counts.json`:**
- Новые поля: `last_message_at`, `norm_notified`
- `increment_message_count` пишет `last_message_at`
- `reset_all_counters` сохраняет `joined_at`, `last_message_at`, сбрасывает `norm_notified`

**📄 Обновления файлов:**
- `config.py`: + `LEFTOVER_FILE`
- `parsers.py`: + `set_birthday`, `get_birthday`, `set_notify_norm`, `get_notify_norm`, `get_users_with_birthday`
- `user_utils.py`: обёртки для новых функций
- `user_history.py`: + `set_role`, `set_birthday`, `set_last_message_at`, `set_left`
- `counters.py`: + `update_last_message_at`, `mark_norm_notified`, `is_norm_notified`, `get_last_message_at`
- `chat_member.py`: триггер нормы + `last_message_at` + `set_left`
- `base_commands.py`: + `/setbirthday`, `/subnorm`, `/unsubnorm`
- `admin_commands.py`: `/stats` переписан с кнопками
- `main.py`: + `_save_leftdata`, + `birthday_personal_loop`, + `birthday_group_loop`, + BotCommand

## [8.0.1] - 2026-10-03

### 🩹 Исправления багов 1-9

**settings_utils.py:**
- БАГ 1: убраны дубли функций `get_messages_norm_low`, `get_warns_accumulate`, `get_warns_to_ban`.
- Добавлена настройка `checknorm_time_window_enabled`.
- Добавлена обёртка `get_checknorm_time_window_enabled()`.

**counters.py:**
- БАГ 2: `reset_all_counters` теперь СОХРАНЯЕТ `joined_at`.
- БАГ 7: `increment_message_count` НЕ ставит `joined_at` (это делает ТОЛЬКО `chat_member.py`).
- `increment_message_count` сохраняет `joined_at` при смене недели.

**warns_utils.py:**
- БАГ 4: переход на МИНУТЫ (было дни).
- `add_warn(user_id, minutes, ...)` — сигнатура с минутами.
- Поле `duration_minutes` в варне.

**chat_member.py:**
- БАГ 4: парсер варн/бан → МИНУТЫ. Поддержка единиц: мин, ч, д/дней, н, мес, г.
- БАГ 6: `_try_parse_warn_command` — ТОЛЬКО ВО ФЛУДЕ.
- БАГ 7: `set_joined_at` остаётся ЗДЕСЬ (единственное место!).
- Дефолт варна: 7 дней = 10080 минут.

**checknorm_commands.py:**
- БАГ 3: `WARN_MINUTES_ACCUMULATE = 21 * 24 * 60`.
- БАГ 9: проверка окна чистки (20:00–21:00 МСК).
- Импорт `get_checknorm_time_window_enabled`.
- Функция `_has_active_sessions()` (для main.py).
- Сроки в МИНУТАХ: `WARN_MINUTES_DEFAULT = 6 * 24 * 60`, `WARN_MINUTES_ACCUMULATE = 21 * 24 * 60`, `BAN_MINUTES = 90 * 24 * 60`.

**settings_commands.py:**
- Добавлена кнопка "Окно чистки".
- Добавлен обработчик `toggle_checknorm_window`.
- Добавлена строка в "Показать все настройки".

**main.py:**
- БАГ 9: `norm_reset_loop` переписан. Сброс ТОЛЬКО в 21:00 МСК. Если есть `ACTIVE_SESSIONS` — ждём до 15 минут.

**.gitignore:**
- Компромисс (02.10.2026): трекаем `roles_status.json`, `*.txt` в `data/roles/`, `free_role_ids.json`. Игнорим `bot.log`, `*.pyc`, `__pycache__`, `users.json`, `admins.json`, `requests.json`, `system_settings.json`, `warns.json`, `message_counts.json`, `proxy_pings_cache.json`.

### 🗑️ Удалено

- `src/utils/system_utils.py` — дублировал `settings_utils.py`

## [8.0.0] - 2026-10-02

### 🚀 Система нормы и чистки

**Новые файлы:**
- `src/utils/settings_utils.py`
- `src/utils/counters.py`
- `src/utils/warns_utils.py`
- `src/utils/norm_utils.py`
- `src/utils/role_ids.py`
- `src/handlers/checknorm_commands.py`
- `src/handlers/clear_me.py`
- `src/middlewares/`
- `migrate_role_ids.py`
- `migrate_roles.py`

**main.py:**
- + `expire_warns_loop` (раз в час)
- + `norm_reminder_loop` (сб 19:00 МСК)
- + `norm_reset_loop` (сб 20:00/21:00 МСК)
- + `check_kicked_loop` (раз в минуту)
- + `RegistrationCheckMiddleware`

**chat_member.py:**
- Счётчик сообщений для зарегистрированных
- Парсер команд варн/бан из чата
- Авто-установка joined_at
- Учёт реста (не считать)

**apply_handlers.py:**
- Таймаут подачи заявки (5 минут)
- callback_data: apply_season_<index>, apply_role_id_<id>
- Проверка лимита смен роли
- Предупреждение при смене роли

**admin_commands.py:**
- /findrole + /userstats с плашками ⚠️/🚫

**base_commands.py:**
- Плашки в /members
- Импорт norm_utils

**settings_commands.py:**
- Группа настроек "Норма и чистка"

**keyboards.py:**
- Кнопка /checknorm
- Стартовый режим

**request_commands.py:**
- Работа с role_id при одобрении
- Уведомления через ADMIN_GROUP_ID

**clear_me.py (НОВЫЙ):**
- /clearme — полная очистка данных юзера
- Тройное подтверждение

## [7.4.0] - 2026-09-26

### 🚀 Добавлено

#### Система смены роли
- `max_role_changes` в system_settings.json.
- `changes_count` в users.json.
- Предупреждение при подаче заявки, если у юзера уже есть роль.
- FSM `confirming_replace`.
- Автоматическое освобождение старой роли.
- Владельцы не ограничены.

#### Команда `/userstats [ID]`
- Показывает статистику юзера.
- Кнопки "🔄 Сбросить счётчик смен" и "🗑️ Сбросить пользователя".

#### Кнопка в /settings
- "🔄 Макс. смен роли: N" (FSM-ввод, 0-20).

#### В parsers.py
- `changes_count` в get_user и add_user.
- `get_changes_count`, `increment_changes_count`, `reset_changes_count`.
- `max_role_changes` в default settings.

#### В config.py
- `MODERATOR_LINK` и `ADMIN_LINK`.

#### Прокси Webshare.io
- `PRIORITY_PROXY=http://логин:пароль@IP:ПОРТ`.

### 🔧 Изменено

#### handlers/apply_handlers.py
- Импорт `TelegramBadRequest`.
- FSM `confirming_replace`.
- Проверка лимита смен роли.
- `try/except` на "message is not modified".
- `apply_replace_confirm`.
- `_submit_request`.
- `_notify_admins` читает admins.json.
- `/free` с подтверждением.

#### handlers/request_commands.py
- Освобождение старой роли + инкремент счётчика.
- Показ старой роли и счётчика смен.
- Ссылки после одобрения (CHAT_INVITE_LINK, ADMIN_LINK, MODERATOR_LINK).

#### handlers/settings_commands.py
- Настройка `max_role_changes`.

#### handlers/admin_commands.py
- `/userstats` + колбэки.

#### src/proxy_manager.py (переписан)
- `PING_COUNT=1`, `PING_TIMEOUT=5`, `BAD_PROXY_TTL=600`.
- `bad_proxies_until` (soft-blacklist).
- Двойная проверка приоритетного прокси.

### 🐛 Исправлено
- Наложение ролей.
- Уведомления о заявках (admins.txt → admins.json).
- Подтверждение /free.
- Ссылки после одобрения.

## [7.3.0] - 2026-09-18

### 🚀 Добавлено
- Раздел "ЗАФИКСИРОВАННЫЕ ВЕРСИИ БИБЛИОТЕК" в GUIDE_FOR_AI.txt.
- Тестовая копия (LoEZF_Bot_test).

### 🔧 Изменено
- requirements.txt: зафиксированы версии.

### 🐛 Исправлено
- Обновлённые версии библиотек ломали подключение через прокси.

## [7.2.0] - 2026-09-16

### 🚀 Добавлено
- `/message_all` (FSM-рассылка).
- Правило чтения файлов через код-блок.

### 🔧 Изменено
- Порядок роутеров: keyboards перед chat_member.
- `unsubscribed_calls` → .json.
- Убран `apply_states_router`.

### 🐛 Исправлено
- Reply-клавиатура не реагировала.
- `/regc`, `/unregc`, `/call`, `/callfal` молчали.

## [7.1.0] - 2026-09-15

### 🚀 Добавлено
- JSON-формат для users/admins/requests.
- Приоритетный прокси.
- FSM для настроек.

### 🔧 Изменено
- `proxy_manager.py`: PING_COUNT=1, MAX_CONCURRENT=200.
- `chat_member` пропускает команды.
- `add_user`/`add_admin` вынесены в utils.

## [7.0.0] - 2026-09-14

### 🚀 Добавлено
- Переход на aiogram 3.x.
- Логика рангов при одобрении заявок.

### 🔧 Изменено
- requests.json — словарь.
- Логи в data/logs/.
- Удаление role_commands.py.
- Абсолютные пути через .resolve().

## [6.2.0] - 2026-09-12

### Исправлено
- 🐛 Критический баг `'str' object has no attribute 'get'` в `role_utils.py`.
- 🐛 `/free` корректно освобождает роли.
- 🐛 `/roles` показывает сезоны и роли.
- 🐛 Reply-кнопки обрабатываются.

### Изменено
- 🔄 `role_utils.py` переписан под реальную структуру `roles_status.json`.

### Добавлено
- ✨ `save_roles_status()`.
- ✨ `get_closed_mode()` / `set_closed_mode()`.
- ✨ `get_system_settings()` / `save_system_settings()`.
- ✨ Обработчики Reply-кнопок.
- ✨ Разделы в GUIDE_FOR_AI.txt.

## [5.5.0] - 2026-09-06

### 🚀 Добавлено
- `/promote`, `/demote`, `/setrank`.
- `/settings` (инлайн-меню).
- `/diag`, `/check_chats`.
- Логирование действий админов.

### 🔧 Изменено
- `chat_member_router` в `__init__.py`.
- Проверки `if message.chat.id == GENERAL_CHAT_ID`.
- `/hide`, `/menu`.

### 🐛 Исправлено
- Напоминалка для незарегистрированных.
- Команды во флуде.
- Импорт `chat_member_router`.

## [5.4.1] - 2026-09-06

### 🔧 Изменено
- Удалена пересылка сообщений из основного бота.

### 🧹 Очистка кода
- Убраны лишние импорты.
- Упрощена клавиатура.

### 📝 Документация
- Обновлён `CHANGELOG.md`.
- Обновлён `GUIDE_FOR_AI.txt`.

## [5.4.0] - 2026-09-06

### 🚀 Добавлено
- Система напоминаний для незарегистрированных.
- Управление пересылкой (удалено в 5.4.1).
- `/update`.

### 🔧 Изменено
- Команды с вводом недоступны во флуде.
- Кнопки для пересылки.
- Логирование [КНОПКА], [КОМАНДА], [ПЕРЕСЫЛКА].

### 🐛 Исправлено
- Кнопки работают.
- `/apply` не работает во флуде.
- Напоминалка.
- Импорт `forward_settings_router`.

## [5.3.0] - 2026-09-05

### 🚀 Добавлено
- Система прокси с пингованием.
- Кэширование результатов (10 минут).
- Автопереключение.

### 🔧 Изменено
- `main.py`: строгое предупреждение.
- `AiohttpSession(proxy=proxy_url)`.
- Автоперезапуск через 5 секунд.

### 🐛 Исправлено
- `ProxyConnectionError`.
- `TelegramNetworkError`.
- Зацикливание при переключении.
- `Invalid proxy response`.

## [5.2.0] - 2026-09-04

### 🚀 Добавлено
- Бот-пересыльщик (`forward_bot`).
- `/forward_settings`.
- `forward_settings.json`.

### 🔧 Изменено
- Логирование кнопок.
- Диагностика путей.

### 🐛 Исправлено
- `ImportError: cannot import name 'get_user_forward_status'`.
- `TypeError: unsupported operand type(s) for /`.
- `role_utils.py` (os.path.join).

## [5.1.0] - 2026-09-03

### 🚀 Добавлено
- Рефакторинг `commands.py` на модули.
- `proxy_manager.py`.

### 🔧 Изменено
- Структура `handlers/`.
- `forward_settings_router`.

### 🐛 Исправлено
- `file_utils.py` (`.parent` для строк).
- Импорт в `forward.py`.
- `role_utils.py` (os.path.join).

## [5.0.0] - 2026-09-02

### 🚀 Добавлено
- Создан проект `LoezF_Bot`.
- SQLite, система ролей, заявок, рестов, калов.
- Базовые команды.

## 📋 Сокращения

| Сокращение | Значение |
|------------|----------|
| `[ДОБАВЛЕНО]` | Новая функциональность |
| `[ИЗМЕНЕНО]` | Изменение существующей функциональности |
| `[ИСПРАВЛЕНО]` | Исправление ошибки |
| `[УДАЛЕНО]` | Удаление функциональности |

📅 Последнее обновление: 28.10.2026