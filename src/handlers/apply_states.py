from aiogram.fsm.state import State, StatesGroup
from aiogram import Router

router = Router()
class ApplyStates(StatesGroup):
    """Состояния для процесса подачи заявки"""
    waiting_for_season = State()      # Ожидание выбора сезона
    waiting_for_role = State()        # Ожидание выбора роли
    waiting_for_position = State()    # Ожидание выбора должности
    waiting_for_confirmation = State() # Ожидание подтверждения