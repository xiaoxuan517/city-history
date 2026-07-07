"""add gazetteer file trigram indexes

Revision ID: 20260707_0003
Revises: 20260707_0002
Create Date: 2026-07-07
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260707_0003"
down_revision: Union[str, None] = "20260707_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index(
        "ix_gazetteer_files_name_trgm",
        "gazetteer_files",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_gazetteer_files_full_path_trgm",
        "gazetteer_files",
        ["full_path"],
        postgresql_using="gin",
        postgresql_ops={"full_path": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_gazetteer_files_full_path_trgm", table_name="gazetteer_files")
    op.drop_index("ix_gazetteer_files_name_trgm", table_name="gazetteer_files")
