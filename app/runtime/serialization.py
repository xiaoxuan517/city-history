from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


def serialize(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, BaseModel):
        return serialize(value.model_dump())
    if is_dataclass(value) and not isinstance(value, type):
        return serialize(asdict(value))
    if isinstance(value, dict):
        return {str(key): serialize(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [serialize(item) for item in value]
    return str(value)
