import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from opdbot.db.base import Base


class UserRole(str, enum.Enum):
    candidate = "candidate"
    hr = "hr"
    admin = "admin"


class GoalCode(str, enum.Enum):
    employment = "employment"
    practice = "practice"
    internship = "internship"


class ApplicationStatus(str, enum.Enum):
    draft = "draft"
    docs_in_progress = "docs_in_progress"
    docs_submitted = "docs_submitted"
    interview_scheduled = "interview_scheduled"
    interview_passed = "interview_passed"
    training_scheduled = "training_scheduled"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


ACTIVE_STATUSES = (
    ApplicationStatus.draft,
    ApplicationStatus.docs_in_progress,
    ApplicationStatus.docs_submitted,
    ApplicationStatus.interview_scheduled,
    ApplicationStatus.interview_passed,
    ApplicationStatus.training_scheduled,
)

TERMINAL_STATUSES = (
    ApplicationStatus.approved,
    ApplicationStatus.rejected,
    ApplicationStatus.cancelled,
)


class DocumentStatus(str, enum.Enum):
    uploaded = "uploaded"
    approved = "approved"
    rejected = "rejected"
    superseded = "superseded"


class GeneratedDocumentKind(str, enum.Enum):
    application_form = "application_form"
    medical_referral = "medical_referral"
    practice_characteristic = "practice_characteristic"


class SlotKind(str, enum.Enum):
    interview = "interview"
    medical = "medical"
    training = "training"


class MessageFromRole(str, enum.Enum):
    hr = "hr"
    candidate = "candidate"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    tg_username: Mapped[Optional[str]] = mapped_column(String(64))
    full_name: Mapped[Optional[str]] = mapped_column(String(256))
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=16),
        default=UserRole.candidate,
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    applications: Mapped[list["Application"]] = relationship(back_populates="user")


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[GoalCode] = mapped_column(
        Enum(GoalCode, native_enum=False, length=16), unique=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    requirements: Mapped[list["DocumentRequirement"]] = relationship(back_populates="goal")
    applications: Mapped[list["Application"]] = relationship(back_populates="goal")


class DocumentRequirement(Base):
    __tablename__ = "document_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    goal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("goals.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allowed_mime: Mapped[str] = mapped_column(
        String(256), default="pdf,jpg,jpeg,png", nullable=False
    )
    max_size_mb: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    goal: Mapped["Goal"] = relationship(back_populates="requirements")
    documents: Mapped[list["Document"]] = relationship(back_populates="requirement")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    goal_id: Mapped[int] = mapped_column(Integer, ForeignKey("goals.id"), nullable=False)
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, native_enum=False, length=32),
        default=ApplicationStatus.draft,
        nullable=False,
        index=True,
    )
    interview_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    medical_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    training_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    hr_comment: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="applications")
    goal: Mapped["Goal"] = relationship(back_populates="applications")
    documents: Mapped[list["Document"]] = relationship(back_populates="application")
    generated_documents: Mapped[list["GeneratedDocument"]] = relationship(back_populates="application")
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="application")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="application")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("applications.id"), nullable=False, index=True
    )
    requirement_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("document_requirements.id"), nullable=False
    )
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    tg_file_id: Mapped[str] = mapped_column(String(256), nullable=False)
    original_name: Mapped[Optional[str]] = mapped_column(String(256))
    mime: Mapped[Optional[str]] = mapped_column(String(128))
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    sha256: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, native_enum=False, length=16),
        default=DocumentStatus.uploaded,
        nullable=False,
        index=True,
    )
    reject_reason: Mapped[Optional[str]] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    application: Mapped["Application"] = relationship(back_populates="documents")
    requirement: Mapped["DocumentRequirement"] = relationship(back_populates="documents")


class GeneratedDocument(Base):
    __tablename__ = "generated_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("applications.id"), nullable=False, index=True
    )
    kind: Mapped[GeneratedDocumentKind] = mapped_column(
        Enum(GeneratedDocumentKind, native_enum=False, length=32), nullable=False
    )
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    application: Mapped["Application"] = relationship(back_populates="generated_documents")


class Slot(Base):
    __tablename__ = "slots"
    __table_args__ = (
        Index("ix_slots_kind_starts_at", "kind", "starts_at"),
        Index("ix_slots_kind_active", "kind", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[SlotKind] = mapped_column(
        Enum(SlotKind, native_enum=False, length=16), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    booked_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ChatMessage(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("applications.id"), nullable=False, index=True
    )
    from_role: Mapped[MessageFromRole] = mapped_column(
        Enum(MessageFromRole, native_enum=False, length=16), nullable=False
    )
    text: Mapped[Optional[str]] = mapped_column(Text)
    requested_doc_code: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    application: Mapped["Application"] = relationship(back_populates="messages")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("applications.id"), index=True
    )
    actor_tg_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)
    event: Mapped[str] = mapped_column(String(256), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    application: Mapped[Optional["Application"]] = relationship(back_populates="audit_logs")
