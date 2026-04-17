import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.db.models import Goal, GoalCode, User, UserRole
from opdbot.db.repo.users import get_or_create_user, get_user_by_tg_id, set_user_role


@pytest.mark.asyncio
async def test_create_user(session: AsyncSession):
    user, created = await get_or_create_user(session, tg_id=12345, tg_username="test")
    assert created is True
    assert user.tg_id == 12345
    assert user.role == UserRole.candidate


@pytest.mark.asyncio
async def test_get_existing_user(session: AsyncSession):
    await get_or_create_user(session, tg_id=99999)
    user, created = await get_or_create_user(session, tg_id=99999)
    assert created is False


@pytest.mark.asyncio
async def test_set_user_role(session: AsyncSession):
    await get_or_create_user(session, tg_id=77777)
    user = await set_user_role(session, 77777, UserRole.hr)
    assert user is not None
    assert user.role == UserRole.hr
