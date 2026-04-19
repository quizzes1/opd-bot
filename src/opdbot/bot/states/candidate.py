from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    waiting_full_name = State()
    waiting_phone = State()
    waiting_goal = State()


class DocUploadStates(StatesGroup):
    uploading = State()


class DocRequestUploadStates(StatesGroup):
    waiting_file = State()


class InterviewSchedulingStates(StatesGroup):
    choosing_slot = State()


class TrainingSchedulingStates(StatesGroup):
    choosing_slot = State()


class FeedbackStates(StatesGroup):
    waiting_message = State()


class EditAppStates(StatesGroup):
    waiting_name = State()
    waiting_phone = State()
    waiting_goal = State()
