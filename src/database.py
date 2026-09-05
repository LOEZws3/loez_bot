import aiosqlite
import json
import os
import asyncio
from datetime import datetime
from typing import Optional, Dict, List, Any
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
        self._lock = asyncio.Lock()
    
    async def init(self):
        """Создание всех таблиц"""
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица ролей
            await db.execute("""
                CREATE TABLE IF NOT EXISTS roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    season TEXT NOT NULL,
                    status TEXT DEFAULT 'свободна',
                    owner_id INTEGER DEFAULT NULL,
                    username TEXT DEFAULT NULL,
                    rest_until INTEGER DEFAULT NULL,
                    extra TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица пользователей
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    role_index TEXT DEFAULT '0',
                    is_admin BOOLEAN DEFAULT 0,
                    is_subscribed_to_calls BOOLEAN DEFAULT 1,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица заявок на роли
            await db.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role_name TEXT NOT NULL,
                    position TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (role_name) REFERENCES roles(name)
                )
            """)
            
            # Таблица заявок на рест
            await db.execute("""
                CREATE TABLE IF NOT EXISTS rest_applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role_name TEXT NOT NULL,
                    days INTEGER NOT NULL,
                    reason TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (role_name) REFERENCES roles(name)
                )
            """)
            
            # Индексы
            await db.execute("CREATE INDEX IF NOT EXISTS idx_roles_status ON roles(status)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_roles_owner ON roles(owner_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_applications_user ON applications(user_id)")
            
            await db.commit()
            logger.info("✅ Таблицы БД созданы")
    
    # ============================================================
    # МИГРАЦИЯ ИЗ JSON
    # ============================================================
    
    async def migrate_from_json(self):
        """Перенос данных из JSON-файлов в SQLite"""
        logger.info("🔄 Начинаю миграцию данных...")
        
        # 1. Перенос ролей из roles_status.json
        await self._migrate_roles()
        
        # 2. Перенос пользователей из users.txt
        await self._migrate_users()
        
        # 3. Перенос заявок из requests.json
        await self._migrate_applications()
        
        # 4. Перенос рестов из roles_status.json
        await self._migrate_rests()
        
        logger.info("✅ Миграция данных завершена!")
    
    async def _migrate_roles(self):
        """Перенос ролей из roles_status.json"""
        try:
            with open("data/roles_status.json", "r", encoding="utf-8") as f:
                roles_data = json.load(f)
        except FileNotFoundError:
            logger.warning("⚠️ roles_status.json не найден, пропускаю")
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            for name, data in roles_data.items():
                rest_until = None
                if data.get("status") == "рест" and data.get("extra"):
                    try:
                        rest_until = int(datetime.strptime(data["extra"], "%Y-%m-%d").timestamp())
                    except:
                        rest_until = None
                
                await db.execute(
                    """INSERT OR REPLACE INTO roles 
                       (name, season, status, owner_id, username, rest_until, extra) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        name,
                        data.get("season", "Неизвестно"),
                        data.get("status", "свободна"),
                        data.get("owner_id"),
                        data.get("username"),
                        rest_until,
                        data.get("extra", "")
                    )
                )
            await db.commit()
            logger.info(f"✅ Перенесено ролей: {len(roles_data)}")
    
    async def _migrate_users(self):
        """Перенос пользователей из users.txt"""
        users_file = "data/users/users.txt"
        if not os.path.exists(users_file):
            logger.warning("⚠️ users.txt не найден, пропускаю")
            return
        
        users = []
        try:
            with open(users_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split('|')
                    if len(parts) >= 4:
                        users.append({
                            'id': int(parts[0]),
                            'username': parts[1] if parts[1] else None,
                            'full_name': parts[2],
                            'role_index': parts[3] if len(parts) > 3 else '0',
                            'extra': parts[4] if len(parts) > 4 else ''
                        })
        except Exception as e:
            logger.error(f"❌ Ошибка чтения users.txt: {e}")
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            for u in users:
                await db.execute(
                    """INSERT OR REPLACE INTO users 
                       (id, username, full_name, role_index) 
                       VALUES (?, ?, ?, ?)""",
                    (u['id'], u['username'], u['full_name'], u['role_index'])
                )
            await db.commit()
            logger.info(f"✅ Перенесено пользователей: {len(users)}")
    
    async def _migrate_applications(self):
        """Перенос заявок из requests.json"""
        try:
            with open("data/system/requests.json", "r", encoding="utf-8") as f:
                requests_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logger.warning("⚠️ requests.json не найден или пуст, пропускаю")
            return
        
        if not requests_data:
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            for req in requests_data:
                if req.get('status') == 'pending':
                    await db.execute(
                        """INSERT INTO applications 
                           (user_id, role_name, position, status, created_at) 
                           VALUES (?, ?, ?, ?, ?)""",
                        (
                            req.get('user_id'),
                            req.get('role'),
                            req.get('position'),
                            req.get('status', 'pending'),
                            req.get('created_at', datetime.now().isoformat())
                        )
                    )
            await db.commit()
            pending = [r for r in requests_data if r.get('status') == 'pending']
            logger.info(f"✅ Перенесено активных заявок: {len(pending)}")
    
    async def _migrate_rests(self):
        """Перенос рестов из roles_status.json"""
        try:
            with open("data/roles_status.json", "r", encoding="utf-8") as f:
                roles_data = json.load(f)
        except FileNotFoundError:
            return
        
        rests = []
        for name, data in roles_data.items():
            if data.get('status') == 'рест' and data.get('owner_id'):
                rests.append({
                    'user_id': data['owner_id'],
                    'role_name': name,
                    'days': 7,  # По умолчанию
                    'reason': data.get('extra', ''),
                    'status': 'approved'
                })
        
        if not rests:
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            for rest in rests:
                await db.execute(
                    """INSERT INTO rest_applications 
                       (user_id, role_name, days, reason, status) 
                       VALUES (?, ?, ?, ?, ?)""",
                    (rest['user_id'], rest['role_name'], rest['days'], rest['reason'], rest['status'])
                )
            await db.commit()
            logger.info(f"✅ Перенесено рестов: {len(rests)}")
    
    # ============================================================
    # РАБОТА С РОЛЯМИ
    # ============================================================
    
    async def get_role(self, name: str) -> Optional[Dict]:
        """Получить информацию о роли"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM roles WHERE name = ?", (name,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def get_all_roles(self) -> List[Dict]:
        """Получить все роли"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM roles ORDER BY name") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_roles_by_status(self, status: str) -> List[Dict]:
        """Получить роли по статусу"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM roles WHERE status = ?", (status,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_user_role(self, user_id: int) -> Optional[Dict]:
        """Найти роль пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM roles WHERE owner_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def take_role(self, role_name: str, user_id: int, username: str) -> bool:
        """Выдать роль пользователю"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                role = await self.get_role(role_name)
                if not role or role['status'] != 'свободна':
                    return False
                
                existing = await self.get_user_role(user_id)
                if existing:
                    return False
                
                await db.execute(
                    """UPDATE roles SET 
                       status = 'занята', 
                       owner_id = ?, 
                       username = ?, 
                       rest_until = NULL 
                       WHERE name = ?""",
                    (user_id, username, role_name)
                )
                await db.commit()
                return True
    
    async def release_role(self, user_id: int) -> bool:
        """Освободить роль пользователя"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                role = await self.get_user_role(user_id)
                if not role:
                    return False
                
                await db.execute(
                    """UPDATE roles SET 
                       status = 'свободна', 
                       owner_id = NULL, 
                       username = NULL, 
                       rest_until = NULL 
                       WHERE owner_id = ?""",
                    (user_id,)
                )
                await db.commit()
                return True
    
    async def set_rest(self, role_name: str, days: int) -> bool:
        """Установить рест для роли"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                role = await self.get_role(role_name)
                if not role or role['status'] != 'занята':
                    return False
                
                rest_until = int(datetime.now().timestamp()) + (days * 86400)
                
                await db.execute(
                    """UPDATE roles SET 
                       status = 'рест', 
                       rest_until = ? 
                       WHERE name = ?""",
                    (rest_until, role_name)
                )
                await db.commit()
                return True
    
    async def remove_rest(self, role_name: str) -> bool:
        """Снять рест с роли"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                role = await self.get_role(role_name)
                if not role or role['status'] != 'рест':
                    return False
                
                await db.execute(
                    """UPDATE roles SET 
                       status = 'занята', 
                       rest_until = NULL 
                       WHERE name = ?""",
                    (role_name,)
                )
                await db.commit()
                return True
    
    async def check_expired_rests(self) -> List[Dict]:
        """Найти и снять истекшие ресты"""
        now = int(datetime.now().timestamp())
        expired = []
        
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM roles WHERE status = 'рест' AND rest_until <= ?",
                    (now,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    expired = [dict(row) for row in rows]
                
                if expired:
                    names = [row['name'] for row in expired]
                    placeholders = ','.join(['?'] * len(names))
                    await db.execute(
                        f"UPDATE roles SET status = 'занята', rest_until = NULL WHERE name IN ({placeholders})",
                        names
                    )
                    await db.commit()
        
        return expired
    
    # ============================================================
    # РАБОТА С ПОЛЬЗОВАТЕЛЯМИ
    # ============================================================
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Получить информацию о пользователе"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def get_all_users(self) -> List[Dict]:
        """Получить всех пользователей"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users ORDER BY id") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def add_user(self, user_id: int, username: str, full_name: str, role_index: str = '0'):
        """Добавить пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO users 
                   (id, username, full_name, role_index) 
                   VALUES (?, ?, ?, ?)""",
                (user_id, username, full_name, role_index)
            )
            await db.commit()
    
    async def remove_user(self, user_id: int) -> bool:
        """Удалить пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("DELETE FROM users WHERE id = ?", (user_id,)) as cursor:
                await db.commit()
                return cursor.rowcount > 0
    
    async def get_subscribed_users(self) -> List[Dict]:
        """Получить подписанных на калы пользователей"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE is_subscribed_to_calls = 1"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    # ============================================================
    # ЗАЯВКИ
    # ============================================================
    
    async def create_application(self, user_id: int, role_name: str, position: str = "") -> bool:
        """Создать заявку на роль"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM applications WHERE user_id = ? AND status = 'pending'",
                (user_id,)
            ) as cursor:
                existing = await cursor.fetchone()
                if existing:
                    return False
            
            await db.execute(
                """INSERT INTO applications (user_id, role_name, position, status) 
                   VALUES (?, ?, ?, 'pending')""",
                (user_id, role_name, position)
            )
            await db.commit()
            return True
    
    async def get_pending_applications(self) -> List[Dict]:
        """Получить все активные заявки"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM applications WHERE status = 'pending' ORDER BY created_at"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def approve_application(self, app_id: int) -> bool:
        """Одобрить заявку"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM applications WHERE id = ? AND status = 'pending'",
                    (app_id,)
                ) as cursor:
                    app = await cursor.fetchone()
                    if not app:
                        return False
                
                success = await self.take_role(app['role_name'], app['user_id'], str(app['user_id']))
                if not success:
                    return False
                
                await db.execute(
                    "UPDATE applications SET status = 'approved' WHERE id = ?",
                    (app_id,)
                )
                await db.commit()
                return True
    
    async def reject_application(self, app_id: int) -> bool:
        """Отклонить заявку"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE applications SET status = 'rejected' WHERE id = ?",
                (app_id,)
            )
            await db.commit()
            return True


# Создаём глобальный экземпляр
db = Database()