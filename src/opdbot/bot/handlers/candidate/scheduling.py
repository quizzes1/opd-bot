from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.bot import texts
from opdbot.bot.keyboards.calendar import slots_keyboard
from opdbot.bot.keyboards.main_menu import candidate_main_menu
from opdbot.bot.states.candidate import InterviewSchedulingStates, TrainingSchedulingStates
from opdbot.db.models import SlotKind
from opdbot.db.repo.applications import get_application, set_interview_slot, set_training_slot
from opdbot.db.repo.slots import book_slot, get_available_slots
from opdbot.db.repo.users import get_user_by_tg_id

router = Router(name="scheduling")


async def start_interview_scheduling(
    message: Message, state: FSMContext, session: AsyncSession, application_id: int
) -> None:
    slots = await get_available_slots(session, SlotKind.interview, from_dt=datetime.now())
    if not slots:
        await message.answer(texts.NO_SLOTS_AVAILABLE)
        return
    await state.set_state(InterviewSchedulingStates.choosing_slot)
    await state.update_data(application_id=application_id)
    await message.answer(
        texts.CHOOSE_INTERVIEW_DATE,
        reply_markup=slots_keyboard(slots, "interview"),
    )


async def start_training_scheduling(
    message: Message, state: FSMContext, session: AsyncSession, application_id: int
) -> None:
    slots = await get_available_slots(session, SlotKind.training, from_dt=datetime.now())
    if not slots:
        await message.answer(texts.NO_SLOTS_AVAILABLE)
        return
    await state.set_state(TrainingSchedulingStates.choosing_slot)
    await state.update_data(application_id=application_id)
    await message.answer(
        texts.CHOOSE_TRAINING_DATE,
        reply_markup=slots_keyboard(slots, "training"),
    )


@router.callback_query(
    InterviewSchedulingStates.choosing_slot, F.data.startswith("slot:interview:")
)
async def handle_interview_slot(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    if callback.message is None or callback.from_user is None:
        return

    slot_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    data = await state.get_data()
    application_id: int = data["application_id"]

    slot = await book_slot(session, slot_id)
    if not slot:
        await callback.answer("Слот уже занят, выберите другой.")
        return

    app = await get_application(session, application_id)
    if app:
        await set_interview_slot(session, app, slot.starts_at)

    await state.clear()
    dt_str = slot.starts_at.strftime("%d.%m.%Y %H:%M")
    await callback.message.edit_text(  # type: ignore[union-attr]
        texts.SLOT_BOOKED.format(kind="собеседование", dt=dt_str),
        parse_mode="HTML",
    )
    await callback.message.answer(texts.MAIN_MENU, reply_markup=candidate_main_menu())  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(
    TrainingSchedulingStates.choosing_slot, F.data.startswith("slot:training:")
)
async def handle_training_slot(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    if callback.message is None or callback.from_user is None:
        return

    slot_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    data = await state.get_data()
    application_id: int = data["application_id"]

    slot = await book_slot(session, slot_id)
    if not slot:
        await callback.answer("Слот уже занят, выберите другой.")
        return

    app = await get_application(session, application_id)
    if app:
        await set_training_slot(session, app, slot.starts_at)

    await state.clear()
    dt_str = slot.starts_at.strftime("%d.%m.%Y %H:%M")
    await callback.message.edit_text(  # type: ignore[union-attr]
        texts.SLOT_BOOKED.format(kind="обучение", dt=dt_str),
        parse_mode="HTML",
    )
    await callback.message.answer(texts.MAIN_MENU, reply_markup=candidate_main_menu())  # type: ignore[union-attr]
    await callback.answer()
