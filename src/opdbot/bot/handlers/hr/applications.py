from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.bot import texts
from opdbot.bot.keyboards.hr import application_card_keyboard, applications_filter_keyboard
from opdbot.db.models import ApplicationStatus, UserRole
from opdbot.db.repo.applications import get_application, list_applications
from opdbot.db.repo.users import get_user_by_tg_id

router = Router(name="hr_applications")

STATUS_MAP = {
    "all": None,
    "docs_submitted": ApplicationStatus.docs_submitted,
    "interview_scheduled": ApplicationStatus.interview_scheduled,
    "approved": ApplicationStatus.approved,
    "rejected": ApplicationStatus.rejected,
}


@router.callback_query(F.data.startswith("hr:filter:"))
async def hr_filter_applications(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        await callback.answer("Нет доступа.")
        return

    filter_key = callback.data.split(":")[2]  # type: ignore[union-attr]
    status = STATUS_MAP.get(filter_key)
    apps = await list_applications(session, status=status, limit=20)

    if not apps:
        if callback.message:
            await callback.message.edit_text(texts.HR_NO_APPLICATIONS)
        await callback.answer()
        return

    lines = [f"{texts.HR_APPLICATIONS_LIST.format(count=len(apps))}"]
    for app in apps:
        status_label = texts.STATUS_LABELS.get(app.status.value, app.status.value)
        goal_label = app.goal.title if app.goal else "—"
        user = app.user
        name = user.full_name or "—"
        lines.append(f"#{app.id} | {name} | {goal_label} | {status_label}")

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for app in apps[:10]:
        builder.button(text=f"#{app.id} {app.user.full_name or '—'}", callback_data=f"hr:app:{app.id}")
    builder.button(text="🔄 Обновить", callback_data=f"hr:filter:{filter_key}")
    builder.adjust(1)

    if callback.message:
        await callback.message.edit_text(
            "\n".join(lines),
            reply_markup=builder.as_markup(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("hr:app:"))
async def hr_application_card(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        await callback.answer("Нет доступа.")
        return

    app_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    app = await get_application(session, app_id)
    if not app:
        await callback.answer("Заявка не найдена.")
        return

    user = app.user
    status_label = texts.STATUS_LABELS.get(app.status.value, app.status.value)
    goal_label = app.goal.title if app.goal else "—"
    interview_line = ""
    training_line = ""
    if app.interview_at:
        interview_line = f"Собеседование: {app.interview_at.strftime('%d.%m.%Y %H:%M')}\n"
    if app.training_at:
        training_line = f"Обучение: {app.training_at.strftime('%d.%m.%Y %H:%M')}\n"

    text = texts.HR_APPLICATION_CARD.format(
        app_id=app.id,
        full_name=user.full_name or "—",
        username=user.tg_username or "нет",
        phone=user.phone or "—",
        goal=goal_label,
        status=status_label,
        created_at=app.created_at.strftime("%d.%m.%Y"),
        interview_line=interview_line,
        training_line=training_line,
        hr_comment=app.hr_comment or "—",
    )

    if callback.message:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=application_card_keyboard(app),
        )
    await callback.answer()


@router.callback_query(F.data == "hr:applications")
async def hr_back_to_applications(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.edit_text(
            "Фильтр заявок:",
            reply_markup=applications_filter_keyboard(),
        )
    await callback.answer()


@router.message(F.text == "🔍 Поиск")
async def hr_search_start(message: Message, state: FSMContext, role: UserRole) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return
    from opdbot.bot.states.hr import HrSearchStates
    await state.set_state(HrSearchStates.waiting_query)
    await message.answer("Введите ФИО, @username или телефон кандидата:")


from opdbot.bot.states.hr import HrSearchStates


@router.message(HrSearchStates.waiting_query)
async def hr_search_execute(message: Message, state: FSMContext, session: AsyncSession) -> None:
    from sqlalchemy import or_, select
    from opdbot.db.models import User, Application
    from sqlalchemy.orm import selectinload

    query_text = (message.text or "").strip()
    result = await session.execute(
        select(User).where(
            or_(
                User.full_name.ilike(f"%{query_text}%"),
                User.tg_username.ilike(f"%{query_text}%"),
                User.phone.ilike(f"%{query_text}%"),
            )
        )
    )
    users = list(result.scalars().all())

    if not users:
        await message.answer("Кандидаты не найдены.")
        await state.clear()
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for user in users[:10]:
        apps = await list_applications(session)
        user_apps = [a for a in apps if a.user_id == user.id]
        for app in user_apps[:3]:
            status_label = texts.STATUS_LABELS.get(app.status.value, app.status.value)
            builder.button(
                text=f"#{app.id} {user.full_name or '—'} | {status_label}",
                callback_data=f"hr:app:{app.id}",
            )
    builder.adjust(1)

    await message.answer(f"Найдено кандидатов: {len(users)}", reply_markup=builder.as_markup())
    await state.clear()
