"""document sha256

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("sha256", sa.String(length=64), nullable=True))
    op.create_index("ix_documents_sha256", "documents", ["sha256"])

    # Test-2: allow .doc alongside .docx/.pdf for practice_direction
    op.execute(
        "UPDATE document_requirements "
        "SET allowed_mime='pdf,doc,docx' "
        "WHERE code='practice_direction'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE document_requirements "
        "SET allowed_mime='pdf,docx' "
        "WHERE code='practice_direction'"
    )
    op.drop_index("ix_documents_sha256", table_name="documents")
    op.drop_column("documents", "sha256")
