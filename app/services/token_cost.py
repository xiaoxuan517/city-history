from __future__ import annotations

from typing import Any

from app.config.settings import settings


def calculate_token_cost(
    usage: dict[str, Any] | None,
    *,
    input_cost_per_1k: float = settings.token_input_cost_per_1k,
    output_cost_per_1k: float = settings.token_output_cost_per_1k,
) -> dict[str, Any]:
    input_tokens = _int_value(usage, "input_tokens")
    output_tokens = _int_value(usage, "output_tokens")
    input_cost = input_tokens / 1000 * input_cost_per_1k
    output_cost = output_tokens / 1000 * output_cost_per_1k
    total_cost = input_cost + output_cost
    return {
        "currency": "USD",
        "input_cost": round(input_cost, 8),
        "output_cost": round(output_cost, 8),
        "total_cost": round(total_cost, 8),
        "input_cost_per_1k": input_cost_per_1k,
        "output_cost_per_1k": output_cost_per_1k,
    }


def _int_value(usage: dict[str, Any] | None, key: str) -> int:
    if not usage:
        return 0
    value = usage.get(key, 0)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
