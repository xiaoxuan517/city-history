from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin


class OperationLog(TimestampMixin, Base):
    __tablename__ = "operation_logs"
    __table_args__ = (
        Index("ix_operation_logs_user_created", "user_id", "created_at"),
        Index("ix_operation_logs_resource", "resource_type", "resource_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
