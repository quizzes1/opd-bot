from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.bot import texts
from opdbot.bot.keyboards.hr import slot_kind_keyboard
from opdbot.bot.keyboards.main_menu import cancel_reply_keyboard, hr_main_menu
from opdbot.bot.states.hr import HrSlotStates
from opdbot.db.models import SlotKind, UserRole
from opdbot.db.repo.slots import (
    create_slot,
    deactivate_slot,
    find_overlapping_slot,
    list_slots,
)

router = Router(name="hr_slots")

SLOT_KIND_MAP = {
    "interview": SlotKind.interview,
    "medical": SlotKind.medical,
    "training": SlotKind.training,
}


@router.message(F.text == "📅 Слоты")
async def hr_slots_menu(message: Message, role: UserRole, session: AsyncSession) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    slots = await list_slots(session)
    kind_order = (SlotKind.interview, SlotKind.medical, SlotKind.training)
    by_kind: dict[SlotKind, list] = {k: [] for k in kind_order}
    for slot in slots:
        by_kind.setdefault(slot.kind, []).append(slot)

    sections: list[str] = []
    for kind in kind_order:
        label = texts.SLOT_KIND_LABELS.get(kind.value, kind.value)
        sections.append(texts.HR_SLOT_GROUP_HEADER.format(kind_label_title=label.capitalize()))
        group = by_kind.get(kind, [])
        if not group:
            sections.append(texts.HR_SLOT_GROUP_EMPTY)
            continue
        for slot in group:
            dt = slot.starts_at.strftime("%d.%m.%Y %H:%M")
            free = slot.capacity - slot.booked_count
            sections.append(
                texts.HR_SLOT_GROUP_LINE.format(
                    dt=dt, free=free, capacity=slot.capacity, slot_id=slot.id
                )
            )

    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Создать слот", callback_data="hr:slot:create")
    for slot in slots[:10]:
        builder.button(text=f"❌ Удалить #{slot.id}", callback_data=f"hr:slot:del:{slot.id}")
    builder.adjust(1)

    body = "\n".join(sections)
    text = f"{texts.HR_SLOTS_HEADER}\n{body}"
    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())


@router.callback_query(F.data == "hr:slot:create")
async def hr_slot_create_start(
    callback: CallbackQuery, state: FSMContext, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return
    await state.set_state(HrSlotStates.waiting_kind)
    if callback.message:
        await callback.message.edit_text(texts.HR_SLOT_CHOOSE_KIND, reply_markup=slot_kind_keyboard())
    await callback.answer()


@router.callback_query(HrSlotStates.waiting_kind, F.data.startswith("hr:slot_kind:"))
async def hr_slot_kind_selected(callback: CallbackQuery, state: FSMContext) -> None:
    kind_str = callback.data.split(":")[2]  # type: ignore[union-attr]
    await state.update_data(slot_kind=kind_str)
    await state.set_state(HrSlotStates.waiting_date)
    if callback.message:
        await callback.message.delete()
        await callback.message.answer(texts.HR_ASK_SLOT_DATE, reply_markup=cancel_reply_keyboard())
    await callback.answer()


@router.message(HrSlotStates.waiting_date)
async def hr_slot_date(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    try:
        dt = datetime.strptime(text, "%d.%m.%Y %H:%M")
    except ValueError:
        await message.answer(texts.HR_SLOT_BAD_DATE)
        return
    if dt <= datetime.now():
        await message.answer(texts.HR_SLOT_DATE_IN_PAST)
        return
    await state.update_data(slot_starts_at=dt.isoformat())
    await state.set_state(HrSlotStates.waiting_duration)
    await message.answer(texts.HR_ASK_SLOT_DURATION)


@router.message(HrSlotStates.waiting_duration)
async def hr_slot_duration(message: Message, state: FSMContext) -> None:
    try:
        minutes = int((message.text or "").strip())
    except ValueError:
        await message.answer(texts.HR_SLOT_BAD_DURATION)
        return
    if minutes < 1 or minutes > 480:
        await message.answer(texts.HR_SLOT_BAD_DURATION)
        return
    await state.update_data(slot_duration_minutes=minutes)
    await state.set_state(HrSlotStates.waiting_capacity)
    await message.answer(texts.HR_ASK_SLOT_CAPACITY)


@router.message(HrSlotStates.waiting_capacity)
async def hr_slot_capacity(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        capacity = int((message.text or "").strip())
    except ValueError:
        await message.answer(texts.HR_SLOT_BAD_CAPACITY_RANGE)
        return
    if capacity < 1 or capacity > 100:
        await message.answer(texts.HR_SLOT_BAD_CAPACITY_RANGE)
        return

    data = await state.get_data()
    kind_str: str = data["slot_kind"]
    starts_at = datetime.fromisoformat(data["slot_starts_at"])
    duration = int(data["slot_duration_minutes"])
    ends_at = starts_at + timedelta(minutes=duration)
    kind = SLOT_KIND_MAP[kind_str]

    overlap = await find_overlapping_slot(session, kind, starts_at, ends_at)
    if overlap is not None:
        await message.answer(
            texts.HR_SLOT_OVERLAPS.format(
                existing=(
                    f"#{overlap.id} "
                    f"{overlap.starts_at.strftime('%d.%m.%Y %H:%M')}"
                )
            )
        )
        await state.clear()
        await message.answer(texts.HR_WELCOME, reply_markup=hr_main_menu())
        return

    slot = await create_slot(session, kind=kind, starts_at=starts_at, ends_at=ends_at, capacity=capacity)
    kind_label = texts.SLOT_KIND_LABELS.get(kind_str, kind_str)
    dt_str = starts_at.strftime("%d.%m.%Y %H:%M")
    await message.answer(
        texts.HR_SLOT_CREATED.format(kind=kind_label, dt=dt_str),
        reply_markup=hr_main_menu(),
    )
    await state.clear()


@router.callback_query(F.data.startswith("hr:slot:del:"))
async def hr_slot_deactivate(
    callback: CallbackQuery, session: AsyncSession, role: UserRole
) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return

    slot_id = int(callback.data.split(":")[3])  # type: ignore[union-attr]
    await deactivate_slot(session, slot_id)
    if callback.message:
        await callback.message.edit_text(texts.HR_SLOT_DEACTIVATED.format(slot_id=slot_id))
    await callback.answer()
