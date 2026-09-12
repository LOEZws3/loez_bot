import os
import json
import logging
from config import DATA_DIR

logger = logging.getLogger(__name__)

def load_roles_status() -> dict:
    """
    Загружает полный файл roles_status.json
    """
    try:
        status_file = os.path.join(DATA_DIR, 'roles_status.json')
        if not os.path.exists(status_file):
            logger.error(f"Файл {status_file} не найден")
            return {}
        
        with open(status_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки roles_status.json: {e}")
        return {}

def get_all_seasons() -> list:
    """
    Возвращает список всех сезонов из roles_status.json
    """
    try:
        data = load_roles_status()
        seasons = []
        for season_data in data:
            if season_data.get('season'):
                seasons.append(season_data.get('season'))
        return seasons
    except Exception as e:
        logger.error(f"Ошибка получения списка сезонов: {e}")
        return []

def get_roles_by_season(season: str) -> list:
    """
    Возвращает список ролей для указанного сезона
    """
    try:
        data = load_roles_status()
        for season_data in data:
            if season_data.get('season') == season:
                return season_data.get('roles', [])
        return []
    except Exception as e:
        logger.error(f"Ошибка получения ролей для {season}: {e}")
        return []

def get_role_status(role_name: str, season: str) -> str:
    """
    Возвращает статус роли (free/pending/occupied)
    """
    try:
        roles = get_roles_by_season(season)
        for role in roles:
            if role.get('name') == role_name:
                return role.get('status', 'unknown')
        return 'unknown'
    except Exception as e:
        logger.error(f"Ошибка получения статуса роли {role_name} в {season}: {e}")
        return 'unknown'

def is_role_free(role_name: str, season: str) -> bool:
    """
    Проверяет, свободна ли роль
    """
    try:
        return get_role_status(role_name, season) == 'free'
    except Exception as e:
        logger.error(f"Ошибка проверки статуса роли {role_name} в {season}: {e}")
        return False

def get_role_info(role_name: str, season: str) -> dict:
    """
    Получает полную информацию о роли
    """
    try:
        roles = get_roles_by_season(season)
        for role in roles:
            if role.get('name') == role_name:
                return role
        return None
    except Exception as e:
        logger.error(f"Ошибка получения информации о роли {role_name} в {season}: {e}")
        return None

def get_all_roles() -> dict:
    """
    Возвращает все роли из всех сезонов в виде словаря {сезон: [роли]}
    """
    try:
        data = load_roles_status()
        result = {}
        for season_data in data:
            season = season_data.get('season')
            roles = season_data.get('roles', [])
            if season:
                result[season] = roles
        return result
    except Exception as e:
        logger.error(f"Ошибка получения всех ролей: {e}")
        return {}

def get_season_stats(season: str) -> dict:
    """
    Возвращает статистику по сезону
    """
    try:
        roles = get_roles_by_season(season)
        total = len(roles)
        free = sum(1 for r in roles if r.get('status') == 'free')
        occupied = sum(1 for r in roles if r.get('status') == 'occupied')
        pending = sum(1 for r in roles if r.get('status') == 'pending')
        
        return {
            'season': season,
            'total': total,
            'free': free,
            'occupied': occupied,
            'pending': pending,
            'free_percent': round((free / total * 100) if total > 0 else 0, 1)
        }
    except Exception as e:
        logger.error(f"Ошибка получения статистики по {season}: {e}")
        return {
            'season': season,
            'total': 0,
            'free': 0,
            'occupied': 0,
            'pending': 0,
            'free_percent': 0
        }

def get_all_seasons_stats() -> dict:
    """
    Возвращает статистику по всем сезонам
    """
    try:
        seasons = get_all_seasons()
        stats = {}
        for season in seasons:
            stats[season] = get_season_stats(season)
        return stats
    except Exception as e:
        logger.error(f"Ошибка получения статистики по всем сезонам: {e}")
        return {}

def get_free_roles_by_season(season: str) -> list:
    """
    Возвращает список свободных ролей в сезоне
    """
    try:
        roles = get_roles_by_season(season)
        return [role for role in roles if role.get('status') == 'free']
    except Exception as e:
        logger.error(f"Ошибка получения свободных ролей в {season}: {e}")
        return []

def get_occupied_roles_by_season(season: str) -> list:
    """
    Возвращает список занятых ролей в сезоне
    """
    try:
        roles = get_roles_by_season(season)
        return [role for role in roles if role.get('status') == 'occupied']
    except Exception as e:
        logger.error(f"Ошибка получения занятых ролей в {season}: {e}")
        return []

def get_pending_roles_by_season(season: str) -> list:
    """
    Возвращает список ролей в ожидании в сезоне
    """
    try:
        roles = get_roles_by_season(season)
        return [role for role in roles if role.get('status') == 'pending']
    except Exception as e:
        logger.error(f"Ошибка получения ролей в ожидании в {season}: {e}")
        return []

# ======================== ДОБАВЛЕННЫЕ ФУНКЦИИ ДЛЯ base_commands.py ========================

def get_taken_roles() -> list:
    """
    Возвращает список занятых ролей (формат для base_commands.py)
    """
    try:
        all_roles = get_all_roles()
        taken = []
        for season, roles in all_roles.items():
            for role in roles:
                if role.get('status') == 'occupied':
                    taken.append({
                        'season': season,
                        'role': role.get('name'),
                        'user': role.get('user', 'Неизвестно')
                    })
        return taken
    except Exception as e:
        logger.error(f"Ошибка получения занятых ролей: {e}")
        return []

def count_taken_roles() -> int:
    """
    Возвращает количество занятых ролей
    """
    try:
        return len(get_taken_roles())
    except Exception as e:
        logger.error(f"Ошибка подсчета занятых ролей: {e}")
        return 0

def get_user_role(user_id: int) -> str:
    """
    Возвращает роль пользователя по его ID
    """
    try:
        all_roles = get_all_roles()
        for season, roles in all_roles.items():
            for role in roles:
                if role.get('user_id') == user_id:
                    return role.get('name', '')
        return ''
    except Exception as e:
        logger.error(f"Ошибка получения роли пользователя {user_id}: {e}")
        return ''

# ======================== ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ СОВМЕСТИМОСТИ ========================

def get_seasons_list() -> list:
    """
    Возвращает список всех сезонов (алиас для get_all_seasons)
    """
    return get_all_seasons()

def update_role_status(role_name: str, season: str, status: str) -> bool:
    """
    Обновляет статус роли (free/pending/occupied)
    """
    try:
        status_file = os.path.join(DATA_DIR, 'roles_status.json')
        if not os.path.exists(status_file):
            logger.error(f"Файл {status_file} не найден")
            return False
        
        # Читаем текущие данные
        with open(status_file, 'r', encoding='utf-8') as f:
            roles_data = json.load(f)
        
        # Обновляем статус роли
        role_found = False
        for season_data in roles_data:
            if season_data.get('season') == season:
                for role in season_data.get('roles', []):
                    if role.get('name') == role_name:
                        old_status = role.get('status', 'unknown')
                        role['status'] = status
                        role_found = True
                        logger.info(f"Статус роли {role_name} в {season} изменен: {old_status} -> {status}")
                        break
                break
        
        if not role_found:
            logger.warning(f"Роль {role_name} не найдена в {season} для обновления статуса")
            return False
        
        # Сохраняем обновленные данные
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(roles_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Статус роли {role_name} в {season} обновлен на {status}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка обновления статуса роли {role_name} в {season}: {e}")
        return False
# ======================== ДОБАВЛЕННАЯ ФУНКЦИЯ ДЛЯ admin_commands.py ========================

def free_role(role_name: str, season: str) -> bool:
    """
    Освобождает роль (устанавливает статус 'free')
    Возвращает True, если роль успешно освобождена
    """
    try:
        return update_role_status(role_name, season, 'free')
    except Exception as e:
        logger.error(f"Ошибка освобождения роли {role_name} в {season}: {e}")
        return False
# ======================== ДОБАВЛЕННАЯ ФУНКЦИЯ ДЛЯ request_commands.py ========================

def get_role_by_name(role_name: str, season: str = None) -> dict:
    """
    Возвращает информацию о роли по её имени.
    Если season указан — ищет только в этом сезоне.
    Если season не указан — ищет во всех сезонах.
    """
    try:
        if season:
            # Ищем в конкретном сезоне
            role_info = get_role_info(role_name, season)
            if role_info:
                role_info['season'] = season
                return role_info
            return None
        
        # Ищем во всех сезонах
        all_roles = get_all_roles()
        for season_name, roles in all_roles.items():
            for role in roles:
                if role.get('name') == role_name:
                    role['season'] = season_name
                    return role
        return None
    except Exception as e:
        logger.error(f"Ошибка получения роли по имени {role_name}: {e}")
        return None
# ======================== ДОБАВЛЕННЫЕ ФУНКЦИИ ДЛЯ rest_commands.py ========================

def save_roles_status(roles_data: dict) -> bool:
    """
    Сохраняет данные в roles_status.json
    """
    try:
        status_file = os.path.join(DATA_DIR, 'roles_status.json')
        
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(roles_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Данные roles_status.json сохранены")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения roles_status.json: {e}")
        return False
# ======================== ДОБАВЛЕННЫЕ ФУНКЦИИ ДЛЯ settings_commands.py ========================

def get_system_settings() -> dict:
    """
    Загружает system_settings.json
    """
    try:
        settings_file = os.path.join(DATA_DIR, 'system_settings.json')
        if not os.path.exists(settings_file):
            # Если файла нет — создаём со значениями по умолчанию
            default_settings = {
                'closed_mode': False,
                'reminder_enabled': True,
                'welcome_enabled': True,
                'auto_unrest': True,
                'call_cooldown': 30,
                'callfal_cooldown': 60,
                'max_rest_days': 14
            }
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(default_settings, f, ensure_ascii=False, indent=2)
            return default_settings
        
        with open(settings_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки system_settings.json: {e}")
        return {}

def save_system_settings(settings: dict) -> bool:
    """
    Сохраняет system_settings.json
    """
    try:
        settings_file = os.path.join(DATA_DIR, 'system_settings.json')
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        logger.info("✅ system_settings.json сохранён")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения system_settings.json: {e}")
        return False

def get_closed_mode() -> bool:
    """
    Возвращает True, если набор ролей закрыт.
    """
    try:
        settings = get_system_settings()
        return settings.get('closed_mode', False)
    except Exception as e:
        logger.error(f"Ошибка получения closed_mode: {e}")
        return False

def set_closed_mode(value: bool) -> bool:
    """
    Устанавливает режим закрытого набора.
    """
    try:
        settings = get_system_settings()
        settings['closed_mode'] = value
        return save_system_settings(settings)
    except Exception as e:
        logger.error(f"Ошибка установки closed_mode: {e}")
        return False