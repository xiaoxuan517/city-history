from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin


class GazetteerFile(TimestampMixin, Base):
    __tablename__ = "gazetteer_files"
    __table_args__ = (
        Index("ix_gazetteer_files_name", "name"),
        Index("ix_gazetteer_files_full_path", "full_path", unique=True),
        Index("ix_gazetteer_files_name_full_path", "name", "full_path"),
        Index("ix_gazetteer_files_name_trgm", "name", postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}),
        Index(
            "ix_gazetteer_files_full_path_trgm",
            "full_path",
            postgresql_using="gin",
            postgresql_ops={"full_path": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    full_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    modified: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
