"""
Утилита для определения категории юзера по норме.
Используется для плашек в /members, /users, /checknorm.
"""

import logging

from utils.counters import get_all_counts, get_message_count, is_new_user
from utils.settings_utils import (
    get_messages_norm, get_messages_norm_low,
)
from utils.warns_utils import get_warns_count

logger = logging.getLogger(__name__)


CATEGORY_GOOD = 'good'      # ✅ набрал норму
CATEGORY_WARN = 'warn'      # ⚠️ от НПНДБ до нормы
CATEGORY_BAN = 'ban'        # 🚫 меньше НПНДБ
CATEGORY_NEW = 'new'        # 👶 Нью (<7 дней)
CATEGORY_REST = 'rest'      # ⏳ в ресте
CATEGORY_UNKNOWN = 'unknown'  # ?


def get_user_category(user_id: int) -> str:
    """
    Определяет категорию юзера за текущую неделю.
    """
    # Нью?
    if is_new_user(user_id, days=7):
        return CATEGORY_NEW

    # В ресте?
    try:
        from utils.role_utils import load_roles_status
        data = load_roles_status()
        for role_key, info in data.items():
            if isinstance(info, dict) and info.get('owner_id') == user_id:
                if info.get('status') == 'рест':
                    return CATEGORY_REST
                break
    except Exception:
        pass

    # Считаем норму
    count = get_message_count(user_id)
    norm = get_messages_norm()
    norm_low = get_messages_norm_low()

    if count >= norm:
        return CATEGORY_GOOD
    if count >= norm_low:
        return CATEGORY_WARN
    return CATEGORY_BAN


def get_emoji(category: str) -> str:
    """Возвращает эмодзи для категории."""
    return {
        CATEGORY_GOOD: '✅',
        CATEGORY_WARN: '⚠️',
        CATEGORY_BAN: '🚫',
        CATEGORY_NEW: '👶',
        CATEGORY_REST: '⏳',
        CATEGORY_UNKNOWN: '❓',
    }.get(category, '')


def get_category_label(category: str) -> str:
    """Текстовая метка категории."""
    return {
        CATEGORY_GOOD: 'Норма набрана',
        CATEGORY_WARN: 'Варн',
        CATEGORY_BAN: 'Бан',
        CATEGORY_NEW: 'Нью',
        CATEGORY_REST: 'Рест',
        CATEGORY_UNKNOWN: 'Неизвестно',
    }.get(category, '')


def get_all_categorized() -> dict:
    """
    Возвращает {category: [(user_id, count), ...]} для всех зарегистрированных.
    """
    from utils.user_utils import load_users

    counts = get_all_counts()
    norm = get_messages_norm()
    norm_low = get_messages_norm_low()

    result = {
        CATEGORY_GOOD: [],
        CATEGORY_WARN: [],
        CATEGORY_BAN: [],
        CATEGORY_NEW: [],
        CATEGORY_REST: [],
    }

    for u in load_users():
        uid = u.get('id')
        if not uid:
            continue

        category = get_user_category(uid)
        count = counts.get(str(uid), 0)

        if category in result:
            result[category].append((uid, count))

    return result