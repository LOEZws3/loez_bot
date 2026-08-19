from database import db
import asyncio

async def on_startup(dp):
    # Инициализация БД
    await db.init()
    
    # Миграция данных из JSON (только при первом запуске!)
    # await db.migrate_from_json()
    
    # Запуск планировщика для проверки рестов
    asyncio.create_task(check_rests_loop())
    
    print("✅ Бот запущен!")

async def check_rests_loop():
    """Планировщик проверки рестов каждую минуту"""
    while True:
        try:
            expired = await db.check_expired_rests()
            for role in expired:
                # Уведомляем пользователя
                if role['owner_id']:
                    await bot.send_message(
                        role['owner_id'],
                        f"🔔 Ваш рест для роли **{role['name']}** закончился! Теперь вы снова активны."
                    )
        except Exception as e:
            print(f"Ошибка в планировщике: {e}")
        
        await asyncio.sleep(60)  # Проверяем каждую минуту