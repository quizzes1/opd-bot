from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.bot import texts
from opdbot.bot.keyboards.main_menu import candidate_main_menu
from opdbot.bot.states.candidate import DocUploadStates
from opdbot.db.models import ApplicationStatus, DocumentRequirement
from opdbot.db.repo.applications import get_application, update_application_status
from opdbot.db.repo.documents import (
    get_requirements_for_goal,
    get_uploaded_requirement_ids,
    save_document,
)
from opdbot.db.repo.users import get_all_staff
from opdbot.services import notifications
from opdbot.services.storage import save_tg_file
from opdbot.utils.validators import TELEGRAM_DOWNLOAD_LIMIT_BYTES, validate_file

router = Router(name="docs")


def _progress(all_reqs: list[DocumentRequirement], pending: list[DocumentRequirement]) -> tuple[int, int]:
    total = len(all_reqs) or 1
    current = total - len(pending) + 1
    return max(current, 1), total


def _pending_required(
    all_reqs: list[DocumentRequirement],
    uploaded_ids: set[int],
    skipped_ids: set[int],
) -> list[DocumentRequirement]:
    return [
        r
        for r in all_reqs
        if r.id not in uploaded_ids and (r.is_required or r.id not in skipped_ids)
    ]


def _doc_request_keyboard(req: DocumentRequirement) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    if not req.is_required:
        builder.button(text=texts.DOC_SKIP_BUTTON, callback_data=f"doc:skip:{req.id}")
    builder.adjust(1)
    return builder


async def _prompt_next(
    message_or_cb: Message | CallbackQuery,
    state: FSMContext,
    req: DocumentRequirement,
    current: int,
    total: int,
) -> None:
    required_mark = "" if req.is_required else texts.DOC_OPTIONAL_MARK
    text = texts.DOC_REQUEST.format(
        current=current,
        total=total,
        title=req.title,
        allowed_mime=req.allowed_mime,
        max_size=req.max_size_mb,
        optional=required_mark,
    )
    kb = _doc_request_keyboard(req).as_markup() if not req.is_required else None
    target = message_or_cb.message if isinstance(message_or_cb, CallbackQuery) else message_or_cb
    if target is None:
        return
    await target.answer(text, parse_mode="HTML", reply_markup=kb)


async def start_doc_upload(
    message: Message, state: FSMContext, session: AsyncSession, application_id: int
) -> None:
    app = await get_application(session, application_id)
    if not app:
        await message.answer(texts.ERROR_NO_ACTIVE_APPLICATION)
        return

    if app.status == ApplicationStatus.draft:
        await update_application_status(session, app, ApplicationStatus.docs_in_progress)

    requirements = await get_requirements_for_goal(session, app.goal_id)
    uploaded_ids = await get_uploaded_requirement_ids(session, application_id)
    pending = _pending_required(requirements, uploaded_ids, set())

    if not pending:
        await message.answer(texts.ALL_DOCS_DONE, reply_markup=candidate_main_menu(True))
        return

    req = pending[0]
    current, total = _progress(requirements, pending)

    await state.set_state(DocUploadStates.uploading)
    await state.update_data(
        application_id=application_id,
        requirement_id=req.id,
        skipped_ids=[],
    )
    await _prompt_next(message, state, req, current, total)


async def _advance(
    target: Message,
    state: FSMContext,
    session: AsyncSession,
    application_id: int,
    bot,
) -> None:
    data = await state.get_data()
    skipped_ids: set[int] = set(data.get("skipped_ids") or [])

    app = await get_application(session, application_id)
    if not app:
        await target.answer(texts.ERROR_GENERIC)
        await state.clear()
        return

    all_reqs = await get_requirements_for_goal(session, app.goal_id)
    uploaded_ids = await get_uploaded_requirement_ids(session, application_id)
    pending = _pending_required(all_reqs, uploaded_ids, skipped_ids)

    if not pending:
        await update_application_status(session, app, ApplicationStatus.docs_submitted)
        await state.clear()

        staff = await get_all_staff(session)
        await session.refresh(app, ["user"])
        user = app.user
        for hr_user in staff:
            await notifications.notify_user(
                bot=bot,
                tg_id=hr_user.tg_id,
                text=texts.NOTIFY_NEW_DOCS.format(
                    full_name=user.full_name or "—", app_id=application_id
                ),
            )

        await target.answer(texts.ALL_DOCS_DONE, reply_markup=candidate_main_menu(True))
        return

    next_req = pending[0]
    current, total = _progress(all_reqs, pending)
    await state.update_data(requirement_id=next_req.id)
    await _prompt_next(target, state, next_req, current, total)


@router.message(DocUploadStates.uploading, F.document | F.photo)
async def handle_document_upload(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    data = await state.get_data()
    application_id: int = data["application_id"]
    requirement_id: int = data["requirement_id"]

    app = await get_application(session, application_id)
    if not app:
        await message.answer(texts.ERROR_GENERIC)
        await state.clear()
        return

    requirements = await get_requirements_for_goal(session, app.goal_id)
    req = next((r for r in requirements if r.id == requirement_id), None)
    if not req:
        await message.answer(texts.ERROR_GENERIC)
        return

    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name or f"doc_{requirement_id}"
        mime = message.document.mime_type or ""
        size = message.document.file_size or 0
    elif message.photo:
        photo = message.photo[-1]
        file_id = photo.file_id
        file_name = f"photo_{requirement_id}.jpg"
        mime = "image/jpeg"
        size = photo.file_size or 0
    else:
        return

    if size > TELEGRAM_DOWNLOAD_LIMIT_BYTES:
        await message.answer(texts.DOC_TOO_LARGE_FOR_TG)
        return

    error = validate_file(mime, size, req.allowed_mime, req.max_size_mb, filename=file_name)
    if error == "mime":
        await message.answer(texts.DOC_INVALID_MIME.format(allowed_mime=req.allowed_mime))
        return
    if error == "size":
        await message.answer(texts.DOC_TOO_LARGE.format(max_size=req.max_size_mb))
        return

    file_path = await save_tg_file(
        bot=message.bot,  # type: ignore[arg-type]
        file_id=file_id,
        user_id=app.user_id,
        application_id=application_id,
        req_code=req.code,
        filename=file_name,
    )

    await save_document(
        session,
        application_id=application_id,
        requirement_id=requirement_id,
        file_path=str(file_path),
        tg_file_id=file_id,
        original_name=file_name,
        mime=mime,
        size_bytes=size,
    )

    await message.answer(
        texts.DOC_RECEIVED_SIMPLE.format(title=req.title),
        parse_mode="HTML",
    )

    await _advance(message, state, session, application_id, message.bot)


@router.callback_query(DocUploadStates.uploading, F.data.startswith("doc:skip:"))
async def handle_document_skip(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    req_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    data = await state.get_data()
    application_id: int = data["application_id"]
    skipped: list[int] = list(data.get("skipped_ids") or [])
    if req_id not in skipped:
        skipped.append(req_id)
    await state.update_data(skipped_ids=skipped)

    if callback.message:
        await callback.message.answer(texts.DOC_SKIPPED)
    await callback.answer()

    target = callback.message if callback.message else None
    if target is None:
        return
    await _advance(target, state, session, application_id, callback.bot)
