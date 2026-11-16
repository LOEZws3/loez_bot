import os
import datetime
import logging
from config import DATA_DIR
from utils.parsers import load_json, save_json

logger = logging.getLogger(__name__)

ACTIVITY_FILE = os.path.join(DATA_DIR, 'system', 'activity_feed.json')
MAX_EVENTS = 250

def log_activity(event_type: str, text: str):
    """Записывает событие в ленту, храня только последние 250."""
    try:
        data = load_json(ACTIVITY_FILE, default=[])
        if not isinstance(data, list):
            data = []
            
        event = {
            "time": datetime.datetime.now().strftime("%d.%m %H:%M"),
            "type": event_type,
            "text": text
        }
        
        # Добавляем в начало списка (чтобы новые были сверху)
        data.insert(0, event)
        
        # Обрезаем до 250
        if len(data) > MAX_EVENTS:
            data = data[:MAX_EVENTS]
            
        save_json(ACTIVITY_FILE, data)
    except Exception as e:
        logger.error(f"❌ Ошибка записи ленты событий: {e}")