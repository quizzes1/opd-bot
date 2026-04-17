from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.bot import texts
from opdbot.bot.keyboards.main_menu import candidate_main_menu
from opdbot.bot.states.candidate import FeedbackStates
from opdbot.db.models import ApplicationStatus, Message as DbMessage, MessageFromRole
from opdbot.db.repo.applications import get_user_applications
from opdbot.db.repo.users import get_all_hr, get_user_by_tg_id
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

    apps = await get_user_applications(session, user.id)
    active = [
        a for a in apps
        if a.status not in (ApplicationStatus.approved, ApplicationStatus.rejected, ApplicationStatus.cancelled)
    ]
    if not active:
        await message.answer(texts.ERROR_NO_ACTIVE_APPLICATION)
        return

    await state.set_state(FeedbackStates.waiting_message)
    await state.update_data(application_id=active[0].id)
    await message.answer(texts.FEEDBACK_ASK)


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

    msg = DbMessage(
        application_id=application_id,
        from_role=MessageFromRole.candidate,
        text=text,
    )
    session.add(msg)
    await session.flush()

    user = await get_user_by_tg_id(session, tg_user.id)
    hr_list = await get_all_hr(session)
    for hr_user in hr_list:
        await notifications.notify_user(
            bot=message.bot,  # type: ignore[arg-type]
            tg_id=hr_user.tg_id,
            text=texts.NOTIFY_CANDIDATE_MESSAGE.format(
                full_name=user.full_name if user else "—",
                app_id=application_id,
                text=text,
            ),
        )

    await state.clear()
    await message.answer(texts.FEEDBACK_SENT, reply_markup=candidate_main_menu())
