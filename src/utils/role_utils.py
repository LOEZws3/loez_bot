import os
import json
import logging
from config import DATA_DIR

logger = logging.getLogger(__name__)

# ======================== БАЗОВЫЕ ФУНКЦИИ РАБОТЫ С ФАЙЛОМ ========================

def load_roles_status() -> dict:
    """
    Загружает roles_status.json.
    Структура: {"Имя персонажа": {"status": "свободна", "owner_id": ..., "username": ..., "season": "...", "extra": ""}, ...}
    """
    try:
        status_file = os.path.join(DATA_DIR, 'roles', 'roles_status.json')
        if not os.path.exists(status_file):
            logger.error(f"Файл {status_file} не найден")
            return {}
        
        with open(status_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, dict):
            logger.error(f"roles_status.json имеет неверный формат: ожидался dict, получен {type(data).__name__}")
            return {}
        
        return data
    except Exception as e:
        logger.error(f"Ошибка загрузки roles_status.json: {e}")
        return {}

def save_roles_status(roles_data: dict) -> bool:
    """Сохраняет данные в roles_status.json"""
    try:
        status_file = os.path.join(DATA_DIR, 'roles', 'roles_status.json')
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(roles_data, f, ensure_ascii=False, indent=2)
        logger.info("✅ Данные roles_status.json сохранены")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения roles_status.json: {e}")
        return False

# ======================== СЕЗОНЫ И РОЛИ ========================

def get_seasons_list() -> list:
    """Возвращает список уникальных сезонов"""
    try:
        data = load_roles_status()
        seasons = set()
        for role_name, role_info in data.items():
            if isinstance(role_info, dict):
                season = role_info.get('season')
                if season:
                    seasons.add(season)
        result = sorted(list(seasons))
        logger.debug(f"Загружены сезоны: {result}")
        return result
    except Exception as e:
        logger.error(f"Ошибка получения списка сезонов: {e}")
        return []

def get_all_seasons() -> list:
    """Алиас для get_seasons_list()"""
    return get_seasons_list()

def get_roles_by_season(season: str) -> list:
    """Возвращает список ролей для указанного сезона"""
    try:
        data = load_roles_status()
        roles = []
        for role_name, role_info in data.items():
            if isinstance(role_info, dict) and role_info.get('season') == season:
                role = dict(role_info)
                role['name'] = role_name
                roles.append(role)
        logger.debug(f"Загружены роли для {season}: {len(roles)}")
        return roles
    except Exception as e:
        logger.error(f"Ошибка получения ролей для {season}: {e}")
        return []

def get_role_by_name(role_name: str, season: str = None) -> dict:
    """Возвращает информацию о роли по имени"""
    try:
        data = load_roles_status()
        role_info = data.get(role_name)
        if not role_info or not isinstance(role_info, dict):
            return None
        if season and role_info.get('season') != season:
            return None
        result = dict(role_info)
        result['name'] = role_name
        return result
    except Exception as e:
        logger.error(f"Ошибка получения роли по имени {role_name}: {e}")
        return None

def get_role_info(role_name: str, season: str = None) -> dict:
    """Алиас для get_role_by_name()"""
    return get_role_by_name(role_name, season)

def get_role_status(role_name: str, season: str = None) -> str:
    """Возвращает статус роли: "свободна" / "занята" """
    try:
        role = get_role_by_name(role_name, season)
        if role:
            return role.get('status', 'unknown')
        return 'unknown'
    except Exception as e:
        logger.error(f"Ошибка получения статуса роли {role_name}: {e}")
        return 'unknown'

def is_role_free(role_name: str, season: str = None) -> bool:
    """Проверяет, свободна ли роль (status == "свободна")"""
    try:
        return get_role_status(role_name, season) == 'свободна'
    except Exception as e:
        logger.error(f"Ошибка проверки статуса роли {role_name}: {e}")
        return False

def update_role_status(role_name: str, season: str, status: str) -> bool:
    """Обновляет статус роли (свободна / занята / ожидает)"""
    try:
        data = load_roles_status()
        if role_name not in data:
            logger.warning(f"Роль {role_name} не найдена в roles_status.json")
            return False
        
        if season and data[role_name].get('season') != season:
            logger.warning(f"Роль {role_name} не принадлежит сезону {season}")
            return False
        
        old_status = data[role_name].get('status', 'unknown')
        data[role_name]['status'] = status
        
        if save_roles_status(data):
            logger.info(f"✅ Статус роли {role_name}: {old_status} -> {status}")
            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка обновления статуса роли {role_name}: {e}")
        return False

def free_role(role_name: str, season: str = None) -> bool:
    """Освобождает роль (status = "свободна")"""
    try:
        data = load_roles_status()
        if role_name not in data:
            logger.warning(f"Роль {role_name} не найдена")
            return False
        
        data[role_name]['status'] = 'свободна'
        data[role_name]['owner_id'] = None
        data[role_name]['username'] = None
        
        if save_roles_status(data):
            logger.info(f"✅ Роль {role_name} освобождена")
            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка освобождения роли {role_name}: {e}")
        return False

# ======================== ПОЛЬЗОВАТЕЛИ И РОЛИ ========================

def get_user_role(user_id: int) -> str:
    """Возвращает имя роли, которую занимает пользователь"""
    try:
        data = load_roles_status()
        for role_name, role_info in data.items():
            if isinstance(role_info, dict) and role_info.get('owner_id') == user_id:
                return role_name
        return ''
    except Exception as e:
        logger.error(f"Ошибка получения роли пользователя {user_id}: {e}")
        return ''

def get_taken_roles() -> list:
    """Возвращает список занятых ролей"""
    try:
        data = load_roles_status()
        taken = []
        for role_name, role_info in data.items():
            if isinstance(role_info, dict) and role_info.get('status') == 'занята':
                taken.append({
                    'season': role_info.get('season', ''),
                    'role': role_name,
                    'user': role_info.get('username') or 'Неизвестно'
                })
        return taken
    except Exception as e:
        logger.error(f"Ошибка получения занятых ролей: {e}")
        return []

def count_taken_roles() -> int:
    """Возвращает количество занятых ролей"""
    return len(get_taken_roles())

# ======================== СТАТИСТИКА ========================

def get_all_roles() -> dict:
    """Возвращает все роли в виде {сезон: [роли]}"""
    try:
        data = load_roles_status()
        result = {}
        for role_name, role_info in data.items():
            if isinstance(role_info, dict):
                season = role_info.get('season', 'Без сезона')
                if season not in result:
                    result[season] = []
                role = dict(role_info)
                role['name'] = role_name
                result[season].append(role)
        return result
    except Exception as e:
        logger.error(f"Ошибка получения всех ролей: {e}")
        return {}

def get_season_stats(season: str) -> dict:
    """Статистика по сезону"""
    try:
        roles = get_roles_by_season(season)
        total = len(roles)
        free = sum(1 for r in roles if r.get('status') == 'свободна')
        occupied = sum(1 for r in roles if r.get('status') == 'занята')
        
        return {
            'season': season,
            'total': total,
            'free': free,
            'occupied': occupied,
            'free_percent': round((free / total * 100) if total > 0 else 0, 1)
        }
    except Exception as e:
        logger.error(f"Ошибка статистики по {season}: {e}")
        return {'season': season, 'total': 0, 'free': 0, 'occupied': 0, 'free_percent': 0}

def get_all_seasons_stats() -> dict:
    """Статистика по всем сезонам"""
    return {season: get_season_stats(season) for season in get_seasons_list()}

def get_free_roles_by_season(season: str) -> list:
    """Свободные роли в сезоне"""
    return [r for r in get_roles_by_season(season) if r.get('status') == 'свободна']

def get_occupied_roles_by_season(season: str) -> list:
    """Занятые роли в сезоне"""
    return [r for r in get_roles_by_season(season) if r.get('status') == 'занята']

# ======================== НАСТРОЙКИ СИСТЕМЫ ========================

def get_system_settings() -> dict:
    """Загружает system_settings.json"""
    try:
        settings_file = os.path.join(DATA_DIR, 'system', 'system_settings.json')
        if not os.path.exists(settings_file):
            default = {
                'closed_mode': False,
                'reminder_enabled': True,
                'welcome_enabled': True,
                'auto_unrest': True,
                'call_cooldown': 30,
                'callfal_cooldown': 60,
                'max_rest_days': 14
            }
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
            return default
        
        with open(settings_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки system_settings.json: {e}")
        return {}

def save_system_settings(settings: dict) -> bool:
    """Сохраняет system_settings.json"""
    try:
        settings_file = os.path.join(DATA_DIR, 'system', 'system_settings.json')
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения system_settings.json: {e}")
        return False

def get_closed_mode() -> bool:
    """Возвращает True, если набор закрыт"""
    try:
        return get_system_settings().get('closed_mode', False)
    except Exception as e:
        logger.error(f"Ошибка получения closed_mode: {e}")
        return False

def set_closed_mode(value: bool) -> bool:
    """Устанавливает режим закрытого набора"""
    try:
        settings = get_system_settings()
        settings['closed_mode'] = value
        return save_system_settings(settings)
    except Exception as e:
        logger.error(f"Ошибка установки closed_mode: {e}")
        return False