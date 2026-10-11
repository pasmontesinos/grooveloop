from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from grooveloop.shared.domain.agent_log_action import AgentLogAction

_DETAIL_KEYS = ("description", "filePath", "file_path", "pattern", "command", "skill", "name", "path")
_MAX_DETAIL = 80
_SEPARATOR = " · "
_ELLIPSIS = "…"


def describe_action(tool: str, tool_input: Any) -> str | None:
    if len(tool) == 0:
        return None

    detail = _detail(tool_input)
    if detail is None:
        return tool

    return f"{tool}{_SEPARATOR}{detail}"


def describe_last_action(log_tail: str, describe_event: Callable[[dict[str, Any]], str | None]) -> str | None:
    for line in reversed(log_tail.splitlines()):
        event = _load(line)
        described = describe_event(event) if event is not None else None
        if described is not None:
            return described

    return None


def describe_actions(
    log_text: str, actions_of_event: Callable[[dict[str, Any]], list[AgentLogAction]]
) -> list[AgentLogAction]:
    return [
        action
        for line in log_text.splitlines()
        if (event := _load(line)) is not None
        for action in actions_of_event(event)
    ]


def _load(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None

    return parsed if isinstance(parsed, dict) else None


def _detail(tool_input: Any) -> str | None:
    if not isinstance(tool_input, dict):
        return None

    for key in _DETAIL_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and len(value.strip()) > 0:
            return _shorten(value)

    return None


def _shorten(value: str) -> str:
    collapsed = " ".join(value.split())
    if len(collapsed) <= _MAX_DETAIL:
        return collapsed

    return f"{collapsed[:_MAX_DETAIL]}{_ELLIPSIS}"
