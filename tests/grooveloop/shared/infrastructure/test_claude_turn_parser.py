from __future__ import annotations

import json

from grooveloop.shared.infrastructure.claude_turn_parser import parse_turns

_RESULT = json.dumps(
    {
        "type": "result",
        "total_cost_usd": 0.42,
        "num_turns": 5,
        "subagent_stats": {"spawned": 2},
    }
)


class TestParseTurns:
    def test_should_read_the_turns_and_subagents_of_the_result_event(self) -> None:
        turns, subagents = parse_turns(f"{_RESULT}\n[AGENT_EXIT] 0\n")

        assert turns == 5
        assert subagents == 2

    def test_should_read_no_turns_or_subagents_when_the_log_has_no_result_event(self) -> None:
        assert parse_turns("working\n") == (None, None)

    def test_should_read_no_subagents_when_the_result_event_has_no_subagent_stats(self) -> None:
        result = json.dumps({"type": "result", "num_turns": 3})

        assert parse_turns(f"{result}\n") == (3, None)
