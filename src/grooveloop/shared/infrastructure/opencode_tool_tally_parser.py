from __future__ import annotations

import json
from typing import Any

from grooveloop.shared.domain.tool_tally import ToolTally
from grooveloop.shared.infrastructure.agent_exit_marker import is_exit_marker

_TOOL_USE_EVENT = "tool_use"
_SKILL_TOOL = "skill"


def parse_tool_tallies(log_text: str) -> tuple[list[str], list[ToolTally]]:
    skills: list[str] = []
    counts: dict[str, int] = {}
    order: list[str] = []
    for part in _tool_use_parts(log_text):
        tool = part.get("tool")
        if not isinstance(tool, str) or len(tool) == 0:
            continue

        if tool not in counts:
            order.append(tool)
        counts[tool] = counts.get(tool, 0) + 1

        if tool == _SKILL_TOOL:
            _collect_skill(part, skills)

    return skills, [ToolTally(name=tool, count=counts[tool]) for tool in order]


def _collect_skill(part: dict[str, Any], skills: list[str]) -> None:
    state = part.get("state")
    tool_input = state.get("input") if isinstance(state, dict) else None
    name = tool_input.get("name") if isinstance(tool_input, dict) else None
    if isinstance(name, str) and name not in skills:
        skills.append(name)


def _tool_use_parts(log_text: str) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for line in log_text.splitlines():
        if not line.strip() or is_exit_marker(line):
            continue

        event = _try_load(line)
        if event is None or event.get("type") != _TOOL_USE_EVENT:
            continue

        part = event.get("part")
        if isinstance(part, dict):
            parts.append(part)

    return parts


def _try_load(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None

    return parsed if isinstance(parsed, dict) else None
