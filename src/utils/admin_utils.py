import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

ADMINS_FILE = "data/admins/admins.txt"
OWNER_ID = 8076284478  # Ваш ID


def load_admins() -> List[Dict]:
    """Загружает список администраторов"""
    if not os.path.exists(ADMINS_FILE):
        return []
    
    admins = []
    try:
        with open(ADMINS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split('|')
                if len(parts) >= 4:
                    admins.append({
                        'id': int(parts[0]),
                        'username': parts[1] if parts[1] else None,
                        'full_name': parts[2],
                        'rank': int(parts[3]) if parts[3].isdigit() else 2
                    })
                elif len(parts) >= 3:
                    admins.append({
                        'id': int(parts[0]),
                        'username': parts[1] if parts[1] else None,
                        'full_name': parts[2],
                        'rank': 2
                    })
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки админов: {e}")
    
    return admins


def save_admins(admins: List[Dict]):
    """Сохраняет список администраторов"""
    try:
        os.makedirs(os.path.dirname(ADMINS_FILE), exist_ok=True)
        with open(ADMINS_FILE, 'w', encoding='utf-8') as f:
            for admin in admins:
                username = admin.get('username', '') or ''
                full_name = admin.get('full_name', 'Неизвестный')
                rank = admin.get('rank', 2)
                f.write(f"{admin['id']}|{username}|{full_name}|{rank}\n")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения админов: {e}")
        return False


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    if user_id == OWNER_ID:
        return True
    admins = load_admins()
    for admin in admins:
        if admin['id'] == user_id:
            return True
    return False


def is_owner(user_id: int) -> bool:
    """Проверяет, является ли пользователь владельцем"""
    return user_id == OWNER_ID


def get_admin_rank(user_id: int) -> int:
    """Возвращает ранг пользователя (1-Владелец, 2-Админ, 3-Модератор)"""
    if user_id == OWNER_ID:
        return 1
    admins = load_admins()
    for admin in admins:
        if admin['id'] == user_id:
            return admin.get('rank', 2)
    return 0


def add_admin(user_id: int, username: str = None, full_name: str = None, rank: int = 2) -> bool:
    """Добавляет администратора"""
    if is_admin(user_id):
        return False
    
    admins = load_admins()
    admins.append({
        'id': user_id,
        'username': username or '',
        'full_name': full_name or f"User {user_id}",
        'rank': rank
    })
    return save_admins(admins)


def remove_admin(user_id: int) -> bool:
    """Удаляет администратора"""
    if user_id == OWNER_ID:
        return False
    
    admins = load_admins()
    new_admins = [a for a in admins if a['id'] != user_id]
    if len(new_admins) == len(admins):
        return False
    return save_admins(new_admins)


def set_rank(user_id: int, rank: int) -> bool:
    """Устанавливает ранг администратора"""
    if user_id == OWNER_ID:
        return False
    
    admins = load_admins()
    for admin in admins:
        if admin['id'] == user_id:
            admin['rank'] = rank
            return save_admins(admins)
    return False


def get_admin_info(user_id: int) -> Optional[Dict]:
    """Возвращает информацию об администраторе"""
    admins = load_admins()
    for admin in admins:
        if admin['id'] == user_id:
            return admin
    return None