from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.bot import texts
from opdbot.bot.keyboards.main_menu import candidate_main_menu, cancel_reply_keyboard
from opdbot.bot.states.candidate import FeedbackStates
from opdbot.db.models import ApplicationStatus, ChatMessage, MessageFromRole
from opdbot.db.repo.applications import get_active_application, get_user_applications
from opdbot.db.repo.users import get_all_staff, get_user_by_tg_id
from opdbot.services import notifications

router = Router(name="feedback")


@router.message(F.text == "💬 Связаться с HR")
async def start_feedback(message: Message, state: FSMContext, session: AsyncSession) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return

    user = await get_user_by_tg_id(session, tg_user.id)
    if not user:
        await message.answer(texts.ERROR_NO_ACTIVE_APPLICATION)
        return

    active = await get_active_application(session, user.id)
    if active is None:
        apps = await get_user_applications(session, user.id)
        active = next(
            (a for a in apps if a.status == ApplicationStatus.approved), None
        )
    if active is None:
        await message.answer(texts.ERROR_NO_ACTIVE_APPLICATION)
        return

    await state.set_state(FeedbackStates.waiting_message)
    await state.update_data(application_id=active.id)
    await message.answer(texts.FEEDBACK_ASK, reply_markup=cancel_reply_keyboard())


@router.message(FeedbackStates.waiting_message)
async def handle_feedback_message(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return

    data = await state.get_data()
    application_id: int = data["application_id"]
    text = message.text or ""

    session.add(
        ChatMessage(
            application_id=application_id,
            from_role=MessageFromRole.candidate,
            text=text,
        )
    )
    await session.flush()

    user = await get_user_by_tg_id(session, tg_user.id)
    staff = await get_all_staff(session)
    full_name = user.full_name if user else "—"
    for hr_user in staff:
        await notifications.notify_user(
            bot=message.bot,  # type: ignore[arg-type]
            tg_id=hr_user.tg_id,
            text=texts.NOTIFY_CANDIDATE_MESSAGE.format(
                full_name=full_name,
                app_id=application_id,
                text=text,
            ),
        )

    await state.clear()
    await message.answer(texts.FEEDBACK_SENT, reply_markup=candidate_main_menu(True))
