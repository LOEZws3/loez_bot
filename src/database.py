import aiosqlite
import json
from datetime import datetime
from typing import Optional, Dict, List, Any
import asyncio
from pathlib import Path

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
                    first_name TEXT,
                    last_name TEXT,
                    is_admin BOOLEAN DEFAULT 0,
                    is_subscribed_to_calls BOOLEAN DEFAULT 1,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица заявок
            await db.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role_name TEXT NOT NULL,
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
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (role_name) REFERENCES roles(name)
                )
            """)
            
            # Таблица истории
            await db.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action TEXT,
                    role_name TEXT,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            # Индексы для быстрого поиска
            await db.execute("CREATE INDEX IF NOT EXISTS idx_roles_status ON roles(status)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_roles_owner ON roles(owner_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_applications_user ON applications(user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status)")
            
            await db.commit()
    
    async def migrate_from_json(self, json_path: str = "data/roles_status.json"):
        """Миграция данных из JSON в SQLite"""
        with open(json_path, "r", encoding="utf-8") as f:
            roles_data = json.load(f)
        
        async with aiosqlite.connect(self.db_path) as db:
            for name, data in roles_data.items():
                # Преобразуем строку даты в timestamp если есть рест
                rest_until = None
                if data.get("status") == "рест" and data.get("extra"):
                    try:
                        # Пробуем распарсить дату в формате YYYY-MM-DD
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
    
    # === РАБОТА С РОЛЯМИ ===
    
    async def get_role(self, name: str) -> Optional[Dict]:
        """Получить информацию о роли"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM roles WHERE name = ?", (name,)
            ) as cursor:
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
            async with db.execute(
                "SELECT * FROM roles WHERE status = ?", (status,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_user_role(self, user_id: int) -> Optional[Dict]:
        """Найти роль пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM roles WHERE owner_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def take_role(self, role_name: str, user_id: int, username: str) -> bool:
        """Выдать роль пользователю"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                # Проверяем, свободна ли роль
                role = await self.get_role(role_name)
                if not role or role['status'] != 'свободна':
                    return False
                
                # Проверяем, нет ли у пользователя другой роли
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
                
                # Рассчитываем дату окончания реста
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
                
                # Снимаем ресты
                if expired:
                    placeholders = ','.join(['?'] * len(expired))
                    names = [row['name'] for row in expired]
                    await db.execute(
                        f"UPDATE roles SET status = 'занята', rest_until = NULL WHERE name IN ({placeholders})",
                        names
                    )
                    await db.commit()
        
        return expired
    
    # === РАБОТА С ПОЛЬЗОВАТЕЛЯМИ ===
    
    async def add_user(self, user_id: int, username: str, first_name: str = "", last_name: str = ""):
        """Добавить пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR IGNORE INTO users (id, username, first_name, last_name) 
                   VALUES (?, ?, ?, ?)""",
                (user_id, username, first_name, last_name)
            )
            await db.commit()
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Получить информацию о пользователе"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def get_all_users(self) -> List[Dict]:
        """Получить всех пользователей"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users ORDER BY id") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_subscribed_users(self) -> List[Dict]:
        """Получить подписанных на калы пользователей"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE is_subscribed_to_calls = 1"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def toggle_call_subscription(self, user_id: int) -> bool:
        """Переключить подписку на калы"""
        async with aiosqlite.connect(self.db_path) as db:
            user = await self.get_user(user_id)
            if not user:
                return False
            
            new_status = 0 if user['is_subscribed_to_calls'] else 1
            await db.execute(
                "UPDATE users SET is_subscribed_to_calls = ? WHERE id = ?",
                (new_status, user_id)
            )
            await db.commit()
            return bool(new_status)
    
    # === РАБОТА С ЗАЯВКАМИ ===
    
    async def create_application(self, user_id: int, role_name: str):
        """Создать заявку на роль"""
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем, нет ли уже активной заявки
            async with db.execute(
                "SELECT * FROM applications WHERE user_id = ? AND status = 'pending'",
                (user_id,)
            ) as cursor:
                existing = await cursor.fetchone()
                if existing:
                    return False
            
            await db.execute(
                "INSERT INTO applications (user_id, role_name, status) VALUES (?, ?, 'pending')",
                (user_id, role_name)
            )
            await db.commit()
            return True
    
    async def get_pending_applications(self) -> List[Dict]:
        """Получить все заявки в ожидании"""
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
                # Получаем заявку
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM applications WHERE id = ? AND status = 'pending'",
                    (app_id,)
                ) as cursor:
                    app = await cursor.fetchone()
                    if not app:
                        return False
                
                # Выдаём роль
                success = await self.take_role(app['role_name'], app['user_id'], str(app['user_id']))
                if not success:
                    return False
                
                # Обновляем статус заявки
                await db.execute(
                    "UPDATE applications SET status = 'approved' WHERE id = ?",
                    (app_id,)
                )
                await db.commit()
                return True
    
    async def reject_application(self, app_id: int):
        """Отклонить заявку"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE applications SET status = 'rejected' WHERE id = ?",
                (app_id,)
            )
            await db.commit()
    
    # === ИСТОРИЯ ===
    
    async def add_history(self, user_id: int, action: str, role_name: str = "", details: str = ""):
        """Добавить запись в историю"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO history (user_id, action, role_name, details) VALUES (?, ?, ?, ?)",
                (user_id, action, role_name, details)
            )
            await db.commit()
    
    async def get_user_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Получить историю пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM history WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
                (user_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

# Создаём глобальный экземпляр
db = Database()