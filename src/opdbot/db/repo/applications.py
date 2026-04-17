from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from opdbot.db.models import Application, ApplicationStatus


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
            selectinload(Application.documents),
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


async def update_application_status(
    session: AsyncSession,
    application: Application,
    status: ApplicationStatus,
    hr_comment: str | None = None,
) -> Application:
    application.status = status
    application.updated_at = datetime.now()
    if hr_comment is not None:
        application.hr_comment = hr_comment
    await session.flush()
    return application


async def list_applications(
    session: AsyncSession,
    status: Optional[ApplicationStatus] = None,
    goal_id: Optional[int] = None,
    limit: int = 20,
    offset: int = 0,
) -> list[Application]:
    query = select(Application).options(
        selectinload(Application.user),
        selectinload(Application.goal),
    )
    if status:
        query = query.where(Application.status == status)
    if goal_id:
        query = query.where(Application.goal_id == goal_id)
    query = query.order_by(Application.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    return list(result.scalars().all())


async def set_interview_slot(
    session: AsyncSession, application: Application, interview_at: datetime
) -> Application:
    application.interview_at = interview_at
    application.status = ApplicationStatus.interview_scheduled
    application.updated_at = datetime.now()
    await session.flush()
    return application


async def set_training_slot(
    session: AsyncSession, application: Application, training_at: datetime
) -> Application:
    application.training_at = training_at
    application.status = ApplicationStatus.training_scheduled
    application.updated_at = datetime.now()
    await session.flush()
    return application
