from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.bot import texts
from opdbot.bot.keyboards.main_menu import cancel_reply_keyboard, hr_main_menu
from opdbot.bot.states.hr import HrCharacteristicStates, HrMedicalDateStates
from opdbot.db.models import (
    AuditLog,
    GeneratedDocument,
    GeneratedDocumentKind,
    UserRole,
)
from opdbot.db.repo.applications import get_application, set_medical_date
from opdbot.services import documents as doc_service
from opdbot.services import notifications
from opdbot.services.storage import get_absolute_path

router = Router(name="hr_documents_gen")

GEN_DOC_LABELS = texts.HR_DOCGEN_LABELS


@router.callback_query(F.data.startswith("hr:medical:"))
async def hr_send_medical_referral(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    app_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    app = await get_application(session, app_id)
    if not app:
        await callback.answer(texts.HR_APP_NOT_FOUND)
        return

    try:
        file_rel = await doc_service.render_medical_referral(app)
    except Exception as e:
        if callback.message:
            await callback.message.edit_text(texts.HR_DOCGEN_ERROR.format(error=e))
        await callback.answer()
        return

    session.add(
        GeneratedDocument(
            application_id=app_id,
            kind=GeneratedDocumentKind.medical_referral,
            file_path=str(file_rel),
        )
    )
    await session.flush()

    await session.refresh(app, ["user"])
    abs_path = get_absolute_path(file_rel)
    await notifications.notify_user(
        bot=callback.bot,  # type: ignore[arg-type]
        tg_id=app.user.tg_id,
        text=texts.NOTIFY_MEDICAL_REFERRAL.format(app_id=app_id),
        document=FSInputFile(abs_path),
    )

    await state.set_state(HrMedicalDateStates.waiting_date)
    await state.update_data(app_id=app_id)
    if callback.message:
        await callback.message.edit_text(texts.HR_MEDICAL_ASK_DATE)
        await callback.message.answer(
            texts.HR_MEDICAL_ASK_DATE, reply_markup=cancel_reply_keyboard()
        )
    await callback.answer()


@router.message(HrMedicalDateStates.waiting_date)
async def hr_set_medical_date(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    try:
        dt = datetime.strptime((message.text or "").strip(), "%d.%m.%Y %H:%M")
    except ValueError:
        await message.answer(texts.HR_DOCGEN_BAD_DATETIME)
        return

    data = await state.get_data()
    app_id: int = data["app_id"]

    app = await get_application(session, app_id)
    if not app:
        await message.answer(texts.HR_APP_NOT_FOUND)
        await state.clear()
        return

    await set_medical_date(session, app, dt)
    session.add(
        AuditLog(
            application_id=app_id,
            actor_tg_id=message.from_user.id if message.from_user else None,
            event="medical_date_set",
            details=dt.isoformat(),
        )
    )

    await session.refresh(app, ["user"])
    await notifications.notify_user(
        bot=message.bot,  # type: ignore[arg-type]
        tg_id=app.user.tg_id,
        text=texts.NOTIFY_MEDICAL_DATE.format(
            app_id=app_id, dt=dt.strftime("%d.%m.%Y %H:%M")
        ),
    )

    await message.answer(
        texts.HR_MEDICAL_DATE_SET.format(dt=dt.strftime("%d.%m.%Y %H:%M")),
        reply_markup=hr_main_menu(),
    )
    await state.clear()


@router.callback_query(F.data.startswith("hr:characteristic:"))
async def hr_characteristic_start(
    callback: CallbackQuery, state: FSMContext, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    app_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    await state.set_state(HrCharacteristicStates.waiting_supervisor)
    await state.update_data(app_id=app_id)
    if callback.message:
        await callback.message.delete()
        await callback.message.answer(
            texts.HR_DOCGEN_ASK_SUPERVISOR, reply_markup=cancel_reply_keyboard()
        )
    await callback.answer()


@router.message(HrCharacteristicStates.waiting_supervisor)
async def hr_characteristic_supervisor(message: Message, state: FSMContext) -> None:
    await state.update_data(supervisor=message.text or "")
    await state.set_state(HrCharacteristicStates.waiting_topic)
    await message.answer(texts.HR_DOCGEN_ASK_TOPIC)


@router.message(HrCharacteristicStates.waiting_topic)
async def hr_characteristic_topic(message: Message, state: FSMContext) -> None:
    await state.update_data(topic=message.text or "")
    await state.set_state(HrCharacteristicStates.waiting_period_from)
    await message.answer(texts.HR_DOCGEN_ASK_PERIOD_FROM)


@router.message(HrCharacteristicStates.waiting_period_from)
async def hr_characteristic_period_from(message: Message, state: FSMContext) -> None:
    try:
        dt = datetime.strptime((message.text or "").strip(), "%d.%m.%Y")
    except ValueError:
        await message.answer(texts.HR_DOCGEN_BAD_DATE)
        return
    await state.update_data(period_from=dt.isoformat())
    await state.set_state(HrCharacteristicStates.waiting_period_to)
    await message.answer(texts.HR_DOCGEN_ASK_PERIOD_TO)


@router.message(HrCharacteristicStates.waiting_period_to)
async def hr_characteristic_period_to(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    try:
        dt_to = datetime.strptime((message.text or "").strip(), "%d.%m.%Y")
    except ValueError:
        await message.answer(texts.HR_DOCGEN_BAD_DATE)
        return

    data = await state.get_data()
    app_id: int = data["app_id"]
    supervisor: str = data["supervisor"]
    topic: str = data["topic"]
    period_from = datetime.fromisoformat(data["period_from"])

    if dt_to < period_from:
        await message.answer(texts.HR_DOCGEN_PERIOD_INVALID)
        return

    app = await get_application(session, app_id)
    if not app:
        await message.answer(texts.HR_APP_NOT_FOUND)
        await state.clear()
        return

    try:
        file_rel = await doc_service.render_practice_characteristic(
            app, supervisor=supervisor, topic=topic, period_from=period_from, period_to=dt_to
        )
    except Exception as e:
        await message.answer(texts.HR_DOCGEN_ERROR.format(error=e))
        await state.clear()
        return

    session.add(
        GeneratedDocument(
            application_id=app_id,
            kind=GeneratedDocumentKind.practice_characteristic,
            file_path=str(file_rel),
        )
    )
    await session.flush()

    await message.answer_document(
        FSInputFile(get_absolute_path(file_rel)),
        caption=texts.HR_DOCGEN_CHAR_CAPTION.format(app_id=app_id),
    )
    await message.answer(texts.HR_WELCOME, reply_markup=hr_main_menu())
    await state.clear()


@router.callback_query(F.data.startswith("hr:gendocs:"))
async def hr_show_generated_docs(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    app_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    app = await get_application(session, app_id)
    if not app:
        await callback.answer(texts.HR_APP_NOT_FOUND)
        return

    gen_docs = app.generated_documents
    if not gen_docs:
        if callback.message:
            await callback.message.edit_text(texts.HR_DOCGEN_EMPTY)
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    for gd in gen_docs:
        label = GEN_DOC_LABELS.get(gd.kind.value, gd.kind.value)
        builder.button(
            text=f"📥 {label} ({gd.created_at.strftime('%d.%m.%Y')})",
            callback_data=f"hr:dl_gendoc:{gd.id}",
        )
    builder.button(text="◀️ Назад", callback_data=f"hr:app:{app_id}")
    builder.adjust(1)

    if callback.message:
        await callback.message.edit_text(
            texts.HR_DOCGEN_LIST_HEADER.format(app_id=app_id),
            reply_markup=builder.as_markup(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("hr:dl_gendoc:"))
async def hr_download_generated_doc(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    gd_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    result = await session.execute(
        select(GeneratedDocument).where(GeneratedDocument.id == gd_id)
    )
    gd = result.scalar_one_or_none()
    if not gd:
        await callback.answer(texts.HR_DOC_NOT_FOUND)
        return

    file_path = get_absolute_path(gd.file_path)
    if not file_path.exists():
        await callback.answer(texts.HR_FILE_MISSING)
        return

    session.add(
        AuditLog(
            application_id=gd.application_id,
            actor_tg_id=callback.from_user.id if callback.from_user else None,
            event="gendoc_downloaded",
            details=f"gendoc_id={gd.id}",
        )
    )

    if callback.message:
        await callback.message.answer_document(FSInputFile(file_path))
    await callback.answer()
