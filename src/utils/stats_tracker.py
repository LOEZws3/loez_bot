import os
import json
import datetime
import logging
from config import DATA_DIR

logger = logging.getLogger(__name__)
STATS_FILE = os.path.join(DATA_DIR, 'system', 'stats_history.json')

def _load_stats():
    if not os.path.exists(STATS_FILE):
        return {}
    try:
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _save_stats(data):
    try:
        os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения stats_history.json: {e}")

def add_time(uptime=0, bugtime=0, downtime=0):
    """Добавляет секунды к сегодняшнему дню."""
    today = datetime.date.today().isoformat()
    data = _load_stats()
    
    if today not in data:
        data[today] = {"uptime": 0, "bugtime": 0, "downtime": 0}
        
    data[today]["uptime"] += uptime
    data[today]["bugtime"] += bugtime
    data[today]["downtime"] += downtime
    
    # Ограничиваем историю 365 днями, чтобы файл не рос бесконечно
    if len(data) > 365:
        oldest = sorted(data.keys())[0]
        del data[oldest]
        
    _save_stats(data)

def get_stats(days=7):
    """Возвращает список последних N дней с данными."""
    data = _load_stats()
    today = datetime.date.today()
    result = []
    
    for i in range(days - 1, -1, -1):
        d = (today - datetime.timedelta(days=i)).isoformat()
        if d in data:
            result.append((d, data[d]))
        else:
            result.append((d, {"uptime": 0, "bugtime": 0, "downtime": 0}))
            
    return result