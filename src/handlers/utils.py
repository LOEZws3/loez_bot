import os
import json
import datetime
import calendar
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

UNSUBSCRIBED_FILE = "data/users/unsubscribed_calls.txt"
REST_REQUESTS_FILE = "data/requests/rest_requests.json"

def load_unsubscribed():
    """Загрузить список отписавшихся от калов"""
    try:
        with open(UNSUBSCRIBED_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_unsubscribed(data):
    """Сохранить список отписавшихся"""
    os.makedirs(os.path.dirname(UNSUBSCRIBED_FILE), exist_ok=True)
    with open(UNSUBSCRIBED_FILE, 'w') as f:
        json.dump(data, f)

def is_unsubscribed(user_id):
    """Проверить, отписан ли пользователь"""
    return user_id in load_unsubscribed()

def add_unsubscribed(user_id):
    """Добавить пользователя в список отписавшихся"""
    data = load_unsubscribed()
    if user_id not in data:
        data.append(user_id)
        save_unsubscribed(data)

def remove_unsubscribed(user_id):
    """Удалить пользователя из списка отписавшихся"""
    data = load_unsubscribed()
    if user_id in data:
        data.remove(user_id)
        save_unsubscribed(data)

def load_rest_requests():
    """Загрузить заявки на рест"""
    os.makedirs(os.path.dirname(REST_REQUESTS_FILE), exist_ok=True)
    try:
        with open(REST_REQUESTS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_rest_requests(requests):
    """Сохранить заявки на рест"""
    os.makedirs(os.path.dirname(REST_REQUESTS_FILE), exist_ok=True)
    with open(REST_REQUESTS_FILE, 'w') as f:
        json.dump(requests, f, indent=4)

def generate_calendar_keyboard(year, month, callback_prefix="rest_cal"):
    """Создать клавиатуру-календарь для выбора даты"""
    cal = calendar.monthcalendar(year, month)
    keyboard = []
    month_name = calendar.month_name[month]
    keyboard.append([InlineKeyboardButton(text=f"{month_name} {year}", callback_data="ignore")])
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
                    row.append(InlineKeyboardButton(text=str(day), callback_data="ignore"))
                else:
                    row.append(InlineKeyboardButton(text=str(day), callback_data=f"{callback_prefix}_{year}_{month}_{day}"))
        keyboard.append(row)

    nav_row = []
    if month > 1:
        nav_row.append(InlineKeyboardButton(text="<", callback_data=f"{callback_prefix}_prev_{year}_{month}"))
    else:
        nav_row.append(InlineKeyboardButton(text="<", callback_data=f"{callback_prefix}_prev_{year - 1}_12"))
    
    nav_row.append(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_rest_request"))
    
    if month < 12:
        nav_row.append(InlineKeyboardButton(text=">", callback_data=f"{callback_prefix}_next_{year}_{month}"))
    else:
        nav_row.append(InlineKeyboardButton(text=">", callback_data=f"{callback_prefix}_next_{year + 1}_1"))
    
    keyboard.append(nav_row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)