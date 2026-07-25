from .commands import router
from .forward import forward_to_admin_group, reply_from_admin_group
from .chat_member import router as chat_member_router
from .apply_handlers import router as apply_router  # <-- Добавляем

# Экспортируем все роутеры
__all__ = ['router', 'chat_member_router', 'apply_router']