import os
import datetime
import json
from pathlib import Path
from config import DATA_DIR, ADMINS_FILE, USERS_FILE, CREATION_FILE, FORWARD_FILE


def ensure_dirs():
    for dir_path in [DATA_DIR, ADMINS_FILE.parent, USERS_FILE.parent, CREATION_FILE.parent]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)


def get_creation_date():
    ensure_dirs()
    if not os.path.exists(CREATION_FILE):
        with open(CREATION_FILE, 'w', encoding='utf-8') as f:
            f.write(datetime.date.today().isoformat())
    with open(CREATION_FILE, 'r', encoding='utf-8') as f:
        return datetime.date.fromisoformat(f.read().strip())


def days_since_creation():
    delta = datetime.date.today() - get_creation_date()
    return delta.days


def load_forward_map():
    ensure_dirs()
    if os.path.exists(FORWARD_FILE):
        try:
            with open(FORWARD_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {int(k): int(v) for k, v in data.items()}
        except:
            return {}
    return {}


def save_forward_map(forward_map):
    ensure_dirs()
    with open(FORWARD_FILE, 'w', encoding='utf-8') as f:
        json.dump(forward_map, f, ensure_ascii=False, indent=2)