from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models.operation_log import OperationLog


class OperationLogService:
    def record(
        self,
        session: Session,
        *,
        user_id: int | None,
        action: str,
        resource_type: str | None = None,
        resource_id: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> OperationLog:
        operation_log = OperationLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
        )
        session.add(operation_log)
        session.commit()
        session.refresh(operation_log)
        return operation_log


def get_operation_log_service() -> OperationLogService:
    return OperationLogService()
