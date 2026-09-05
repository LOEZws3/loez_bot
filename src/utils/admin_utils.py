import os
from config import ADMINS_FILE, OWNER_ID
from .file_utils import ensure_dirs


def load_admins():
    if not os.path.exists(ADMINS_FILE):
        return []
    admins = []
    with open(ADMINS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split('|')
            if len(parts) >= 4:
                user_id, username, full_name, rank = parts[:4]
                admins.append({
                    'id': int(user_id),
                    'username': username if username != 'None' else None,
                    'full_name': full_name,
                    'rank': int(rank)
                })
            elif len(parts) == 3:
                user_id, username, full_name = parts
                rank = 1 if (OWNER_ID and int(user_id) == OWNER_ID) else 2
                admins.append({
                    'id': int(user_id),
                    'username': username if username != 'None' else None,
                    'full_name': full_name,
                    'rank': rank
                })
    if OWNER_ID is None and admins and admins[0]['rank'] != 1:
        admins[0]['rank'] = 1
        save_admins(admins)
    return admins


def save_admins(admins):
    ensure_dirs()
    with open(ADMINS_FILE, 'w', encoding='utf-8') as f:
        for a in admins:
            f.write(f"{a['id']}|{a['username'] or 'None'}|{a['full_name']}|{a['rank']}\n")


def add_admin(user_id, username, full_name, rank=None):
    admins = load_admins()
    for a in admins:
        if a['id'] == user_id:
            return False
    if rank is None:
        rank = 1 if not admins else 2
    admins.append({
        'id': user_id,
        'username': username,
        'full_name': full_name,
        'rank': rank
    })
    save_admins(admins)
    return True


def get_admin_rank(user_id):
    admins = load_admins()
    for a in admins:
        if a['id'] == user_id:
            return a['rank']
    return None


def is_admin(user_id):
    return get_admin_rank(user_id) is not None


def is_owner(user_id):
    return get_admin_rank(user_id) == 1


def set_rank(user_id, new_rank):
    admins = load_admins()
    for a in admins:
        if a['id'] == user_id:
            a['rank'] = new_rank
            save_admins(admins)
            return True
    return False