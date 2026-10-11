from __future__ import annotations

import json
from typing import Any

from grooveloop.shared.domain.turn_growth import TurnGrowth
from grooveloop.shared.infrastructure.agent_action import describe_action
from grooveloop.shared.infrastructure.agent_exit_marker import is_exit_marker

_ASSISTANT_EVENT = "assistant"
_TOOL_USE_BLOCK = "tool_use"


def parse_turn_growth(log_text: str) -> list[TurnGrowth]:
    order: list[str] = []
    usage_by_message: dict[str, dict[str, Any]] = {}
    last_tool_by_message: dict[str, str] = {}

    for message_id, usage, tool_description in _assistant_chunks(log_text):
        if message_id not in usage_by_message:
            order.append(message_id)
        usage_by_message[message_id] = usage
        if tool_description is not None:
            last_tool_by_message[message_id] = tool_description

    growth: list[TurnGrowth] = []
    pending_action: str | None = None
    for turn, message_id in enumerate(order, start=1):
        growth.append(
            TurnGrowth(
                turn=turn,
                added_tokens=_added_tokens(usage_by_message[message_id]),
                after_action=pending_action,
            )
        )
        pending_action = last_tool_by_message.get(message_id)

    return growth


def _added_tokens(usage: dict[str, Any]) -> int:
    return _int(usage.get("input_tokens")) + _int(usage.get("cache_creation_input_tokens"))


def _int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) else 0


def _assistant_chunks(log_text: str) -> list[tuple[str, dict[str, Any], str | None]]:
    chunks: list[tuple[str, dict[str, Any], str | None]] = []
    for line in log_text.splitlines():
        if not line.strip() or is_exit_marker(line):
            continue

        event = _try_load(line)
        if event is None or event.get("type") != _ASSISTANT_EVENT:
            continue

        message = event.get("message")
        if not isinstance(message, dict):
            continue

        message_id = message.get("id")
        usage = message.get("usage")
        if not isinstance(message_id, str) or not isinstance(usage, dict):
            continue

        chunks.append((message_id, usage, _tool_description(message)))

    return chunks


def _tool_description(message: dict[str, Any]) -> str | None:
    content = message.get("content")
    if not isinstance(content, list):
        return None

    blocks = [block for block in content if isinstance(block, dict) and block.get("type") == _TOOL_USE_BLOCK]
    if len(blocks) == 0:
        return None

    block = blocks[-1]

    return describe_action(str(block.get("name", "")), block.get("input"))


def _try_load(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None

    return parsed if isinstance(parsed, dict) else None
