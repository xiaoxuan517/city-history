"""add gazetteer files

Revision ID: 20260707_0002
Revises: 20260617_0001
Create Date: 2026-07-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260707_0002"
down_revision: Union[str, None] = "20260617_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gazetteer_files",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("full_path", sa.String(length=2048), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("modified", sa.String(length=64), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gazetteer_files_name", "gazetteer_files", ["name"])
    op.create_index("ix_gazetteer_files_full_path", "gazetteer_files", ["full_path"], unique=True)
    op.create_index("ix_gazetteer_files_name_full_path", "gazetteer_files", ["name", "full_path"])


def downgrade() -> None:
    op.drop_index("ix_gazetteer_files_name_full_path", table_name="gazetteer_files")
    op.drop_index("ix_gazetteer_files_full_path", table_name="gazetteer_files")
    op.drop_index("ix_gazetteer_files_name", table_name="gazetteer_files")
    op.drop_table("gazetteer_files")
