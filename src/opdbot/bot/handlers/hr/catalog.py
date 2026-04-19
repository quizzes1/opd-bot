from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.bot import texts
from opdbot.bot.keyboards.main_menu import cancel_reply_keyboard, hr_main_menu
from opdbot.bot.states.hr import HrCatalogStates
from opdbot.db.models import DocumentRequirement, Goal, UserRole
from opdbot.db.repo.documents import get_requirements_for_goal
from opdbot.utils.validators import (
    ALLOWED_FORMATS_REGISTRY,
    parse_allowed_formats,
    validate_catalog_code,
)

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
    await message.answer(texts.HR_CATALOG_CHOOSE_GOAL, reply_markup=builder.as_markup())


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
        mark = texts.HR_CATALOG_REQUIRED_MARK if req.is_required else texts.HR_CATALOG_OPTIONAL_MARK
        req_label = texts.HR_CATALOG_REQ_LABEL.format(title=req.title, mark=mark)
        builder.button(text=req_label, callback_data=f"hr:catalog:req:{req.id}")
    builder.button(text="➕ Добавить документ", callback_data=f"hr:catalog:add:{goal_id}")
    builder.button(text="◀️ Назад", callback_data="hr:catalog:back")
    builder.adjust(1)

    if callback.message:
        await callback.message.edit_text(
            texts.HR_CATALOG_GOAL_HEADER.format(count=len(requirements)),
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
        await callback.message.delete()
        await callback.message.answer(
            texts.HR_CATALOG_ASK_TITLE, reply_markup=cancel_reply_keyboard()
        )
    await callback.answer()


@router.message(HrCatalogStates.waiting_doc_title)
async def hr_catalog_doc_title(message: Message, state: FSMContext) -> None:
    await state.update_data(doc_title=message.text or "")
    await state.set_state(HrCatalogStates.waiting_doc_code)
    await message.answer(texts.HR_CATALOG_ASK_CODE)


@router.message(HrCatalogStates.waiting_doc_code)
async def hr_catalog_doc_code(message: Message, state: FSMContext) -> None:
    code = validate_catalog_code(message.text or "")
    if code is None:
        await message.answer(texts.HR_CATALOG_BAD_CODE)
        return
    await state.update_data(doc_code=code)
    await state.set_state(HrCatalogStates.waiting_doc_mime)
    await message.answer(texts.HR_CATALOG_ASK_MIME)


@router.message(HrCatalogStates.waiting_doc_mime)
async def hr_catalog_doc_mime(message: Message, state: FSMContext) -> None:
    accepted, unknown = parse_allowed_formats(message.text or "")
    if unknown or not accepted:
        await message.answer(
            texts.HR_CATALOG_BAD_MIME_LIST.format(
                bad=", ".join(unknown) if unknown else "—",
                allowed=", ".join(sorted(ALLOWED_FORMATS_REGISTRY)),
            )
        )
        return
    await state.update_data(doc_mime=",".join(accepted))
    await state.set_state(HrCatalogStates.waiting_doc_size)
    await message.answer(texts.HR_CATALOG_ASK_SIZE)


@router.message(HrCatalogStates.waiting_doc_size)
async def hr_catalog_doc_size(message: Message, state: FSMContext) -> None:
    try:
        max_size = int((message.text or "").strip())
    except ValueError:
        await message.answer(texts.HR_CATALOG_BAD_SIZE_RANGE)
        return
    if max_size < 1 or max_size > 20:
        await message.answer(texts.HR_CATALOG_BAD_SIZE_RANGE)
        return

    await state.update_data(doc_max_size=max_size)
    await state.set_state(HrCatalogStates.waiting_doc_required)
    await message.answer(texts.HR_CATALOG_ASK_REQUIRED)


@router.message(HrCatalogStates.waiting_doc_required)
async def hr_catalog_doc_required(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    raw = (message.text or "").strip().lower()
    if raw in ("", "да", "д", "yes", "y"):
        is_required = True
    elif raw in ("нет", "н", "no", "n"):
        is_required = False
    else:
        await message.answer(texts.HR_CATALOG_BAD_REQUIRED)
        return

    data = await state.get_data()
    goal_id: int = data["goal_id"]
    title: str = data["doc_title"]
    code: str = data["doc_code"]
    allowed_mime: str = data["doc_mime"]
    max_size: int = int(data["doc_max_size"])

    existing = await get_requirements_for_goal(session, goal_id)
    order = len(existing)

    req = DocumentRequirement(
        goal_id=goal_id,
        code=code,
        title=title,
        allowed_mime=allowed_mime,
        max_size_mb=max_size,
        order=order,
        is_required=is_required,
    )
    session.add(req)
    await session.flush()

    await message.answer(
        texts.HR_CATALOG_ADDED.format(title=title), reply_markup=hr_main_menu()
    )
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
        await callback.answer(texts.HR_REQ_NOT_FOUND)
        return

    text = texts.HR_CATALOG_REQ_CARD.format(
        title=req.title,
        code=req.code,
        allowed_mime=req.allowed_mime,
        max_size=req.max_size_mb,
        required=texts.HR_CATALOG_YES if req.is_required else texts.HR_CATALOG_NO,
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
        await callback.message.edit_text(texts.HR_CATALOG_DELETED)
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
            texts.HR_CATALOG_CHOOSE_GOAL,
            reply_markup=builder.as_markup(),
        )
    await callback.answer()
