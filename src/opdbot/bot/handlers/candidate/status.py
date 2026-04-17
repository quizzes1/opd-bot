from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.bot import texts
from opdbot.bot.handlers.candidate.docs import start_doc_upload
from opdbot.bot.handlers.candidate.scheduling import (
    start_interview_scheduling,
    start_training_scheduling,
)
from opdbot.db.models import ApplicationStatus
from opdbot.db.repo.applications import get_user_applications
from opdbot.db.repo.users import get_user_by_tg_id

router = Router(name="status")


@router.message(F.text == "📋 Мои заявки")
async def my_applications(message: Message, session: AsyncSession) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return

    user = await get_user_by_tg_id(session, tg_user.id)
    if not user:
        await message.answer(texts.NO_APPLICATIONS)
        return

    apps = await get_user_applications(session, user.id)
    if not apps:
        await message.answer(texts.NO_APPLICATIONS)
        return

    lines = []
    for app in apps:
        status_label = texts.STATUS_LABELS.get(app.status.value, app.status.value)
        goal_label = app.goal.title if app.goal else "—"
        interview_line = ""
        training_line = ""
        if app.interview_at:
            interview_line = f"Собеседование: {app.interview_at.strftime('%d.%m.%Y %H:%M')}\n"
        if app.training_at:
            training_line = f"Обучение: {app.training_at.strftime('%d.%m.%Y %H:%M')}\n"

        lines.append(
            texts.APPLICATION_CARD.format(
                app_id=app.id,
                goal=goal_label,
                status=status_label,
                created_at=app.created_at.strftime("%d.%m.%Y"),
                interview_line=interview_line,
                training_line=training_line,
            )
        )

    await message.answer("\n\n".join(lines), parse_mode="HTML")


@router.message(F.text == "📄 Подать заявку")
async def new_application(message: Message, state: FSMContext, session: AsyncSession) -> None:
    from sqlalchemy import select
    from opdbot.db.models import Goal
    from opdbot.bot.states.candidate import OnboardingStates
    from opdbot.bot.keyboards.goals import goals_keyboard
    from opdbot.db.repo.users import get_user_by_tg_id

    tg_user = message.from_user
    if tg_user is None:
        return

    user = await get_user_by_tg_id(session, tg_user.id)
    if not user or not user.full_name or not user.phone:
        await state.set_state(OnboardingStates.waiting_full_name)
        await message.answer(texts.WELCOME)
        return

    result = await session.execute(select(Goal).where(Goal.is_active.is_(True)))
    goals = list(result.scalars().all())
    await state.set_state(OnboardingStates.waiting_goal)
    await message.answer(texts.ASK_GOAL, reply_markup=goals_keyboard(goals))


@router.message(F.text == "📅 Записаться на собеседование")
async def schedule_interview(message: Message, state: FSMContext, session: AsyncSession) -> None:
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

    await start_interview_scheduling(message, state, session, active[0].id)


@router.message(F.text == "🎓 Записаться на обучение")
async def schedule_training(message: Message, state: FSMContext, session: AsyncSession) -> None:
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

    await start_training_scheduling(message, state, session, active[0].id)


@router.message(F.text == "🔄 Изменить документы")
async def change_documents(message: Message, state: FSMContext, session: AsyncSession) -> None:
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

    await start_doc_upload(message, state, session, active[0].id)
