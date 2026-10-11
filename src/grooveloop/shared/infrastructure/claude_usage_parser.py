from __future__ import annotations

import json
from typing import Any

from grooveloop.shared.domain.model_usage import ModelUsage
from grooveloop.shared.infrastructure.agent_exit_marker import is_exit_marker

_RESULT_EVENT = "result"


def parse_usage(log_text: str) -> tuple[float | None, list[ModelUsage]]:
    payload = load_result_event(log_text)
    if payload is None:
        return None, []

    return _read_cost(payload), _read_models(payload)


def load_result_event(log_text: str) -> dict[str, Any] | None:
    for line in reversed(log_text.splitlines()):
        if not line.strip() or is_exit_marker(line):
            continue

        event = _try_load(line)
        if event is not None and event.get("type") == _RESULT_EVENT:
            return event

    return None


def _try_load(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None

    return parsed if isinstance(parsed, dict) else None


def _read_cost(payload: dict[str, Any]) -> float | None:
    cost = _first(payload, "total_cost_usd", "totalCostUsd")

    return float(cost) if isinstance(cost, (int, float)) else None


def _read_models(payload: dict[str, Any]) -> list[ModelUsage]:
    model_usage = _first(payload, "modelUsage", "model_usage")
    if not isinstance(model_usage, dict):
        return []

    return [_to_model_usage(model, entry) for model, entry in model_usage.items() if isinstance(entry, dict)]


def _to_model_usage(model: str, entry: dict[str, Any]) -> ModelUsage:
    return ModelUsage(
        model=model,
        input_tokens=_int(entry, "inputTokens", "input_tokens"),
        output_tokens=_int(entry, "outputTokens", "output_tokens"),
        cache_read_tokens=_int(entry, "cacheReadInputTokens", "cache_read_input_tokens"),
        cache_creation_tokens=_int(entry, "cacheCreationInputTokens", "cache_creation_input_tokens"),
        cost_usd=_float(entry, "costUSD", "cost_usd"),
    )


def _first(source: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in source:
            return source[key]

    return None


def _int(source: dict[str, Any], *keys: str) -> int:
    value = _first(source, *keys)

    return int(value) if isinstance(value, (int, float)) else 0


def _float(source: dict[str, Any], *keys: str) -> float:
    value = _first(source, *keys)

    return float(value) if isinstance(value, (int, float)) else 0.0
