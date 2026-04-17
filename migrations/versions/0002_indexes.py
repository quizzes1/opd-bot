"""indexes

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-17

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_applications_user_id", "applications", ["user_id"])
    op.create_index("ix_applications_status", "applications", ["status"])
    op.create_index("ix_documents_application_id", "documents", ["application_id"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_document_requirements_goal_id", "document_requirements", ["goal_id"])
    op.create_index("ix_generated_documents_application_id", "generated_documents", ["application_id"])
    op.create_index("ix_messages_application_id", "messages", ["application_id"])
    op.create_index("ix_audit_logs_application_id", "audit_logs", ["application_id"])
    op.create_index("ix_audit_logs_actor_tg_id", "audit_logs", ["actor_tg_id"])
    op.create_index("ix_slots_kind_starts_at", "slots", ["kind", "starts_at"])
    op.create_index("ix_slots_kind_active", "slots", ["kind", "is_active"])


def downgrade() -> None:
    op.drop_index("ix_slots_kind_active", table_name="slots")
    op.drop_index("ix_slots_kind_starts_at", table_name="slots")
    op.drop_index("ix_audit_logs_actor_tg_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_application_id", table_name="audit_logs")
    op.drop_index("ix_messages_application_id", table_name="messages")
    op.drop_index("ix_generated_documents_application_id", table_name="generated_documents")
    op.drop_index("ix_document_requirements_goal_id", table_name="document_requirements")
    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_index("ix_documents_application_id", table_name="documents")
    op.drop_index("ix_applications_status", table_name="applications")
    op.drop_index("ix_applications_user_id", table_name="applications")
    op.drop_index("ix_users_role", table_name="users")
