import datetime
import logging

logger = logging.getLogger(__name__)

# Глобальные переменные для отслеживания сетевых сбоев (Bugtime)
BUGTIME_TOTAL = 0.0         # Всего секунд в сбое
BUGTIME_START = None        # Время начала текущего сбоя

def mark_bug_start():
    global BUGTIME_START
    if BUGTIME_START is None:
        BUGTIME_START = datetime.datetime.now()
        logger.warning("⚠️ [BUGTIME] Сеть недоступна! Таймер запущен.")

def mark_bug_end():
    global BUGTIME_TOTAL, BUGTIME_START
    if BUGTIME_START is not None:
        delta = (datetime.datetime.now() - BUGTIME_START).total_seconds()
        BUGTIME_TOTAL += delta
        BUGTIME_START = None
        logger.info(f"✅ [BUGTIME] Сеть восстановлена. Сбой длился {delta:.1f} сек.")

def get_bugtime_str() -> str:
    total = BUGTIME_TOTAL
    if BUGTIME_START is not None:
        # Если сбой прямо сейчас, добавляем текущее время
        total += (datetime.datetime.now() - BUGTIME_START).total_seconds()
    
    if total < 1:
        return "0 сек."
        
    hours, remainder = divmod(int(total), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if hours > 0:
        return f"{hours} ч. {minutes} мин. {seconds} сек."
    elif minutes > 0:
        return f"{minutes} мин. {seconds} сек."
    return f"{seconds} сек."