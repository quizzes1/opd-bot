from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.bot import texts
from opdbot.bot.keyboards.hr import document_actions_keyboard, request_doc_keyboard
from opdbot.bot.states.hr import HrMessageStates, HrRejectDocStates
from opdbot.db.models import (
    AuditLog,
    ApplicationStatus,
    Document,
    DocumentStatus,
    Message as DbMessage,
    MessageFromRole,
    UserRole,
)
from opdbot.db.repo.applications import get_application, update_application_status
from opdbot.db.repo.documents import (
    get_documents_for_application,
    get_requirements_for_goal,
    update_document_status,
)
from opdbot.db.repo.users import get_user_by_tg_id
from opdbot.services import notifications

router = Router(name="hr_review")


@router.callback_query(F.data.startswith("hr:docs:"))
async def hr_show_documents(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        await callback.answer("Нет доступа.")
        return

    app_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    docs = await get_documents_for_application(session, app_id)

    if not docs:
        if callback.message:
            await callback.message.edit_text("Документов нет.")
        await callback.answer()
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for doc in docs:
        status_label = texts.STATUS_LABELS.get(doc.status.value, doc.status.value) if hasattr(texts, "STATUS_LABELS") else doc.status.value
        req_title = doc.requirement.title if doc.requirement else doc.requirement_id
        builder.button(
            text=f"{req_title} — {doc.status.value}",
            callback_data=f"hr:doc:{doc.id}",
        )
    builder.button(text="◀️ Назад", callback_data=f"hr:app:{app_id}")
    builder.adjust(1)

    if callback.message:
        await callback.message.edit_text(
            f"Документы по заявке #{app_id}:",
            reply_markup=builder.as_markup(),
        )
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
        await callback.answer("Документ не найден.")
        return

    from sqlalchemy.orm import selectinload
    await session.refresh(doc, ["requirement"])
    req_title = doc.requirement.title if doc.requirement else "—"
    text = (
        f"Документ: <b>{req_title}</b>\n"
        f"Файл: {doc.original_name or '—'}\n"
        f"Размер: {round((doc.size_bytes or 0) / 1024, 1)} КБ\n"
        f"Статус: {doc.status.value}\n"
    )
    if doc.reject_reason:
        text += f"Причина отклонения: {doc.reject_reason}\n"

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
        await callback.answer("Документ не найден.")
        return

    from pathlib import Path
    from opdbot.config import settings

    file_path = Path(settings.storage_root) / doc.file_path
    if not file_path.exists():
        await callback.answer("Файл не найден на диске.")
        return

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
        await callback.answer("Документ не найден.")
        return

    await session.refresh(doc, ["requirement"])
    await update_document_status(session, doc, DocumentStatus.approved)

    log = AuditLog(
        application_id=doc.application_id,
        actor_tg_id=callback.from_user.id if callback.from_user else None,
        event="doc_approved",
        details=f"doc_id={doc.id}",
    )
    session.add(log)

    req_title = doc.requirement.title if doc.requirement else "—"
    if callback.message:
        await callback.message.edit_text(
            texts.HR_DOC_APPROVED.format(title=req_title),
        )
    await callback.answer()


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
        await callback.message.edit_text(texts.HR_ASK_REJECT_REASON)
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
        await message.answer("Документ не найден.")
        await state.clear()
        return

    await session.refresh(doc, ["requirement", "application"])
    await update_document_status(session, doc, DocumentStatus.rejected, reject_reason=reason)

    log = AuditLog(
        application_id=doc.application_id,
        actor_tg_id=message.from_user.id if message.from_user else None,
        event="doc_rejected",
        details=f"doc_id={doc.id}, reason={reason}",
    )
    session.add(log)

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
        await callback.answer("Заявка не найдена.")
        return

    await update_application_status(session, app, ApplicationStatus.approved)
    log = AuditLog(
        application_id=app_id,
        actor_tg_id=callback.from_user.id if callback.from_user else None,
        event="application_approved",
    )
    session.add(log)

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
        await callback.message.edit_text(f"✅ Заявка #{app_id} одобрена.")
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
        await callback.answer("Заявка не найдена.")
        return

    await update_application_status(session, app, ApplicationStatus.rejected)
    log = AuditLog(
        application_id=app_id,
        actor_tg_id=callback.from_user.id if callback.from_user else None,
        event="application_rejected",
    )
    session.add(log)

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
        await callback.message.edit_text(f"❌ Заявка #{app_id} отклонена.")
    await callback.answer()


@router.callback_query(F.data.startswith("hr:request_doc:"))
async def hr_request_document(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    app_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    app = await get_application(session, app_id)
    if not app:
        await callback.answer("Заявка не найдена.")
        return

    requirements = await get_requirements_for_goal(session, app.goal_id)
    if callback.message:
        await callback.message.edit_text(
            "Выберите документ для запроса:",
            reply_markup=request_doc_keyboard(requirements),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("hr:req_doc:"))
async def hr_send_doc_request(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    req_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    from sqlalchemy.orm import selectinload
    from opdbot.db.models import DocumentRequirement
    result = await session.execute(
        select(DocumentRequirement).where(DocumentRequirement.id == req_id)
    )
    req = result.scalar_one_or_none()
    if not req:
        await callback.answer("Требование не найдено.")
        return

    # Find application from context - search recent apps
    apps = await list_applications_by_goal(session, req.goal_id)
    # We need to get the app ID from the conversation state — use message context
    # For now, notify all candidates with docs_submitted status for this goal
    for app in apps:
        await session.refresh(app, ["user"])
        msg_record = DbMessage(
            application_id=app.id,
            from_role=MessageFromRole.hr,
            requested_doc_code=req.code,
        )
        session.add(msg_record)
        await notifications.notify_user(
            bot=callback.bot,  # type: ignore[arg-type]
            tg_id=app.user.tg_id,
            text=texts.NOTIFY_DOC_REQUESTED.format(app_id=app.id, title=req.title),
        )

    if callback.message:
        await callback.message.edit_text(f"✅ Запрос документа «{req.title}» отправлен.")
    await callback.answer()


async def list_applications_by_goal(session: AsyncSession, goal_id: int) -> list:
    from sqlalchemy.orm import selectinload
    from opdbot.db.models import Application
    from sqlalchemy import select as sa_select
    result = await session.execute(
        sa_select(Application)
        .options(selectinload(Application.user))
        .where(Application.goal_id == goal_id, Application.status == ApplicationStatus.docs_submitted)
    )
    return list(result.scalars().all())


@router.callback_query(F.data.startswith("hr:message:"))
async def hr_message_start(
    callback: CallbackQuery, state: FSMContext, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    app_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    await state.set_state(HrMessageStates.waiting_text)
    await state.update_data(app_id=app_id)
    if callback.message:
        await callback.message.edit_text("Введите сообщение кандидату:")
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
        await message.answer("Заявка не найдена.")
        await state.clear()
        return

    msg_record = DbMessage(
        application_id=app_id,
        from_role=MessageFromRole.hr,
        text=text,
    )
    session.add(msg_record)

    await session.refresh(app, ["user"])
    await notifications.notify_user(
        bot=message.bot,  # type: ignore[arg-type]
        tg_id=app.user.tg_id,
        text=texts.NOTIFY_HR_MESSAGE.format(app_id=app_id, text=text),
    )

    await message.answer("✅ Сообщение отправлено кандидату.")
    await state.clear()
