from __future__ import annotations

import json
from typing import Any

from grooveloop.shared.infrastructure.agent_exit_marker import is_exit_marker

_STEP_FINISH_EVENT = "step_finish"
_TOOL_USE_EVENT = "tool_use"
_TASK_TOOL = "task"


def parse_turns(log_text: str) -> tuple[int, int]:
    turns = 0
    subagents = 0
    for event in _events(log_text):
        event_type = event.get("type")
        if event_type == _STEP_FINISH_EVENT:
            turns += 1
        elif event_type == _TOOL_USE_EVENT and _tool(event) == _TASK_TOOL:
            subagents += 1

    return turns, subagents


def _tool(event: dict[str, Any]) -> str | None:
    part = event.get("part")

    return part.get("tool") if isinstance(part, dict) else None


def _events(log_text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in log_text.splitlines():
        if not line.strip() or is_exit_marker(line):
            continue

        event = _try_load(line)
        if event is not None:
            events.append(event)

    return events


def _try_load(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None

    return parsed if isinstance(parsed, dict) else None
