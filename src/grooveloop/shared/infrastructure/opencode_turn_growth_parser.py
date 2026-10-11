from __future__ import annotations

import json
from typing import Any

from grooveloop.shared.domain.turn_growth import TurnGrowth
from grooveloop.shared.infrastructure.agent_action import describe_action
from grooveloop.shared.infrastructure.agent_exit_marker import is_exit_marker
from grooveloop.shared.infrastructure.opencode_json_numbers import parse_int

_STEP_FINISH_EVENT = "step_finish"
_TOOL_USE_EVENT = "tool_use"


def parse_turn_growth(log_text: str) -> list[TurnGrowth]:
    growth: list[TurnGrowth] = []
    pending_action: str | None = None
    turn = 0

    for event in _events(log_text):
        event_type = event.get("type")
        if event_type == _TOOL_USE_EVENT:
            description = _tool_description(event)
            if description is not None:
                pending_action = description
        elif event_type == _STEP_FINISH_EVENT:
            turn += 1
            growth.append(TurnGrowth(turn=turn, added_tokens=_added_tokens(event), after_action=pending_action))
            pending_action = None

    return growth


def _added_tokens(event: dict[str, Any]) -> int:
    part = event.get("part")
    tokens = part.get("tokens") if isinstance(part, dict) else None
    if not isinstance(tokens, dict):
        return 0

    cache = tokens.get("cache")
    cache_write = cache.get("write") if isinstance(cache, dict) else None

    return parse_int(tokens.get("input")) + parse_int(cache_write)


def _tool_description(event: dict[str, Any]) -> str | None:
    part = event.get("part")
    if not isinstance(part, dict):
        return None

    state = part.get("state")

    return describe_action(str(part.get("tool", "")), state.get("input") if isinstance(state, dict) else None)


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
