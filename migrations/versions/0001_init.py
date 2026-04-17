"""init

Revision ID: 0001
Revises:
Create Date: 2026-04-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tg_id", sa.BigInteger, unique=True, nullable=False, index=True),
        sa.Column("tg_username", sa.String(64)),
        sa.Column("full_name", sa.String(256)),
        sa.Column("phone", sa.String(32)),
        sa.Column("role", sa.Enum("candidate", "hr", "admin", name="userrole"), nullable=False, server_default="candidate"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "goals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.Enum("employment", "practice", "internship", name="goalcode"), unique=True, nullable=False),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
    )

    op.create_table(
        "document_requirements",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("goal_id", sa.Integer, sa.ForeignKey("goals.id"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("is_required", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("allowed_mime", sa.String(256), nullable=False, server_default="pdf,jpg,jpeg,png"),
        sa.Column("max_size_mb", sa.Integer, nullable=False, server_default="10"),
        sa.Column("order", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "applications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("goal_id", sa.Integer, sa.ForeignKey("goals.id"), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft", "docs_in_progress", "docs_submitted",
                "interview_scheduled", "interview_passed",
                "training_scheduled", "approved", "rejected", "cancelled",
                name="applicationstatus",
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("interview_at", sa.DateTime),
        sa.Column("medical_at", sa.DateTime),
        sa.Column("training_at", sa.DateTime),
        sa.Column("hr_comment", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("application_id", sa.Integer, sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("requirement_id", sa.Integer, sa.ForeignKey("document_requirements.id"), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("tg_file_id", sa.String(256), nullable=False),
        sa.Column("original_name", sa.String(256)),
        sa.Column("mime", sa.String(128)),
        sa.Column("size_bytes", sa.Integer),
        sa.Column(
            "status",
            sa.Enum("uploaded", "approved", "rejected", "superseded", name="documentstatus"),
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column("reject_reason", sa.Text),
        sa.Column("uploaded_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "generated_documents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("application_id", sa.Integer, sa.ForeignKey("applications.id"), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("application_form", "medical_referral", "practice_characteristic", name="generateddocumentkind"),
            nullable=False,
        ),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("pdf_path", sa.String(512)),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "slots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("kind", sa.Enum("interview", "medical", "training", name="slotkind"), nullable=False),
        sa.Column("starts_at", sa.DateTime, nullable=False),
        sa.Column("ends_at", sa.DateTime, nullable=False),
        sa.Column("capacity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("booked_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("application_id", sa.Integer, sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("from_role", sa.Enum("hr", "candidate", name="messagefromrole"), nullable=False),
        sa.Column("text", sa.Text),
        sa.Column("requested_doc_code", sa.String(64)),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("application_id", sa.Integer, sa.ForeignKey("applications.id")),
        sa.Column("actor_tg_id", sa.BigInteger),
        sa.Column("event", sa.String(256), nullable=False),
        sa.Column("details", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # Seed initial Goals
    op.execute("""
        INSERT INTO goals (code, title, description, is_active) VALUES
        ('employment', 'Трудоустройство', 'Оформление на постоянное место работы', 1),
        ('practice', 'Практика', 'Прохождение учебной практики', 1),
        ('internship', 'Стажировка', 'Прохождение стажировки', 1)
    """)

    # Seed DocumentRequirements for employment
    op.execute("""
        INSERT INTO document_requirements (goal_id, code, title, is_required, allowed_mime, max_size_mb, "order") VALUES
        (1, 'passport', 'Паспорт (главная страница + прописка)', 1, 'pdf,jpg,jpeg,png', 10, 0),
        (1, 'snils', 'СНИЛС', 1, 'pdf,jpg,jpeg,png', 5, 1),
        (1, 'inn', 'ИНН', 1, 'pdf,jpg,jpeg,png', 5, 2),
        (1, 'workbook', 'Трудовая книжка (первая страница)', 0, 'pdf,jpg,jpeg,png', 10, 3),
        (1, 'diploma', 'Диплом об образовании', 1, 'pdf,jpg,jpeg,png', 20, 4),
        (1, 'photo', 'Фото 3x4', 1, 'jpg,jpeg,png', 5, 5)
    """)

    # Seed DocumentRequirements for practice
    op.execute("""
        INSERT INTO document_requirements (goal_id, code, title, is_required, allowed_mime, max_size_mb, "order") VALUES
        (2, 'passport', 'Паспорт (главная страница + прописка)', 1, 'pdf,jpg,jpeg,png', 10, 0),
        (2, 'snils', 'СНИЛС', 1, 'pdf,jpg,jpeg,png', 5, 1),
        (2, 'student_id', 'Студенческий билет', 1, 'pdf,jpg,jpeg,png', 5, 2),
        (2, 'practice_direction', 'Направление от учебного заведения', 1, 'pdf,docx', 10, 3),
        (2, 'photo', 'Фото 3x4', 1, 'jpg,jpeg,png', 5, 4)
    """)

    # Seed DocumentRequirements for internship
    op.execute("""
        INSERT INTO document_requirements (goal_id, code, title, is_required, allowed_mime, max_size_mb, "order") VALUES
        (3, 'passport', 'Паспорт (главная страница + прописка)', 1, 'pdf,jpg,jpeg,png', 10, 0),
        (3, 'snils', 'СНИЛС', 1, 'pdf,jpg,jpeg,png', 5, 1),
        (3, 'inn', 'ИНН', 1, 'pdf,jpg,jpeg,png', 5, 2),
        (3, 'resume', 'Резюме', 1, 'pdf,docx', 5, 3),
        (3, 'photo', 'Фото 3x4', 1, 'jpg,jpeg,png', 5, 4)
    """)


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("messages")
    op.drop_table("slots")
    op.drop_table("generated_documents")
    op.drop_table("documents")
    op.drop_table("applications")
    op.drop_table("document_requirements")
    op.drop_table("goals")
    op.drop_table("users")
