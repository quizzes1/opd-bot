from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.db.models import SlotKind
from opdbot.db.repo.slots import book_slot, create_slot


@pytest.mark.asyncio
async def test_book_slot_respects_capacity(session: AsyncSession):
    start = datetime(2026, 5, 1, 10, 0)
    slot = await create_slot(
        session,
        kind=SlotKind.interview,
        starts_at=start,
        ends_at=start + timedelta(minutes=30),
        capacity=2,
    )

    booked1 = await book_slot(session, slot.id)
    assert booked1 is not None and booked1.booked_count == 1
    booked2 = await book_slot(session, slot.id)
    assert booked2 is not None and booked2.booked_count == 2
    booked3 = await book_slot(session, slot.id)
    assert booked3 is None


@pytest.mark.asyncio
async def test_book_slot_ignores_inactive(session: AsyncSession):
    start = datetime(2026, 5, 2, 10, 0)
    slot = await create_slot(
        session,
        kind=SlotKind.interview,
        starts_at=start,
        ends_at=start + timedelta(minutes=30),
        capacity=1,
    )
    slot.is_active = False
    await session.flush()

    booked = await book_slot(session, slot.id)
    assert booked is None
