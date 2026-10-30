import os
import zipfile
import time
import datetime
import logging
from config import DATA_DIR, ROLES_STATUS_FILE, SYSTEM_SETTINGS_FILE

logger = logging.getLogger(__name__)
BACKUP_DIR = r"C:\Users\olika\PyCharmMiscProject\backup"
BACKUP_MAX_AGE_DAYS = 90

def create_backup() -> str:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    zip_filename = os.path.join(BACKUP_DIR, f"loez_backup_{timestamp}.zip")
    files_to_backup = [
        os.path.join(DATA_DIR, 'users', 'users.json'),
        os.path.join(DATA_DIR, 'admins', 'admins.json'),
        ROLES_STATUS_FILE, SYSTEM_SETTINGS_FILE,
        os.path.join(DATA_DIR, 'system', 'requests.json'),
        os.path.join(DATA_DIR, 'system', 'message_counts.json'),
    ]
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in files_to_backup:
            if os.path.exists(file_path):
                zipf.write(file_path, arcname=os.path.basename(file_path))
                
    # Очистка старых
    now = time.time()
    for filename in os.listdir(BACKUP_DIR):
        if filename.endswith(".zip"):
            filepath = os.path.join(BACKUP_DIR, filename)
            if os.path.getmtime(filepath) < now - (BACKUP_MAX_AGE_DAYS * 86400):
                try: os.remove(filepath)
                except Exception: pass
    return zip_filename