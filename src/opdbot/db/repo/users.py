from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.db.models import User, UserRole


async def get_user_by_tg_id(session: AsyncSession, tg_id: int) -> User | None:
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    return result.scalar_one_or_none()


async def get_or_create_user(
    session: AsyncSession,
    tg_id: int,
    tg_username: str | None = None,
    full_name: str | None = None,
) -> tuple[User, bool]:
    user = await get_user_by_tg_id(session, tg_id)
    if user:
        return user, False
    user = User(tg_id=tg_id, tg_username=tg_username, full_name=full_name)
    session.add(user)
    await session.flush()
    return user, True


async def update_user(session: AsyncSession, user: User, **kwargs: object) -> User:
    for key, value in kwargs.items():
        setattr(user, key, value)
    await session.flush()
    return user


async def get_all_staff(session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(User).where(
            User.role.in_((UserRole.hr, UserRole.admin)),
            User.is_active.is_(True),
        )
    )
    return list(result.scalars().all())


async def set_user_role(session: AsyncSession, tg_id: int, role: UserRole) -> User | None:
    user = await get_user_by_tg_id(session, tg_id)
    if user and user.role != role:
        user.role = role
        await session.flush()
    return user
