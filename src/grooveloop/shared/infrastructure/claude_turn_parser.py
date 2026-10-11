from __future__ import annotations

from typing import Any

from grooveloop.shared.infrastructure.claude_usage_parser import load_result_event


def parse_turns(log_text: str) -> tuple[int | None, int | None]:
    payload = load_result_event(log_text)
    if payload is None:
        return None, None

    return _read_turns(payload), _read_subagents(payload)


def _read_turns(payload: dict[str, Any]) -> int | None:
    turns = payload.get("num_turns")

    return int(turns) if isinstance(turns, (int, float)) else None


def _read_subagents(payload: dict[str, Any]) -> int | None:
    stats = payload.get("subagent_stats")
    if not isinstance(stats, dict):
        return None

    spawned = stats.get("spawned")

    return int(spawned) if isinstance(spawned, (int, float)) else None
