from aiogram.fsm.state import State, StatesGroup


class PickFlow(StatesGroup):
    rank = State()
    map = State()
    role = State()
    ready = State()
    agent = State()
    lineup = State()
    lineup_side = State()
    lineup_site = State()


class AIChat(StatesGroup):
    chatting = State()
