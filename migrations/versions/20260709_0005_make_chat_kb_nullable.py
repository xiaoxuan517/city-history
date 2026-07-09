"""make chat kb nullable

Revision ID: 20260709_0005
Revises: 20260708_0004
Create Date: 2026-07-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260709_0005"
down_revision: Union[str, None] = "20260708_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("chat_sessions", "kb_id", existing_type=sa.BigInteger(), nullable=True)
    op.alter_column("chat_runs", "kb_id", existing_type=sa.BigInteger(), nullable=True)
    op.alter_column("chat_run_events", "kb_id", existing_type=sa.BigInteger(), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM chat_run_events WHERE kb_id IS NULL")
    op.execute("DELETE FROM chat_runs WHERE kb_id IS NULL")
    op.execute("DELETE FROM chat_sessions WHERE kb_id IS NULL")
    op.alter_column("chat_run_events", "kb_id", existing_type=sa.BigInteger(), nullable=False)
    op.alter_column("chat_runs", "kb_id", existing_type=sa.BigInteger(), nullable=False)
    op.alter_column("chat_sessions", "kb_id", existing_type=sa.BigInteger(), nullable=False)
