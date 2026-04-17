from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.bot import texts
from opdbot.bot.states.hr import HrCharacteristicStates
from opdbot.db.models import GeneratedDocument, GeneratedDocumentKind, UserRole
from opdbot.db.repo.applications import get_application
from opdbot.services import documents as doc_service
from opdbot.services import notifications

router = Router(name="hr_documents_gen")


@router.callback_query(F.data.startswith("hr:medical:"))
async def hr_send_medical_referral(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    app_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    app = await get_application(session, app_id)
    if not app:
        await callback.answer("Заявка не найдена.")
        return

    try:
        file_path = await doc_service.render_medical_referral(app)
    except Exception as e:
        if callback.message:
            await callback.message.edit_text(f"Ошибка генерации документа: {e}")
        await callback.answer()
        return

    gen_doc = GeneratedDocument(
        application_id=app_id,
        kind=GeneratedDocumentKind.medical_referral,
        file_path=str(file_path),
    )
    session.add(gen_doc)
    await session.flush()

    await session.refresh(app, ["user"])
    await notifications.notify_user(
        bot=callback.bot,  # type: ignore[arg-type]
        tg_id=app.user.tg_id,
        text=f"Направление на медосмотр по заявке #{app_id} сформировано. Прикреплён файл.",
        document=FSInputFile(file_path),
    )

    if callback.message:
        await callback.message.answer_document(
            FSInputFile(file_path),
            caption=f"Направление на медосмотр для заявки #{app_id}",
        )
        await callback.message.edit_text("✅ Направление сформировано и отправлено кандидату.")
    await callback.answer()


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
        await callback.message.edit_text("Введите ФИО руководителя практики/стажировки:")
    await callback.answer()


@router.message(HrCharacteristicStates.waiting_supervisor)
async def hr_characteristic_supervisor(message: Message, state: FSMContext) -> None:
    await state.update_data(supervisor=message.text or "")
    await state.set_state(HrCharacteristicStates.waiting_topic)
    await message.answer("Введите тему практики/стажировки:")


@router.message(HrCharacteristicStates.waiting_topic)
async def hr_characteristic_topic(message: Message, state: FSMContext) -> None:
    await state.update_data(topic=message.text or "")
    await state.set_state(HrCharacteristicStates.waiting_period_from)
    await message.answer("Введите дату начала (ДД.ММ.ГГГГ):")


@router.message(HrCharacteristicStates.waiting_period_from)
async def hr_characteristic_period_from(message: Message, state: FSMContext) -> None:
    try:
        dt = datetime.strptime((message.text or "").strip(), "%d.%m.%Y")
    except ValueError:
        await message.answer("Неверный формат. Введите дату ДД.ММ.ГГГГ:")
        return
    await state.update_data(period_from=dt.isoformat())
    await state.set_state(HrCharacteristicStates.waiting_period_to)
    await message.answer("Введите дату окончания (ДД.ММ.ГГГГ):")


@router.message(HrCharacteristicStates.waiting_period_to)
async def hr_characteristic_period_to(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    try:
        dt_to = datetime.strptime((message.text or "").strip(), "%d.%m.%Y")
    except ValueError:
        await message.answer("Неверный формат. Введите дату ДД.ММ.ГГГГ:")
        return

    data = await state.get_data()
    app_id: int = data["app_id"]
    supervisor: str = data["supervisor"]
    topic: str = data["topic"]
    period_from = datetime.fromisoformat(data["period_from"])

    app = await get_application(session, app_id)
    if not app:
        await message.answer("Заявка не найдена.")
        await state.clear()
        return

    try:
        file_path = await doc_service.render_practice_characteristic(
            app, supervisor=supervisor, topic=topic, period_from=period_from, period_to=dt_to
        )
    except Exception as e:
        await message.answer(f"Ошибка генерации документа: {e}")
        await state.clear()
        return

    gen_doc = GeneratedDocument(
        application_id=app_id,
        kind=GeneratedDocumentKind.practice_characteristic,
        file_path=str(file_path),
    )
    session.add(gen_doc)
    await session.flush()

    await message.answer_document(
        FSInputFile(file_path),
        caption=f"Характеристика по заявке #{app_id}",
    )
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
        await callback.answer("Заявка не найдена.")
        return

    gen_docs = app.generated_documents
    if not gen_docs:
        if callback.message:
            await callback.message.edit_text("Сгенерированных документов нет.")
        await callback.answer()
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for gd in gen_docs:
        builder.button(
            text=f"📥 {gd.kind.value} ({gd.created_at.strftime('%d.%m.%Y')})",
            callback_data=f"hr:dl_gendoc:{gd.id}",
        )
    builder.button(text="◀️ Назад", callback_data=f"hr:app:{app_id}")
    builder.adjust(1)

    if callback.message:
        await callback.message.edit_text(
            f"Сгенерированные документы по заявке #{app_id}:",
            reply_markup=builder.as_markup(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("hr:dl_gendoc:"))
async def hr_download_generated_doc(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    from sqlalchemy import select
    gd_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    result = await session.execute(
        select(GeneratedDocument).where(GeneratedDocument.id == gd_id)
    )
    gd = result.scalar_one_or_none()
    if not gd:
        await callback.answer("Документ не найден.")
        return

    from pathlib import Path
    file_path = Path(gd.file_path)
    if not file_path.exists():
        await callback.answer("Файл не найден на диске.")
        return

    if callback.message:
        await callback.message.answer_document(FSInputFile(file_path))
    await callback.answer()
