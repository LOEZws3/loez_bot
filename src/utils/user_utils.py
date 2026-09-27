import os
import json
import datetime
import calendar
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

UNSUBSCRIBED_FILE = "data/users/unsubscribed_calls.json"
REST_REQUESTS_FILE = "data/requests/rest_requests.json"


# ======================== ОТПИСАВШИЕСЯ ОТ КАЛОВ ========================

def load_unsubscribed() -> dict:
    """Загрузить отписавшихся. Возвращает dict {user_id_str: True}."""
    try:
        os.makedirs(os.path.dirname(UNSUBSCRIBED_FILE), exist_ok=True)
        with open(UNSUBSCRIBED_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        return {}


def save_unsubscribed(data: dict) -> bool:
    try:
        os.makedirs(os.path.dirname(UNSUBSCRIBED_FILE), exist_ok=True)
        with open(UNSUBSCRIBED_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def is_unsubscribed(user_id: int) -> bool:
    data = load_unsubscribed()
    return str(user_id) in data


def add_unsubscribed(user_id: int) -> bool:
    data = load_unsubscribed()
    data[str(user_id)] = True
    return save_unsubscribed(data)


def remove_unsubscribed(user_id: int) -> bool:
    data = load_unsubscribed()
    if str(user_id) in data:
        del data[str(user_id)]
        return save_unsubscribed(data)
    return True


# ======================== ЗАЯВКИ НА РЕСТ (JSON-СЛОВАРЬ) ========================

def load_rest_requests() -> dict:
    """
    Загрузить заявки на рест.
    Формат: {user_id_str: {user_id, username, full_name, role_name, days,
             rest_until, reason, status, created_at}}
    """
    try:
        os.makedirs(os.path.dirname(REST_REQUESTS_FILE), exist_ok=True)
        with open(REST_REQUESTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        return {}


def save_rest_requests(data: dict) -> bool:
    try:
        os.makedirs(os.path.dirname(REST_REQUESTS_FILE), exist_ok=True)
        with open(REST_REQUESTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def get_rest_request(user_id: int) -> dict:
    """Возвращает заявку на рест конкретного юзера (или {})"""
    data = load_rest_requests()
    return data.get(str(user_id), {})


def add_rest_request(user_id: int, request_data: dict) -> bool:
    """Добавляет/перезаписывает заявку юзера"""
    data = load_rest_requests()
    data[str(user_id)] = request_data
    return save_rest_requests(data)


def remove_rest_request(user_id: int) -> bool:
    """Удаляет заявку юзера"""
    data = load_rest_requests()
    if str(user_id) in data:
        del data[str(user_id)]
        return save_rest_requests(data)
    return True


def update_rest_request(user_id: int, key: str, value) -> bool:
    """Обновляет одно поле в заявке"""
    data = load_rest_requests()
    uid_str = str(user_id)
    if uid_str not in data:
        return False
    data[uid_str][key] = value
    return save_rest_requests(data)


def get_pending_rests() -> list:
    """Возвращает список pending-заявок [(user_id, data), ...]"""
    data = load_rest_requests()
    result = []
    for uid_str, req in data.items():
        if isinstance(req, dict) and req.get('status') == 'pending':
            try:
                result.append((int(uid_str), req))
            except ValueError:
                continue
    return result


# ======================== КАЛЕНДАРЬ ДЛЯ РЕСТОВ ========================

def generate_calendar_keyboard(year, month, callback_prefix="rest_cal"):
    """
    Создаёт клавиатуру-календарь для выбора даты.
    Callback data:
    - выбор дня:    {prefix}_day_YYYY_M_D
    - пред. месяц:  {prefix}_prev_YYYY_M
    - след. месяц:  {prefix}_next_YYYY_M
    - отмена:       cancel_rest_request
    """
    cal = calendar.monthcalendar(year, month)
    keyboard = []

    month_names = [
        "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]
    keyboard.append([InlineKeyboardButton(
        text=f"{month_names[month]} {year}",
        callback_data="ignore"
    )])

    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    keyboard.append([InlineKeyboardButton(text=day, callback_data="ignore") for day in week_days])

    today = datetime.date.today()

    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                date_obj = datetime.date(year, month, day)
                if date_obj < today:
                    # Прошедшие дни — неактивные
                    row.append(InlineKeyboardButton(text=f"·{day}", callback_data="ignore"))
                else:
                    row.append(InlineKeyboardButton(
                        text=str(day),
                        callback_data=f"{callback_prefix}_day_{year}_{month}_{day}"
                    ))
        keyboard.append(row)

    # Навигация
    nav_row = []

    # Назад
    if month > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"{callback_prefix}_prev_{year}_{month}"))
    else:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"{callback_prefix}_prev_{year - 1}_12"))

    nav_row.append(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_rest_request"))

    # Вперёд
    if month < 12:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"{callback_prefix}_next_{year}_{month}"))
    else:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"{callback_prefix}_next_{year + 1}_1"))

    keyboard.append(nav_row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)