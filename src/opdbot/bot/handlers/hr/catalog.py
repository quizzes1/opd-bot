from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.bot.states.hr import HrCatalogStates
from opdbot.db.models import DocumentRequirement, Goal, UserRole
from opdbot.db.repo.documents import get_requirements_for_goal

router = Router(name="hr_catalog")


@router.message(F.text == "📂 Каталог документов")
async def hr_catalog_menu(message: Message, session: AsyncSession, role: UserRole) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    result = await session.execute(select(Goal).where(Goal.is_active.is_(True)))
    goals = list(result.scalars().all())

    builder = InlineKeyboardBuilder()
    for goal in goals:
        builder.button(text=goal.title, callback_data=f"hr:catalog:goal:{goal.id}")
    builder.adjust(1)
    await message.answer("Выберите цель для просмотра документов:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("hr:catalog:goal:"))
async def hr_catalog_goal_docs(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    goal_id = int(callback.data.split(":")[3])  # type: ignore[union-attr]
    requirements = await get_requirements_for_goal(session, goal_id)

    builder = InlineKeyboardBuilder()
    for req in requirements:
        req_label = f"{req.title} ({'обяз.' if req.is_required else 'необяз.'})"
        builder.button(text=req_label, callback_data=f"hr:catalog:req:{req.id}")
    builder.button(text="➕ Добавить документ", callback_data=f"hr:catalog:add:{goal_id}")
    builder.button(text="◀️ Назад", callback_data="hr:catalog:back")
    builder.adjust(1)

    if callback.message:
        await callback.message.edit_text(
            f"Документы для цели (всего {len(requirements)}):",
            reply_markup=builder.as_markup(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("hr:catalog:add:"))
async def hr_catalog_add_start(
    callback: CallbackQuery, state: FSMContext, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    goal_id = int(callback.data.split(":")[3])  # type: ignore[union-attr]
    await state.set_state(HrCatalogStates.waiting_doc_title)
    await state.update_data(goal_id=goal_id)
    if callback.message:
        await callback.message.edit_text("Введите название документа:")
    await callback.answer()


@router.message(HrCatalogStates.waiting_doc_title)
async def hr_catalog_doc_title(message: Message, state: FSMContext) -> None:
    await state.update_data(doc_title=message.text or "")
    await state.set_state(HrCatalogStates.waiting_doc_code)
    await message.answer("Введите код документа (латиница, без пробелов, напр. passport):")


@router.message(HrCatalogStates.waiting_doc_code)
async def hr_catalog_doc_code(message: Message, state: FSMContext) -> None:
    code = (message.text or "").strip().lower()
    if not code.replace("_", "").isalpha():
        await message.answer("Код должен содержать только латинские буквы и подчёркивание:")
        return
    await state.update_data(doc_code=code)
    await state.set_state(HrCatalogStates.waiting_doc_mime)
    await message.answer("Допустимые форматы (через запятую, напр. pdf,jpg,jpeg):")


@router.message(HrCatalogStates.waiting_doc_mime)
async def hr_catalog_doc_mime(message: Message, state: FSMContext) -> None:
    await state.update_data(doc_mime=message.text or "pdf,jpg,jpeg")
    await state.set_state(HrCatalogStates.waiting_doc_size)
    await message.answer("Максимальный размер в МБ (напр. 10):")


@router.message(HrCatalogStates.waiting_doc_size)
async def hr_catalog_doc_size(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        max_size = int((message.text or "").strip())
        if max_size <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите положительное число:")
        return

    data = await state.get_data()
    goal_id: int = data["goal_id"]
    title: str = data["doc_title"]
    code: str = data["doc_code"]
    allowed_mime: str = data["doc_mime"]

    existing = await get_requirements_for_goal(session, goal_id)
    order = len(existing)

    req = DocumentRequirement(
        goal_id=goal_id,
        code=code,
        title=title,
        allowed_mime=allowed_mime,
        max_size_mb=max_size,
        order=order,
    )
    session.add(req)
    await session.flush()

    await message.answer(f"✅ Документ «{title}» добавлен в каталог.")
    await state.clear()


@router.callback_query(F.data.startswith("hr:catalog:req:"))
async def hr_catalog_req_detail(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    req_id = int(callback.data.split(":")[3])  # type: ignore[union-attr]
    result = await session.execute(select(DocumentRequirement).where(DocumentRequirement.id == req_id))
    req = result.scalar_one_or_none()
    if not req:
        await callback.answer("Требование не найдено.")
        return

    text = (
        f"<b>{req.title}</b>\n"
        f"Код: {req.code}\n"
        f"Форматы: {req.allowed_mime}\n"
        f"Макс. размер: {req.max_size_mb} МБ\n"
        f"Обязателен: {'да' if req.is_required else 'нет'}\n"
    )

    builder = InlineKeyboardBuilder()
    builder.button(
        text="🗑 Удалить",
        callback_data=f"hr:catalog:del:{req.id}:{req.goal_id}",
    )
    builder.button(text="◀️ Назад", callback_data=f"hr:catalog:goal:{req.goal_id}")
    builder.adjust(1)

    if callback.message:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("hr:catalog:del:"))
async def hr_catalog_delete_req(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    parts = callback.data.split(":")  # type: ignore[union-attr]
    req_id = int(parts[3])
    goal_id = int(parts[4])

    result = await session.execute(select(DocumentRequirement).where(DocumentRequirement.id == req_id))
    req = result.scalar_one_or_none()
    if req:
        await session.delete(req)
        await session.flush()

    if callback.message:
        await callback.message.edit_text(f"Требование удалено.")
    await callback.answer()


@router.callback_query(F.data == "hr:catalog:back")
async def hr_catalog_back(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await session.execute(select(Goal).where(Goal.is_active.is_(True)))
    goals = list(result.scalars().all())

    builder = InlineKeyboardBuilder()
    for goal in goals:
        builder.button(text=goal.title, callback_data=f"hr:catalog:goal:{goal.id}")
    builder.adjust(1)

    if callback.message:
        await callback.message.edit_text(
            "Выберите цель для просмотра документов:",
            reply_markup=builder.as_markup(),
        )
    await callback.answer()
