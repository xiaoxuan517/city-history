from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

MetadataFilter = dict[str, Any]
MetadataFilterValue = str | int | float | bool

_SCALAR_TYPES = (str, int, float, bool)


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def _normalize_scalar(value: Any, *, field_name: str) -> MetadataFilterValue:
    if isinstance(value, _SCALAR_TYPES):
        return value
    raise ValueError(f"Metadata filter field {field_name!r} must be a scalar value, got: {type(value).__name__}")


def _normalize_sequence(value: Sequence[Any], *, field_name: str) -> list[MetadataFilterValue]:
    normalized = [_normalize_scalar(item, field_name=field_name) for item in value if not _is_empty(item)]
    if not normalized:
        raise ValueError(f"Metadata filter field {field_name!r} must not be an empty list")
    return normalized


def normalize_metadata_filter(metadata_filter: Mapping[str, Any] | None) -> MetadataFilter | None:
    """Normalize simple metadata filters for retrieval adapters.

    Supported input forms:
    - {"source": "file.txt"} for equality match
    - {"source": ["a.txt", "b.txt"]} for $in match
    - {"page": {"$eq": 1}} for explicit operators
    """
    if not metadata_filter:
        return None

    normalized: MetadataFilter = {}
    for raw_key, raw_value in metadata_filter.items():
        key = str(raw_key).strip()
        if not key or _is_empty(raw_value):
            continue

        if isinstance(raw_value, Mapping):
            normalized[key] = dict(raw_value)
            continue

        if isinstance(raw_value, Sequence) and not isinstance(raw_value, (str, bytes, bytearray)):
            values = _normalize_sequence(raw_value, field_name=key)
            normalized[key] = values[0] if len(values) == 1 else {"$in": values}
            continue

        normalized[key] = _normalize_scalar(raw_value, field_name=key)

    return normalized or None


def parse_metadata_filter_json(raw_value: str | None) -> MetadataFilter | None:
    if not raw_value:
        return None

    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid metadata filter JSON: {raw_value}") from exc

    if not isinstance(payload, Mapping):
        raise ValueError("Metadata filter JSON must be an object.")

    return normalize_metadata_filter(payload)


def merge_metadata_filters(*filters: Mapping[str, Any] | None) -> MetadataFilter | None:
    merged: MetadataFilter = {}
    for metadata_filter in filters:
        normalized = normalize_metadata_filter(metadata_filter)
        if normalized:
            merged.update(normalized)
    return merged or None
