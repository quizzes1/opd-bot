from datetime import datetime
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from opdbot.db.models import (
    ACTIVE_STATUSES,
    Application,
    ApplicationStatus,
    User,
)


async def create_application(session: AsyncSession, user_id: int, goal_id: int) -> Application:
    app = Application(user_id=user_id, goal_id=goal_id, status=ApplicationStatus.draft)
    session.add(app)
    await session.flush()
    return app


async def get_application(session: AsyncSession, application_id: int) -> Application | None:
    result = await session.execute(
        select(Application)
        .options(
            selectinload(Application.user),
            selectinload(Application.goal),
            selectinload(Application.generated_documents),
        )
        .where(Application.id == application_id)
    )
    return result.scalar_one_or_none()


async def get_user_applications(session: AsyncSession, user_id: int) -> list[Application]:
    result = await session.execute(
        select(Application)
        .options(selectinload(Application.goal))
        .where(Application.user_id == user_id)
        .order_by(Application.created_at.desc())
    )
    return list(result.scalars().all())


async def get_active_application(
    session: AsyncSession, user_id: int
) -> Application | None:
    result = await session.execute(
        select(Application)
        .options(selectinload(Application.goal))
        .where(
            Application.user_id == user_id,
            Application.status.in_(ACTIVE_STATUSES),
        )
        .order_by(Application.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def update_application_status(
    session: AsyncSession,
    application: Application,
    status: ApplicationStatus,
    hr_comment: str | None = None,
) -> Application:
    application.status = status
    if hr_comment is not None:
        application.hr_comment = hr_comment
    await session.flush()
    return application


async def list_applications(
    session: AsyncSession,
    status: Optional[ApplicationStatus] = None,
    statuses: Optional[list[ApplicationStatus]] = None,
    exclude_statuses: Optional[list[ApplicationStatus]] = None,
    goal_id: Optional[int] = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Application], int]:
    from sqlalchemy import func as sa_func

    base = select(Application)
    count_q = select(sa_func.count(Application.id))
    if status:
        base = base.where(Application.status == status)
        count_q = count_q.where(Application.status == status)
    if statuses:
        base = base.where(Application.status.in_(statuses))
        count_q = count_q.where(Application.status.in_(statuses))
    if exclude_statuses:
        base = base.where(Application.status.not_in(exclude_statuses))
        count_q = count_q.where(Application.status.not_in(exclude_statuses))
    if goal_id:
        base = base.where(Application.goal_id == goal_id)
        count_q = count_q.where(Application.goal_id == goal_id)

    base = (
        base.options(
            selectinload(Application.user),
            selectinload(Application.goal),
        )
        .order_by(Application.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = await session.execute(base)
    total = (await session.execute(count_q)).scalar_one()
    return list(rows.scalars().all()), int(total)


async def search_applications(
    session: AsyncSession, query: str, limit: int = 20
) -> list[Application]:
    pattern = f"%{query.strip()}%"
    stmt = (
        select(Application)
        .join(User, Application.user_id == User.id)
        .options(
            selectinload(Application.user),
            selectinload(Application.goal),
        )
        .where(
            or_(
                User.full_name.ilike(pattern),
                User.tg_username.ilike(pattern),
                User.phone.ilike(pattern),
            )
        )
        .order_by(Application.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def set_interview_slot(
    session: AsyncSession, application: Application, interview_at: datetime
) -> Application:
    application.interview_at = interview_at
    application.status = ApplicationStatus.interview_scheduled
    await session.flush()
    return application


async def set_training_slot(
    session: AsyncSession, application: Application, training_at: datetime
) -> Application:
    application.training_at = training_at
    application.status = ApplicationStatus.training_scheduled
    await session.flush()
    return application


async def set_medical_date(
    session: AsyncSession, application: Application, medical_at: datetime
) -> Application:
    application.medical_at = medical_at
    await session.flush()
    return application
