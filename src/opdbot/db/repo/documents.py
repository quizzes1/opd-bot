from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from opdbot.db.models import Document, DocumentRequirement, DocumentStatus


async def get_requirements_for_goal(
    session: AsyncSession, goal_id: int
) -> list[DocumentRequirement]:
    result = await session.execute(
        select(DocumentRequirement)
        .where(DocumentRequirement.goal_id == goal_id)
        .order_by(DocumentRequirement.order, DocumentRequirement.id)
    )
    return list(result.scalars().all())


async def save_document(
    session: AsyncSession,
    application_id: int,
    requirement_id: int,
    file_path: str,
    tg_file_id: str,
    original_name: str | None = None,
    mime: str | None = None,
    size_bytes: int | None = None,
    sha256: str | None = None,
) -> Document:
    # Supersede previous documents for this requirement
    prev_result = await session.execute(
        select(Document).where(
            Document.application_id == application_id,
            Document.requirement_id == requirement_id,
            Document.status == DocumentStatus.uploaded,
        )
    )
    for prev in prev_result.scalars().all():
        prev.status = DocumentStatus.superseded

    doc = Document(
        application_id=application_id,
        requirement_id=requirement_id,
        file_path=file_path,
        tg_file_id=tg_file_id,
        original_name=original_name,
        mime=mime,
        size_bytes=size_bytes,
        sha256=sha256,
        status=DocumentStatus.uploaded,
    )
    session.add(doc)
    await session.flush()
    return doc


async def find_duplicate_by_sha(
    session: AsyncSession, application_id: int, requirement_id: int, sha256: str
) -> Document | None:
    result = await session.execute(
        select(Document).where(
            Document.application_id == application_id,
            Document.requirement_id == requirement_id,
            Document.sha256 == sha256,
            Document.status != DocumentStatus.superseded,
        )
    )
    return result.scalars().first()


async def get_documents_for_application(
    session: AsyncSession, application_id: int
) -> list[Document]:
    result = await session.execute(
        select(Document)
        .options(selectinload(Document.requirement))
        .where(
            Document.application_id == application_id,
            Document.status != DocumentStatus.superseded,
        )
        .order_by(Document.uploaded_at)
    )
    return list(result.scalars().all())


async def update_document_status(
    session: AsyncSession,
    document: Document,
    status: DocumentStatus,
    reject_reason: str | None = None,
) -> Document:
    document.status = status
    if reject_reason is not None:
        document.reject_reason = reject_reason
    await session.flush()
    return document


async def get_uploaded_requirement_ids(
    session: AsyncSession, application_id: int
) -> set[int]:
    result = await session.execute(
        select(Document.requirement_id).where(
            Document.application_id == application_id,
            Document.status.in_([DocumentStatus.uploaded, DocumentStatus.approved]),
        )
    )
    return set(result.scalars().all())
