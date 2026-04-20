from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.bot import texts
from opdbot.bot.handlers.candidate.docs import start_doc_upload
from opdbot.bot.handlers.candidate.scheduling import (
    start_interview_scheduling,
    start_training_scheduling,
)
from opdbot.bot.keyboards.goals import goals_keyboard
from opdbot.bot.keyboards.main_menu import candidate_main_menu
from opdbot.bot.states.candidate import EditAppStates, OnboardingStates
from opdbot.utils.dates import fmt_date, fmt_datetime
from opdbot.utils.validators import validate_full_name, validate_phone
from opdbot.db.models import ApplicationStatus, AuditLog, Goal, SlotKind
from opdbot.db.repo.applications import (
    get_active_application,
    get_user_applications,
    update_application_status,
)
from opdbot.db.repo.slots import free_slot_by_start
from opdbot.db.repo.users import get_user_by_tg_id

router = Router(name="status")


def _app_row_keyboard(app_id: int, status: ApplicationStatus) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    if status not in (
        ApplicationStatus.approved,
        ApplicationStatus.rejected,
        ApplicationStatus.cancelled,
    ):
        builder.button(text="✏️ Изменить данные", callback_data=f"candidate:edit:{app_id}")
        builder.button(text="❌ Отменить заявку", callback_data=f"candidate:cancel:{app_id}")
    builder.adjust(1)
    return builder


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

    for app in apps:
        status_label = texts.STATUS_LABELS.get(app.status.value, app.status.value)
        goal_label = app.goal.title if app.goal else "—"
        interview_line = ""
        training_line = ""
        if app.interview_at:
            interview_line = f"Собеседование: {fmt_datetime(app.interview_at)}\n"
        if app.training_at:
            training_line = f"Обучение: {fmt_datetime(app.training_at)}\n"

        text = texts.APPLICATION_CARD.format(
            app_id=app.id,
            goal=goal_label,
            status=status_label,
            created_at=fmt_date(app.created_at),
            interview_line=interview_line,
            training_line=training_line,
        )
        kb = _app_row_keyboard(app.id, app.status)
        markup = kb.as_markup() if kb.export() else None
        await message.answer(text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data.startswith("candidate:cancel:"))
async def cancel_application(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    app_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    tg_user = callback.from_user
    if tg_user is None:
        return

    user = await get_user_by_tg_id(session, tg_user.id)
    if not user:
        await callback.answer("Пользователь не найден.")
        return

    apps = await get_user_applications(session, user.id)
    app = next((a for a in apps if a.id == app_id), None)
    if not app:
        await callback.answer("Заявка не найдена.")
        return
    if app.status in (
        ApplicationStatus.approved,
        ApplicationStatus.rejected,
        ApplicationStatus.cancelled,
    ):
        await callback.answer("Эту заявку нельзя отменить.")
        return

    if app.interview_at:
        await free_slot_by_start(session, SlotKind.interview, app.interview_at)
        app.interview_at = None
    if app.training_at:
        await free_slot_by_start(session, SlotKind.training, app.training_at)
        app.training_at = None
    if app.medical_at:
        await free_slot_by_start(session, SlotKind.medical, app.medical_at)
        app.medical_at = None
    await update_application_status(session, app, ApplicationStatus.cancelled)
    session.add(
        AuditLog(
            application_id=app_id,
            actor_tg_id=tg_user.id,
            event="application_cancelled_by_candidate",
        )
    )
    await callback.answer("Заявка отменена.")
    if callback.message:
        await callback.message.edit_text(
            texts.APPLICATION_CANCELLED.format(app_id=app_id),
        )
        remaining_active = await get_active_application(session, user.id)
        await callback.message.answer(
            texts.MAIN_MENU,
            reply_markup=candidate_main_menu(remaining_active is not None),
        )


@router.message(F.text == "📄 Подать заявку")
async def new_application(message: Message, state: FSMContext, session: AsyncSession) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return

    user = await get_user_by_tg_id(session, tg_user.id)
    if not user or not user.full_name or not user.phone:
        await state.set_state(OnboardingStates.waiting_full_name)
        await message.answer(texts.WELCOME)
        return

    existing = await get_active_application(session, user.id)
    if existing is not None:
        await message.answer(
            texts.ACTIVE_APPLICATION_EXISTS.format(app_id=existing.id),
            reply_markup=candidate_main_menu(True),
        )
        return

    result = await session.execute(select(Goal).where(Goal.is_active.is_(True)))
    goals = list(result.scalars().all())
    await state.set_state(OnboardingStates.waiting_goal)
    await message.answer(texts.ASK_GOAL, reply_markup=goals_keyboard(goals))


async def _active_app(session: AsyncSession, message: Message):
    tg_user = message.from_user
    if tg_user is None:
        return None
    user = await get_user_by_tg_id(session, tg_user.id)
    if not user:
        return None
    return await get_active_application(session, user.id)


@router.message(F.text == "📅 Записаться на собеседование")
async def schedule_interview(message: Message, state: FSMContext, session: AsyncSession) -> None:
    app = await _active_app(session, message)
    if app is None:
        await message.answer(texts.ERROR_NO_ACTIVE_APPLICATION)
        return
    await start_interview_scheduling(message, state, session, app.id)


@router.message(F.text == "🎓 Записаться на обучение")
async def schedule_training(message: Message, state: FSMContext, session: AsyncSession) -> None:
    app = await _active_app(session, message)
    if app is None:
        await message.answer(texts.ERROR_NO_ACTIVE_APPLICATION)
        return
    await start_training_scheduling(message, state, session, app.id)


@router.message(F.text == "🔄 Изменить документы")
async def change_documents(message: Message, state: FSMContext, session: AsyncSession) -> None:
    app = await _active_app(session, message)
    if app is None:
        await message.answer(texts.ERROR_NO_ACTIVE_APPLICATION)
        return
    from opdbot.bot.handlers.candidate.docs import offer_doc_to_replace

    await offer_doc_to_replace(message, state, session, app.id)


_EDITABLE_STATUSES = (
    ApplicationStatus.draft,
    ApplicationStatus.docs_in_progress,
    ApplicationStatus.docs_submitted,
)


@router.callback_query(F.data.startswith("candidate:edit:"))
async def edit_application(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    app_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    tg_user = callback.from_user
    if tg_user is None:
        return
    user = await get_user_by_tg_id(session, tg_user.id)
    if not user:
        await callback.answer("Пользователь не найден.")
        return
    apps = await get_user_applications(session, user.id)
    app = next((a for a in apps if a.id == app_id), None)
    if not app:
        await callback.answer("Заявка не найдена.")
        return
    if app.status not in _EDITABLE_STATUSES:
        await callback.answer(texts.EDIT_APP_NOT_EDITABLE, show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.button(text=texts.EDIT_APP_FIELD_NAME, callback_data=f"candidate:edit_f:{app_id}:name")
    builder.button(text=texts.EDIT_APP_FIELD_PHONE, callback_data=f"candidate:edit_f:{app_id}:phone")
    builder.button(text=texts.EDIT_APP_FIELD_GOAL, callback_data=f"candidate:edit_f:{app_id}:goal")
    builder.adjust(1)

    if callback.message:
        await callback.message.answer(
            texts.EDIT_APP_MENU.format(app_id=app_id),
            reply_markup=builder.as_markup(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("candidate:edit_f:"))
async def edit_field_start(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    parts = callback.data.split(":")  # type: ignore[union-attr]
    app_id = int(parts[2])
    field = parts[3]

    tg_user = callback.from_user
    if tg_user is None:
        return
    user = await get_user_by_tg_id(session, tg_user.id)
    if not user:
        await callback.answer("Пользователь не найден.")
        return
    apps = await get_user_applications(session, user.id)
    app = next((a for a in apps if a.id == app_id), None)

    await state.update_data(app_id=app_id)
    if field == "name":
        await state.set_state(EditAppStates.waiting_name)
        current = user.full_name or "—"
        prompt = f"Текущее ФИО: {current}\nВведите новое ФИО:"
    elif field == "phone":
        await state.set_state(EditAppStates.waiting_phone)
        current = user.phone or "—"
        prompt = f"Текущий телефон: {current}\nВведите новый телефон (+7XXXXXXXXXX):"
    elif field == "goal":
        result = await session.execute(select(Goal).where(Goal.is_active.is_(True)))
        goals = list(result.scalars().all())
        await state.set_state(EditAppStates.waiting_goal)
        current = app.goal.title if app and app.goal else "—"
        if callback.message:
            await callback.message.answer(
                f"Текущая цель: {current}\n{texts.ASK_GOAL}",
                reply_markup=goals_keyboard(goals),
            )
        await callback.answer()
        return
    else:
        await callback.answer()
        return

    if callback.message:
        await callback.message.answer(prompt)
    await callback.answer()


@router.message(EditAppStates.waiting_name)
async def edit_name_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    name = validate_full_name(message.text or "")
    if name is None:
        await message.answer(texts.BAD_FULL_NAME)
        return
    tg_user = message.from_user
    if tg_user is None:
        return
    user = await get_user_by_tg_id(session, tg_user.id)
    if user:
        user.full_name = name
        await session.flush()
    await message.answer(texts.EDIT_APP_UPDATED, reply_markup=candidate_main_menu(True))
    await state.clear()


@router.message(EditAppStates.waiting_phone)
async def edit_phone_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    phone = validate_phone(message.text or "")
    if phone is None:
        await message.answer(texts.BAD_PHONE)
        return
    tg_user = message.from_user
    if tg_user is None:
        return
    user = await get_user_by_tg_id(session, tg_user.id)
    if user:
        user.phone = phone
        await session.flush()
    await message.answer(texts.EDIT_APP_UPDATED, reply_markup=candidate_main_menu(True))
    await state.clear()


@router.callback_query(EditAppStates.waiting_goal, F.data.startswith("goal:"))
async def edit_goal_save(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    goal_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    data = await state.get_data()
    app_id: int = data["app_id"]

    tg_user = callback.from_user
    if tg_user is None:
        return
    user = await get_user_by_tg_id(session, tg_user.id)
    if not user:
        await callback.answer("Пользователь не найден.")
        return
    apps = await get_user_applications(session, user.id)
    app = next((a for a in apps if a.id == app_id), None)
    if not app:
        await callback.answer("Заявка не найдена.")
        return
    app.goal_id = goal_id
    await session.flush()

    await callback.answer()
    await state.clear()
    if callback.message:
        await callback.message.answer(texts.EDIT_APP_UPDATED)
        from opdbot.bot.handlers.candidate.docs import start_doc_upload

        await start_doc_upload(callback.message, state, session, app.id)
