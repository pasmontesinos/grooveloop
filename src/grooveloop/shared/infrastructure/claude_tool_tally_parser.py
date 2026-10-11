from __future__ import annotations

import json
from typing import Any

from grooveloop.shared.domain.tool_tally import ToolTally
from grooveloop.shared.infrastructure.agent_exit_marker import is_exit_marker

_ASSISTANT_EVENT = "assistant"
_TOOL_USE_BLOCK = "tool_use"
_SKILL_TOOL = "Skill"


def parse_tool_tallies(log_text: str) -> tuple[list[str], list[ToolTally]]:
    skills: list[str] = []
    counts: dict[str, int] = {}
    order: list[str] = []
    seen_tool_use_ids: set[str] = set()
    for block in _tool_use_blocks_in_log(log_text):
        tool_use_id = block.get("id")
        if isinstance(tool_use_id, str):
            if tool_use_id in seen_tool_use_ids:
                continue
            seen_tool_use_ids.add(tool_use_id)

        name = str(block.get("name", ""))
        if len(name) == 0:
            continue

        if name not in counts:
            order.append(name)
        counts[name] = counts.get(name, 0) + 1

        if name == _SKILL_TOOL:
            _collect_skill(block, skills)

    return skills, [ToolTally(name=name, count=counts[name]) for name in order]


def _collect_skill(block: dict[str, Any], skills: list[str]) -> None:
    tool_input = block.get("input")
    skill = tool_input.get("skill") if isinstance(tool_input, dict) else None
    if isinstance(skill, str) and skill not in skills:
        skills.append(skill)


def _tool_use_blocks_in_log(log_text: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for line in log_text.splitlines():
        if not line.strip() or is_exit_marker(line):
            continue

        event = _try_load(line)
        if event is None or event.get("type") != _ASSISTANT_EVENT:
            continue

        message = event.get("message")
        if not isinstance(message, dict):
            continue

        blocks.extend(_tool_use_blocks(message))

    return blocks


def _tool_use_blocks(message: dict[str, Any]) -> list[dict[str, Any]]:
    content = message.get("content")
    if not isinstance(content, list):
        return []

    return [block for block in content if isinstance(block, dict) and block.get("type") == _TOOL_USE_BLOCK]


def _try_load(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None

    return parsed if isinstance(parsed, dict) else None
