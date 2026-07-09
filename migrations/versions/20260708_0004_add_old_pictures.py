"""add old pictures

Revision ID: 20260708_0004
Revises: 20260707_0003
Create Date: 2026-07-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260708_0004"
down_revision: Union[str, None] = "20260707_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "old_pictures",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("full_path", sa.String(length=2048), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("modified", sa.String(length=64), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_old_pictures_name", "old_pictures", ["name"])
    op.create_index("ix_old_pictures_full_path", "old_pictures", ["full_path"], unique=True)
    op.create_index("ix_old_pictures_name_full_path", "old_pictures", ["name", "full_path"])
    op.create_index(
        "ix_old_pictures_name_trgm",
        "old_pictures",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_old_pictures_full_path_trgm",
        "old_pictures",
        ["full_path"],
        postgresql_using="gin",
        postgresql_ops={"full_path": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_old_pictures_full_path_trgm", table_name="old_pictures")
    op.drop_index("ix_old_pictures_name_trgm", table_name="old_pictures")
    op.drop_index("ix_old_pictures_name_full_path", table_name="old_pictures")
    op.drop_index("ix_old_pictures_full_path", table_name="old_pictures")
    op.drop_index("ix_old_pictures_name", table_name="old_pictures")
    op.drop_table("old_pictures")
