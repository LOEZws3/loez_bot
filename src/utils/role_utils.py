import os
import json
import logging
from config import DATA_DIR

logger = logging.getLogger(__name__)

def get_seasons_list() -> list:
    """
    Возвращает список всех сезонов из roles_status.json
    """
    try:
        status_file = os.path.join(DATA_DIR, 'roles_status.json')
        if not os.path.exists(status_file):
            logger.error(f"Файл {status_file} не найден")
            return []
        
        with open(status_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        seasons = []
        for season_data in data:
            if season_data.get('season'):
                seasons.append(season_data.get('season'))
        
        logger.debug(f"Загружены сезоны: {seasons}")
        return seasons
    except Exception as e:
        logger.error(f"Ошибка получения списка сезонов: {e}")
        return []

def get_roles_by_season(season: str) -> list:
    """
    Возвращает список ролей для указанного сезона
    """
    try:
        status_file = os.path.join(DATA_DIR, 'roles_status.json')
        if not os.path.exists(status_file):
            logger.error(f"Файл {status_file} не найден")
            return []
        
        with open(status_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for season_data in data:
            if season_data.get('season') == season:
                roles = season_data.get('roles', [])
                logger.debug(f"Загружены роли для {season}: {len(roles)}")
                return roles
        
        logger.warning(f"Сезон {season} не найден")
        return []
    except Exception as e:
        logger.error(f"Ошибка получения ролей для {season}: {e}")
        return []

def is_role_free(role_name: str, season: str) -> bool:
    """
    Проверяет, свободна ли роль
    """
    try:
        roles = get_roles_by_season(season)
        for role in roles:
            if role.get('name') == role_name:
                status = role.get('status', 'occupied')
                is_free = status == 'free'
                logger.debug(f"Роль {role_name} в {season}: статус {status}, свободна: {is_free}")
                return is_free
        
        logger.warning(f"Роль {role_name} не найдена в {season}")
        return False
    except Exception as e:
        logger.error(f"Ошибка проверки статуса роли {role_name} в {season}: {e}")
        return False

def update_role_status(role_name: str, season: str, status: str):
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

def get_role_info(role_name: str, season: str) -> dict:
    """
    Получает полную информацию о роли
    """
    try:
        roles = get_roles_by_season(season)
        for role in roles:
            if role.get('name') == role_name:
                logger.debug(f"Найдена роль {role_name} в {season}: {role}")
                return role
        
        logger.warning(f"Роль {role_name} не найдена в {season}")
        return None
    except Exception as e:
        logger.error(f"Ошибка получения информации о роли {role_name} в {season}: {e}")
        return None

def get_all_roles() -> dict:
    """
    Возвращает все роли из всех сезонов в виде словаря {сезон: [роли]}
    """
    try:
        status_file = os.path.join(DATA_DIR, 'roles_status.json')
        if not os.path.exists(status_file):
            logger.error(f"Файл {status_file} не найден")
            return {}
        
        with open(status_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        result = {}
        for season_data in data:
            season = season_data.get('season')
            roles = season_data.get('roles', [])
            if season:
                result[season] = roles
        
        logger.debug(f"Загружены все роли: {len(result)} сезонов")
        return result
    except Exception as e:
        logger.error(f"Ошибка получения всех ролей: {e}")
        return {}

def get_role_status(role_name: str, season: str) -> str:
    """
    Возвращает статус роли (free/pending/occupied)
    """
    try:
        role_info = get_role_info(role_name, season)
        if role_info:
            return role_info.get('status', 'unknown')
        return 'unknown'
    except Exception as e:
        logger.error(f"Ошибка получения статуса роли {role_name} в {season}: {e}")
        return 'unknown'

def get_free_roles_by_season(season: str) -> list:
    """
    Возвращает список свободных ролей в сезоне
    """
    try:
        roles = get_roles_by_season(season)
        free_roles = [role for role in roles if role.get('status') == 'free']
        logger.debug(f"Свободные роли в {season}: {len(free_roles)}")
        return free_roles
    except Exception as e:
        logger.error(f"Ошибка получения свободных ролей в {season}: {e}")
        return []

def get_occupied_roles_by_season(season: str) -> list:
    """
    Возвращает список занятых ролей в сезоне
    """
    try:
        roles = get_roles_by_season(season)
        occupied_roles = [role for role in roles if role.get('status') == 'occupied']
        logger.debug(f"Занятые роли в {season}: {len(occupied_roles)}")
        return occupied_roles
    except Exception as e:
        logger.error(f"Ошибка получения занятых ролей в {season}: {e}")
        return []

def get_pending_roles_by_season(season: str) -> list:
    """
    Возвращает список ролей в ожидании в сезоне
    """
    try:
        roles = get_roles_by_season(season)
        pending_roles = [role for role in roles if role.get('status') == 'pending']
        logger.debug(f"Роли в ожидании в {season}: {len(pending_roles)}")
        return pending_roles
    except Exception as e:
        logger.error(f"Ошибка получения ролей в ожидании в {season}: {e}")
        return []

def get_role_description(role_name: str, season: str) -> str:
    """
    Возвращает описание роли
    """
    try:
        role_info = get_role_info(role_name, season)
        if role_info:
            return role_info.get('description', 'Описание отсутствует')
        return 'Описание отсутствует'
    except Exception as e:
        logger.error(f"Ошибка получения описания роли {role_name} в {season}: {e}")
        return 'Описание отсутствует'

def get_role_requirements(role_name: str, season: str) -> list:
    """
    Возвращает требования к роли
    """
    try:
        role_info = get_role_info(role_name, season)
        if role_info:
            return role_info.get('requirements', [])
        return []
    except Exception as e:
        logger.error(f"Ошибка получения требований роли {role_name} в {season}: {e}")
        return []

def count_roles_by_season(season: str) -> int:
    """
    Возвращает количество ролей в сезоне
    """
    try:
        roles = get_roles_by_season(season)
        return len(roles)
    except Exception as e:
        logger.error(f"Ошибка подсчета ролей в {season}: {e}")
        return 0

def count_free_roles_by_season(season: str) -> int:
    """
    Возвращает количество свободных ролей в сезоне
    """
    try:
        free_roles = get_free_roles_by_season(season)
        return len(free_roles)
    except Exception as e:
        logger.error(f"Ошибка подсчета свободных ролей в {season}: {e}")
        return 0

def count_occupied_roles_by_season(season: str) -> int:
    """
    Возвращает количество занятых ролей в сезоне
    """
    try:
        occupied_roles = get_occupied_roles_by_season(season)
        return len(occupied_roles)
    except Exception as e:
        logger.error(f"Ошибка подсчета занятых ролей в {season}: {e}")
        return 0

def count_pending_roles_by_season(season: str) -> int:
    """
    Возвращает количество ролей в ожидании в сезоне
    """
    try:
        pending_roles = get_pending_roles_by_season(season)
        return len(pending_roles)
    except Exception as e:
        logger.error(f"Ошибка подсчета ролей в ожидании в {season}: {e}")
        return 0

def get_season_stats(season: str) -> dict:
    """
    Возвращает статистику по сезону
    """
    try:
        total = count_roles_by_season(season)
        free = count_free_roles_by_season(season)
        occupied = count_occupied_roles_by_season(season)
        pending = count_pending_roles_by_season(season)
        
        stats = {
            'season': season,
            'total': total,
            'free': free,
            'occupied': occupied,
            'pending': pending,
            'free_percent': round((free / total * 100) if total > 0 else 0, 1)
        }
        
        logger.debug(f"Статистика по {season}: {stats}")
        return stats
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
        seasons = get_seasons_list()
        stats = {}
        for season in seasons:
            stats[season] = get_season_stats(season)
        
        logger.debug(f"Статистика по всем сезонам: {len(stats)} сезонов")
        return stats
    except Exception as e:
        logger.error(f"Ошибка получения статистики по всем сезонам: {e}")
        return {}

def validate_role_status(role_name: str, season: str) -> bool:
    """
    Проверяет, валидный ли статус у роли
    """
    try:
        valid_statuses = ['free', 'occupied', 'pending']
        status = get_role_status(role_name, season)
        return status in valid_statuses
    except Exception as e:
        logger.error(f"Ошибка проверки статуса роли {role_name} в {season}: {e}")
        return False
# ======================== ДОБАВЛЕННЫЕ ФУНКЦИИ ДЛЯ НОВОГО ИНТЕРФЕЙСА ========================

def get_seasons_list() -> list:
    """
    Возвращает список всех сезонов из roles_status.json
    """
    try:
        status_file = os.path.join(DATA_DIR, 'roles_status.json')
        if not os.path.exists(status_file):
            logger.error(f"Файл {status_file} не найден")
            return []
        
        with open(status_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        seasons = []
        for season_data in data:
            if season_data.get('season'):
                seasons.append(season_data.get('season'))
        
        logger.debug(f"Загружены сезоны: {seasons}")
        return seasons
    except Exception as e:
        logger.error(f"Ошибка получения списка сезонов: {e}")
        return []

def get_roles_by_season(season: str) -> list:
    """
    Возвращает список ролей для указанного сезона
    """
    try:
        status_file = os.path.join(DATA_DIR, 'roles_status.json')
        if not os.path.exists(status_file):
            logger.error(f"Файл {status_file} не найден")
            return []
        
        with open(status_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for season_data in data:
            if season_data.get('season') == season:
                roles = season_data.get('roles', [])
                logger.debug(f"Загружены роли для {season}: {len(roles)}")
                return roles
        
        logger.warning(f"Сезон {season} не найден")
        return []
    except Exception as e:
        logger.error(f"Ошибка получения ролей для {season}: {e}")
        return []

def is_role_free(role_name: str, season: str) -> bool:
    """
    Проверяет, свободна ли роль
    """
    try:
        roles = get_roles_by_season(season)
        for role in roles:
            if role.get('name') == role_name:
                status = role.get('status', 'occupied')
                is_free = status == 'free'
                logger.debug(f"Роль {role_name} в {season}: статус {status}, свободна: {is_free}")
                return is_free
        
        logger.warning(f"Роль {role_name} не найдена в {season}")
        return False
    except Exception as e:
        logger.error(f"Ошибка проверки статуса роли {role_name} в {season}: {e}")
        return False

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
    