from __future__ import annotations

import json
from typing import Any

from grooveloop.shared.infrastructure.opencode_turn_parser import parse_turns


def _event(event_type: str, tool: str | None = None) -> str:
    payload: dict[str, Any] = {"type": event_type}
    if tool is not None:
        payload["part"] = {"type": "tool", "tool": tool}

    return json.dumps(payload)


class TestParseTurns:
    def test_should_count_the_step_finish_events_as_turns(self) -> None:
        log = "\n".join([_event("step_start"), _event("step_finish"), _event("text"), _event("step_finish")])

        turns, _ = parse_turns(log)

        assert turns == 2

    def test_should_count_the_task_tool_use_events_as_subagents(self) -> None:
        log = "\n".join(
            [_event("tool_use", tool="bash"), _event("tool_use", tool="task"), _event("tool_use", tool="task")]
        )

        _, subagents = parse_turns(log)

        assert subagents == 2

    def test_should_read_zero_turns_and_subagents_for_a_log_without_those_events(self) -> None:
        assert parse_turns("working\n[AGENT_EXIT] 0\n") == (0, 0)

    def test_should_ignore_the_exit_marker_line(self) -> None:
        assert parse_turns(f"{_event('step_finish')}\n[AGENT_EXIT] 0\n") == (1, 0)
