import os
import json
from config import DATA_DIR
from .file_utils import ensure_dirs

HISTORY_DIR = DATA_DIR / "users_history"

def ensure_history_dir():
    ensure_dirs()
    if not os.path.exists(HISTORY_DIR):
        os.makedirs(HISTORY_DIR)

def load_user_history(user_id):
    ensure_history_dir()
    file_path = HISTORY_DIR / f"{user_id}.json"
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_user_history(user_id, data):
    ensure_history_dir()
    file_path = HISTORY_DIR / f"{user_id}.json"
    history = load_user_history(user_id)
    history.update(data)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def save_user_emoji(user_id, emoji):
    save_user_history(user_id, {"emoji": emoji})