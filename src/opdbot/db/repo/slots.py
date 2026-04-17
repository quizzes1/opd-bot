from datetime import datetime

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.db.models import Slot, SlotKind


async def get_available_slots(
    session: AsyncSession, kind: SlotKind, from_dt: datetime | None = None
) -> list[Slot]:
    query = select(Slot).where(
        and_(
            Slot.kind == kind,
            Slot.is_active.is_(True),
            Slot.booked_count < Slot.capacity,
        )
    )
    if from_dt:
        query = query.where(Slot.starts_at >= from_dt)
    query = query.order_by(Slot.starts_at)
    result = await session.execute(query)
    return list(result.scalars().all())


async def book_slot(session: AsyncSession, slot_id: int) -> Slot | None:
    """Atomic booking: conditional UPDATE prevents overbooking under race."""
    result = await session.execute(
        update(Slot)
        .where(
            Slot.id == slot_id,
            Slot.booked_count < Slot.capacity,
            Slot.is_active.is_(True),
        )
        .values(booked_count=Slot.booked_count + 1)
    )
    if result.rowcount == 0:
        return None
    fetched = await session.execute(select(Slot).where(Slot.id == slot_id))
    return fetched.scalar_one_or_none()


async def create_slot(
    session: AsyncSession,
    kind: SlotKind,
    starts_at: datetime,
    ends_at: datetime,
    capacity: int = 1,
) -> Slot:
    slot = Slot(kind=kind, starts_at=starts_at, ends_at=ends_at, capacity=capacity)
    session.add(slot)
    await session.flush()
    return slot


async def deactivate_slot(session: AsyncSession, slot_id: int) -> Slot | None:
    result = await session.execute(select(Slot).where(Slot.id == slot_id))
    slot = result.scalar_one_or_none()
    if slot:
        slot.is_active = False
        await session.flush()
    return slot


async def list_slots(session: AsyncSession, kind: SlotKind | None = None) -> list[Slot]:
    query = select(Slot).where(Slot.is_active.is_(True)).order_by(Slot.starts_at)
    if kind:
        query = query.where(Slot.kind == kind)
    result = await session.execute(query)
    return list(result.scalars().all())
