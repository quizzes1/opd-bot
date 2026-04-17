from aiogram.fsm.state import State, StatesGroup


class HrRejectDocStates(StatesGroup):
    waiting_reason = State()


class HrMessageStates(StatesGroup):
    waiting_text = State()


class HrSlotStates(StatesGroup):
    waiting_kind = State()
    waiting_date = State()
    waiting_duration = State()
    waiting_capacity = State()


class HrCharacteristicStates(StatesGroup):
    waiting_supervisor = State()
    waiting_topic = State()
    waiting_period_from = State()
    waiting_period_to = State()


class HrSearchStates(StatesGroup):
    waiting_query = State()


class HrCatalogStates(StatesGroup):
    waiting_doc_title = State()
    waiting_doc_code = State()
    waiting_doc_mime = State()
    waiting_doc_size = State()
