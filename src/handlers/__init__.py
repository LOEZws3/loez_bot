# Новые файлы из разделения commands.py
from .base_commands import router as base_commands_router
from .role_commands import router as role_commands_router
from .admin_commands import router as admin_commands_router
from .request_commands import router as request_commands_router
from .call_commands import router as call_commands_router
from .rest_commands import router as rest_commands_router
from .settings_commands import router as settings_commands_router

# Существующие файлы
from .apply_handlers import router as apply_router
from .apply_states import router as apply_states_router
from .chat_member import router as chat_member_router
from .forward import router as forward_router
from .keyboards import router as keyboards_router

# Список всех роутеров для подключения в main.py
routers = [
    base_commands_router,
    role_commands_router,
    admin_commands_router,
    request_commands_router,
    call_commands_router,
    rest_commands_router,
    settings_commands_router,
    apply_router,
    apply_states_router,
    chat_member_router,
    forward_router,
    keyboards_router,
]