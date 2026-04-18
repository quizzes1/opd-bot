from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.bot import texts
from opdbot.bot.keyboards.hr import application_card_keyboard, applications_filter_keyboard
from opdbot.bot.keyboards.main_menu import cancel_reply_keyboard, hr_main_menu
from opdbot.bot.states.hr import HrSearchStates
from opdbot.db.models import ACTIVE_STATUSES, ApplicationStatus, UserRole
from opdbot.db.repo.applications import (
    get_application,
    list_applications,
    search_applications,
)

router = Router(name="hr_applications")

PAGE_SIZE = 10

STATUS_MAP: dict[str, list[ApplicationStatus] | None] = {
    "all": None,
    "active": list(ACTIVE_STATUSES),
    "docs_submitted": [ApplicationStatus.docs_submitted],
    "interview_scheduled": [ApplicationStatus.interview_scheduled],
    "approved": [ApplicationStatus.approved],
    "rejected": [ApplicationStatus.rejected],
}


def _pagination_keyboard(
    filter_key: str, page: int, total: int, apps
) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for app in apps:
        builder.button(
            text=f"#{app.id} {app.user.full_name or '—'}",
            callback_data=f"hr:app:{app.id}",
        )
    builder.adjust(1)

    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    nav = InlineKeyboardBuilder()
    if page > 0:
        nav.button(text="◀️", callback_data=f"hr:filter:{filter_key}:{page - 1}")
    nav.button(text=f"{page + 1}/{max(pages, 1)}", callback_data="noop")
    if page + 1 < pages:
        nav.button(text="▶️", callback_data=f"hr:filter:{filter_key}:{page + 1}")
    builder.attach(nav)
    return builder


@router.callback_query(F.data.startswith("hr:filter:"))
async def hr_filter_applications(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        await callback.answer(texts.HR_NO_ACCESS)
        return

    parts = callback.data.split(":")  # type: ignore[union-attr]
    filter_key = parts[2]
    page = int(parts[3]) if len(parts) > 3 else 0

    statuses = STATUS_MAP.get(filter_key)
    apps, total = await list_applications(
        session,
        statuses=statuses,
        limit=PAGE_SIZE,
        offset=page * PAGE_SIZE,
    )

    if not apps:
        if callback.message:
            await callback.message.edit_text(texts.HR_NO_APPLICATIONS)
        await callback.answer()
        return

    lines = [texts.HR_APPLICATIONS_LIST.format(count=total)]
    for app in apps:
        status_label = texts.STATUS_LABELS.get(app.status.value, app.status.value)
        goal_label = app.goal.title if app.goal else "—"
        name = app.user.full_name or "—"
        lines.append(f"#{app.id} | {name} | {goal_label} | {status_label}")

    builder = _pagination_keyboard(filter_key, page, total, apps)

    if callback.message:
        await callback.message.edit_text(
            "\n".join(lines),
            reply_markup=builder.as_markup(),
        )
    await callback.answer()


@router.callback_query(F.data == "noop")
async def hr_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("hr:app:"))
async def hr_application_card(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        await callback.answer(texts.HR_NO_ACCESS)
        return

    app_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    app = await get_application(session, app_id)
    if not app:
        await callback.answer(texts.HR_APP_NOT_FOUND)
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
        username=user.tg_username or texts.USERNAME_NONE,
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
            texts.HR_FILTER_PROMPT,
            reply_markup=applications_filter_keyboard(),
        )
    await callback.answer()


@router.message(F.text == "🔍 Поиск")
async def hr_search_start(message: Message, state: FSMContext, role: UserRole) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return
    await state.set_state(HrSearchStates.waiting_query)
    await message.answer(texts.HR_SEARCH_PROMPT, reply_markup=cancel_reply_keyboard())


@router.message(HrSearchStates.waiting_query)
async def hr_search_execute(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    query_text = (message.text or "").strip()
    if not query_text:
        await message.answer(texts.HR_EMPTY_QUERY)
        await state.clear()
        return

    apps = await search_applications(session, query_text, limit=20)
    if not apps:
        await message.answer(texts.HR_NO_APPLICATIONS_FOUND)
        await state.clear()
        return

    builder = InlineKeyboardBuilder()
    for app in apps:
        status_label = texts.STATUS_LABELS.get(app.status.value, app.status.value)
        builder.button(
            text=f"#{app.id} {app.user.full_name or '—'} | {status_label}",
            callback_data=f"hr:app:{app.id}",
        )
    builder.adjust(1)

    await message.answer(
        texts.HR_APPLICATIONS_FOUND.format(count=len(apps)),
        reply_markup=builder.as_markup(),
    )
    await message.answer(texts.HR_WELCOME, reply_markup=hr_main_menu())
    await state.clear()
