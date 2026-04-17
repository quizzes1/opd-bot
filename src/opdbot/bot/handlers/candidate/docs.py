from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.bot import texts
from opdbot.bot.keyboards.main_menu import candidate_main_menu
from opdbot.bot.states.candidate import DocUploadStates
from opdbot.db.models import ApplicationStatus
from opdbot.db.repo.applications import get_application, update_application_status
from opdbot.db.repo.documents import (
    get_requirements_for_goal,
    get_uploaded_requirement_ids,
    save_document,
)
from opdbot.services import notifications
from opdbot.services.storage import save_tg_file
from opdbot.utils.validators import validate_file

router = Router(name="docs")


async def start_doc_upload(
    message: Message, state: FSMContext, session: AsyncSession, application_id: int
) -> None:
    app = await get_application(session, application_id)
    if not app:
        await message.answer(texts.ERROR_NO_ACTIVE_APPLICATION)
        return

    requirements = await get_requirements_for_goal(session, app.goal_id)
    uploaded_ids = await get_uploaded_requirement_ids(session, application_id)

    pending = [r for r in requirements if r.id not in uploaded_ids]
    if not pending:
        await message.answer(texts.ALL_DOCS_DONE, reply_markup=candidate_main_menu())
        return

    req = pending[0]
    total = len(requirements)
    current = total - len(pending) + 1

    await state.set_state(DocUploadStates.uploading)
    await state.update_data(
        application_id=application_id,
        requirement_id=req.id,
        current=current,
        total=total,
    )

    await message.answer(
        texts.DOC_REQUEST.format(
            current=current,
            total=total,
            title=req.title,
            allowed_mime=req.allowed_mime,
            max_size=req.max_size_mb,
        ),
        parse_mode="HTML",
    )


@router.message(DocUploadStates.uploading, F.document | F.photo)
async def handle_document_upload(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    data = await state.get_data()
    application_id: int = data["application_id"]
    requirement_id: int = data["requirement_id"]
    current: int = data["current"]
    total: int = data["total"]

    app = await get_application(session, application_id)
    if not app:
        await message.answer(texts.ERROR_GENERIC)
        return

    from opdbot.db.repo.documents import get_requirements_for_goal as get_reqs
    requirements = await get_reqs(session, app.goal_id)
    req = next((r for r in requirements if r.id == requirement_id), None)
    if not req:
        await message.answer(texts.ERROR_GENERIC)
        return

    # Extract file info
    if message.document:
        file = message.document
        file_id = file.file_id
        file_name = file.file_name or f"doc_{requirement_id}"
        mime = file.mime_type or ""
        size = file.file_size or 0
    elif message.photo:
        file = message.photo[-1]
        file_id = file.file_id
        file_name = f"photo_{requirement_id}.jpg"
        mime = "image/jpeg"
        size = file.file_size or 0
    else:
        return

    error = validate_file(mime, size, req.allowed_mime, req.max_size_mb)
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
        texts.DOC_RECEIVED.format(title=req.title, current=current, total=total),
        parse_mode="HTML",
    )

    uploaded_ids = await get_uploaded_requirement_ids(session, application_id)
    all_reqs = await get_reqs(session, app.goal_id)
    pending = [r for r in all_reqs if r.id not in uploaded_ids]

    if not pending:
        await update_application_status(session, app, ApplicationStatus.docs_submitted)
        await state.clear()

        from opdbot.db.repo.users import get_all_hr
        hr_list = await get_all_hr(session)
        user = app.user
        for hr_user in hr_list:
            await notifications.notify_user(
                bot=message.bot,  # type: ignore[arg-type]
                tg_id=hr_user.tg_id,
                text=texts.NOTIFY_NEW_DOCS.format(
                    full_name=user.full_name or "—", app_id=application_id
                ),
            )

        await message.answer(texts.ALL_DOCS_DONE, reply_markup=candidate_main_menu())
    else:
        next_req = pending[0]
        next_current = len(all_reqs) - len(pending) + 1
        await state.update_data(
            requirement_id=next_req.id,
            current=next_current,
        )
        await message.answer(
            texts.DOC_REQUEST.format(
                current=next_current,
                total=total,
                title=next_req.title,
                allowed_mime=next_req.allowed_mime,
                max_size=next_req.max_size_mb,
            ),
            parse_mode="HTML",
        )
