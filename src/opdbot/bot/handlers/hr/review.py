from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.bot import texts
from opdbot.utils.dates import fmt_datetime
from opdbot.bot.keyboards.hr import document_actions_keyboard, request_doc_keyboard
from opdbot.bot.keyboards.main_menu import cancel_reply_keyboard, hr_main_menu
from opdbot.bot.states.hr import HrMessageStates, HrRejectDocStates, HrRequestDocStates
from opdbot.db.models import (
    ApplicationStatus,
    AuditLog,
    ChatMessage,
    Document,
    DocumentRequirement,
    DocumentStatus,
    MessageFromRole,
    SlotKind,
    UserRole,
)
from opdbot.db.repo.applications import (
    get_application,
    set_interview_slot,
    update_application_status,
)
from opdbot.db.repo.slots import book_slot, free_slot_by_start, get_available_slots
from opdbot.db.repo.documents import (
    get_documents_for_application,
    get_requirements_for_goal,
    update_document_status,
)
from opdbot.services import notifications
from opdbot.services.storage import get_absolute_path

router = Router(name="hr_review")


async def _guard_cancelled(callback: CallbackQuery, app) -> bool:
    if app.status == ApplicationStatus.cancelled:
        await callback.answer(texts.HR_APP_CANCELLED_BY_CANDIDATE, show_alert=True)
        return True
    return False


async def _free_app_bookings(session: AsyncSession, app) -> None:
    if app.interview_at:
        await free_slot_by_start(session, SlotKind.interview, app.interview_at)
        app.interview_at = None
    if app.training_at:
        await free_slot_by_start(session, SlotKind.training, app.training_at)
        app.training_at = None
    if app.medical_at:
        await free_slot_by_start(session, SlotKind.medical, app.medical_at)
        app.medical_at = None
    await session.flush()


async def _render_docs_list(session: AsyncSession, app_id: int):
    docs = await get_documents_for_application(session, app_id)
    if not docs:
        return texts.HR_REVIEW_NO_DOCS, None
    builder = InlineKeyboardBuilder()
    for doc in docs:
        req_title = doc.requirement.title if doc.requirement else str(doc.requirement_id)
        builder.button(
            text=f"{req_title} — {doc.status.value}",
            callback_data=f"hr:doc:{doc.id}",
        )
    builder.button(text="◀️ Назад", callback_data=f"hr:app:{app_id}")
    builder.adjust(1)
    return texts.HR_REVIEW_DOCS_HEADER.format(app_id=app_id), builder.as_markup()


@router.callback_query(F.data.startswith("hr:docs:"))
async def hr_show_documents(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        await callback.answer(texts.HR_NO_ACCESS)
        return

    app_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    text, markup = await _render_docs_list(session, app_id)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("hr:doc:"))
async def hr_document_card(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    doc_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    result = await session.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        await callback.answer(texts.HR_DOC_NOT_FOUND)
        return

    await session.refresh(doc, ["requirement"])
    req_title = doc.requirement.title if doc.requirement else "—"
    text = texts.HR_REVIEW_DOC_CARD.format(
        req_title=req_title,
        file_name=doc.original_name or "—",
        size_kb=round((doc.size_bytes or 0) / 1024, 1),
        status=doc.status.value,
    )
    if doc.reject_reason:
        text += texts.HR_REVIEW_REJECT_REASON_LINE.format(reason=doc.reject_reason)

    if callback.message:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=document_actions_keyboard(doc),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("hr:dl_doc:"))
async def hr_download_document(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    doc_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    result = await session.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        await callback.answer(texts.HR_DOC_NOT_FOUND)
        return

    file_path = get_absolute_path(doc.file_path)
    if not file_path.exists():
        await callback.answer(texts.HR_FILE_MISSING)
        return

    session.add(
        AuditLog(
            application_id=doc.application_id,
            actor_tg_id=callback.from_user.id if callback.from_user else None,
            event="doc_downloaded",
            details=f"doc_id={doc.id}",
        )
    )

    if callback.message:
        await callback.message.answer_document(FSInputFile(file_path))
    await callback.answer()


@router.callback_query(F.data.startswith("hr:approve_doc:"))
async def hr_approve_document(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    doc_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    result = await session.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        await callback.answer(texts.HR_DOC_NOT_FOUND)
        return

    await session.refresh(doc, ["requirement"])
    await update_document_status(session, doc, DocumentStatus.approved)

    session.add(
        AuditLog(
            application_id=doc.application_id,
            actor_tg_id=callback.from_user.id if callback.from_user else None,
            event="doc_approved",
            details=f"doc_id={doc.id}",
        )
    )

    req_title = doc.requirement.title if doc.requirement else "—"
    text, markup = await _render_docs_list(session, doc.application_id)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer(texts.HR_DOC_APPROVED.format(title=req_title), show_alert=False)


@router.callback_query(F.data.startswith("hr:reject_doc:"))
async def hr_reject_doc_start(
    callback: CallbackQuery, state: FSMContext, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    doc_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    await state.set_state(HrRejectDocStates.waiting_reason)
    await state.update_data(doc_id=doc_id)
    if callback.message:
        await callback.message.delete()
        await callback.message.answer(
            texts.HR_ASK_REJECT_REASON, reply_markup=cancel_reply_keyboard()
        )
    await callback.answer()


@router.message(HrRejectDocStates.waiting_reason)
async def hr_reject_doc_reason(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    data = await state.get_data()
    doc_id: int = data["doc_id"]
    reason = message.text or ""

    result = await session.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        await message.answer(texts.HR_DOC_NOT_FOUND)
        await state.clear()
        return

    await session.refresh(doc, ["requirement", "application"])
    await update_document_status(session, doc, DocumentStatus.rejected, reject_reason=reason)

    session.add(
        AuditLog(
            application_id=doc.application_id,
            actor_tg_id=message.from_user.id if message.from_user else None,
            event="doc_rejected",
            details=f"doc_id={doc.id}, reason={reason}",
        )
    )

    app = await get_application(session, doc.application_id)
    if app:
        await session.refresh(app, ["user"])
        await notifications.notify_user(
            bot=message.bot,  # type: ignore[arg-type]
            tg_id=app.user.tg_id,
            text=texts.NOTIFY_DOC_REJECTED.format(
                title=doc.requirement.title if doc.requirement else "—",
                app_id=doc.application_id,
                reason=reason,
            ),
        )

    req_title = doc.requirement.title if doc.requirement else "—"
    await message.answer(texts.HR_DOC_REJECTED.format(title=req_title))
    text, markup = await _render_docs_list(session, doc.application_id)
    await message.answer(text, reply_markup=markup)
    await state.clear()


@router.callback_query(F.data.startswith("hr:approve:"))
async def hr_approve_application(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    app_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    app = await get_application(session, app_id)
    if not app:
        await callback.answer(texts.HR_APP_NOT_FOUND)
        return
    if await _guard_cancelled(callback, app):
        return

    await update_application_status(session, app, ApplicationStatus.approved)
    session.add(
        AuditLog(
            application_id=app_id,
            actor_tg_id=callback.from_user.id if callback.from_user else None,
            event="application_approved",
        )
    )

    await session.refresh(app, ["user"])
    await notifications.notify_user(
        bot=callback.bot,  # type: ignore[arg-type]
        tg_id=app.user.tg_id,
        text=texts.NOTIFY_STATUS_CHANGED.format(
            app_id=app_id,
            status=texts.STATUS_LABELS["approved"],
        ),
    )

    if callback.message:
        await callback.message.edit_text(texts.HR_REVIEW_APP_APPROVED.format(app_id=app_id))
    await callback.answer()


@router.callback_query(F.data.startswith("hr:reject:"))
async def hr_reject_application(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    app_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    app = await get_application(session, app_id)
    if not app:
        await callback.answer(texts.HR_APP_NOT_FOUND)
        return
    if await _guard_cancelled(callback, app):
        return

    await _free_app_bookings(session, app)
    await update_application_status(session, app, ApplicationStatus.rejected)
    session.add(
        AuditLog(
            application_id=app_id,
            actor_tg_id=callback.from_user.id if callback.from_user else None,
            event="application_rejected",
        )
    )

    await session.refresh(app, ["user"])
    await notifications.notify_user(
        bot=callback.bot,  # type: ignore[arg-type]
        tg_id=app.user.tg_id,
        text=texts.NOTIFY_STATUS_CHANGED.format(
            app_id=app_id,
            status=texts.STATUS_LABELS["rejected"],
        ),
    )

    if callback.message:
        await callback.message.edit_text(texts.HR_REVIEW_APP_REJECTED.format(app_id=app_id))
    await callback.answer()


@router.callback_query(F.data.startswith("hr:cancel_app:"))
async def hr_cancel_application(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    app_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    app = await get_application(session, app_id)
    if not app:
        await callback.answer(texts.HR_APP_NOT_FOUND)
        return

    await _free_app_bookings(session, app)
    await update_application_status(session, app, ApplicationStatus.cancelled)
    session.add(
        AuditLog(
            application_id=app_id,
            actor_tg_id=callback.from_user.id if callback.from_user else None,
            event="application_cancelled_by_hr",
        )
    )

    await session.refresh(app, ["user"])
    await notifications.notify_user(
        bot=callback.bot,  # type: ignore[arg-type]
        tg_id=app.user.tg_id,
        text=texts.NOTIFY_STATUS_CHANGED.format(
            app_id=app_id,
            status=texts.STATUS_LABELS["cancelled"],
        ),
    )

    if callback.message:
        await callback.message.edit_text(texts.HR_APP_CANCELLED.format(app_id=app_id))
    await callback.answer()


@router.callback_query(F.data.startswith("hr:request_doc:"))
async def hr_request_document(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    app_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    app = await get_application(session, app_id)
    if not app:
        await callback.answer(texts.HR_APP_NOT_FOUND)
        return

    if await _guard_cancelled(callback, app):
        return

    requirements = await get_requirements_for_goal(session, app.goal_id)
    await state.set_state(HrRequestDocStates.choosing_req)
    await state.update_data(app_id=app_id)
    if callback.message:
        await callback.message.edit_text(
            texts.HR_REVIEW_CHOOSE_DOC_REQ,
            reply_markup=request_doc_keyboard(requirements),
        )
    await callback.answer()


@router.callback_query(HrRequestDocStates.choosing_req, F.data.startswith("hr:req_doc:"))
async def hr_send_doc_request(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    req_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    data = await state.get_data()
    app_id: int | None = data.get("app_id")
    if app_id is None:
        await callback.answer(texts.HR_SESSION_EXPIRED)
        await state.clear()
        return

    result = await session.execute(
        select(DocumentRequirement).where(DocumentRequirement.id == req_id)
    )
    req = result.scalar_one_or_none()
    if not req:
        await callback.answer(texts.HR_REQ_NOT_FOUND)
        return

    app = await get_application(session, app_id)
    if not app:
        await callback.answer(texts.HR_APP_NOT_FOUND)
        await state.clear()
        return

    await session.refresh(app, ["user"])
    session.add(
        ChatMessage(
            application_id=app.id,
            from_role=MessageFromRole.hr,
            requested_doc_code=req.code,
        )
    )
    student_kb = InlineKeyboardBuilder()
    student_kb.button(
        text="📎 Прислать документ",
        callback_data=f"candidate:req_doc:{app.id}:{req.id}",
    )
    student_kb.adjust(1)
    await notifications.notify_user(
        bot=callback.bot,  # type: ignore[arg-type]
        tg_id=app.user.tg_id,
        text=texts.NOTIFY_DOC_REQUESTED.format(app_id=app.id, title=req.title),
        reply_markup=student_kb.as_markup(),
    )

    if callback.message:
        await callback.message.edit_text(
            texts.HR_REVIEW_DOC_REQUEST_SENT.format(title=req.title, app_id=app.id)
        )
    await state.clear()
    await callback.answer()


@router.callback_query(F.data.startswith("hr:message:"))
async def hr_message_start(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    app_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    app = await get_application(session, app_id)
    if not app:
        await callback.answer(texts.HR_APP_NOT_FOUND)
        return
    if await _guard_cancelled(callback, app):
        return
    await state.set_state(HrMessageStates.waiting_text)
    await state.update_data(app_id=app_id)
    if callback.message:
        await callback.message.delete()
        await callback.message.answer(
            texts.HR_REVIEW_ASK_MESSAGE, reply_markup=cancel_reply_keyboard()
        )
    await callback.answer()


@router.message(HrMessageStates.waiting_text)
async def hr_message_send(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    data = await state.get_data()
    app_id: int = data["app_id"]
    text = message.text or ""

    app = await get_application(session, app_id)
    if not app:
        await message.answer(texts.HR_APP_NOT_FOUND)
        await state.clear()
        return

    session.add(
        ChatMessage(
            application_id=app_id,
            from_role=MessageFromRole.hr,
            text=text,
        )
    )

    await session.refresh(app, ["user"])
    await notifications.notify_user(
        bot=message.bot,  # type: ignore[arg-type]
        tg_id=app.user.tg_id,
        text=texts.NOTIFY_HR_MESSAGE.format(app_id=app_id, text=text),
    )

    await message.answer(texts.HR_REVIEW_MESSAGE_SENT, reply_markup=hr_main_menu())
    await state.clear()


@router.callback_query(F.data.startswith("hr:set_interview:"))
async def hr_set_interview_start(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    app_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    app = await get_application(session, app_id)
    if not app:
        await callback.answer(texts.HR_APP_NOT_FOUND)
        return
    if await _guard_cancelled(callback, app):
        return
    slots = await get_available_slots(session, SlotKind.interview, from_dt=datetime.now())
    if not slots:
        await callback.answer(texts.HR_ASSIGN_NO_SLOTS, show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for slot in slots:
        dt = fmt_datetime(slot.starts_at)
        free = slot.capacity - slot.booked_count
        builder.button(
            text=f"{dt} (свободно {free}/{slot.capacity})",
            callback_data=f"hr:pick_interview:{app_id}:{slot.id}",
        )
    builder.button(text="◀️ Назад", callback_data=f"hr:app:{app_id}")
    builder.adjust(1)

    if callback.message:
        await callback.message.edit_text(
            texts.HR_ASSIGN_INTERVIEW_HEADER.format(app_id=app_id),
            reply_markup=builder.as_markup(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("hr:pick_interview:"))
async def hr_pick_interview(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    parts = callback.data.split(":")  # type: ignore[union-attr]
    app_id = int(parts[2])
    slot_id = int(parts[3])

    app = await get_application(session, app_id)
    if not app:
        await callback.answer(texts.HR_APP_NOT_FOUND)
        return

    slot = await book_slot(session, slot_id)
    if slot is None:
        await callback.answer(texts.HR_ASSIGN_INTERVIEW_TAKEN, show_alert=True)
        return

    await set_interview_slot(session, app, slot.starts_at)
    session.add(
        AuditLog(
            application_id=app_id,
            actor_tg_id=callback.from_user.id if callback.from_user else None,
            event="interview_scheduled",
            details=f"slot_id={slot.id}",
        )
    )

    await session.refresh(app, ["user"])
    dt_str = fmt_datetime(slot.starts_at)
    await notifications.notify_user(
        bot=callback.bot,  # type: ignore[arg-type]
        tg_id=app.user.tg_id,
        text=texts.NOTIFY_INTERVIEW_SCHEDULED.format(app_id=app_id, dt=dt_str),
    )

    if callback.message:
        await callback.message.edit_text(
            texts.HR_ASSIGN_INTERVIEW_SUCCESS.format(dt=dt_str)
        )
    await callback.answer()
