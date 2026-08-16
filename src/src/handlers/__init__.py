from .commands import router as commands_router
from .apply_handlers import router as apply_router
from .apply_states import router as apply_states_router
from .chat_member import router as chat_member_router
from .forward import router as forward_router
from .keyboards import router as keyboards_router

# Список всех роутеров для подключения в main.py
routers = [
    commands_router,
    apply_router,
    apply_states_router,
    chat_member_router,
    forward_router,
    keyboards_router,
]