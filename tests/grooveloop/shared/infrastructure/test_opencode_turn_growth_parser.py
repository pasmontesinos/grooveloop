from __future__ import annotations

import json

from grooveloop.shared.infrastructure.opencode_turn_growth_parser import parse_turn_growth


def _step_finish(input_tokens: int, cache_write: int) -> str:
    return json.dumps(
        {
            "type": "step_finish",
            "part": {"tokens": {"input": input_tokens, "output": 10, "cache": {"read": 0, "write": cache_write}}},
        }
    )


def _tool_use(tool: str, tool_input: dict[str, object]) -> str:
    return json.dumps({"type": "tool_use", "part": {"tool": tool, "state": {"input": tool_input}}})


class TestParseTurnGrowth:
    def test_should_report_one_turn_per_step_finish_event(self) -> None:
        log = "\n".join([_step_finish(42017, 0), _step_finish(18365, 0)])

        growth = parse_turn_growth(log)

        assert [(turn.turn, turn.added_tokens) for turn in growth] == [(1, 42017), (2, 18365)]

    def test_should_mark_the_first_turn_with_no_preceding_action(self) -> None:
        growth = parse_turn_growth(_step_finish(100, 0))

        assert growth[0].after_action is None

    def test_should_attribute_a_turn_to_the_tool_use_seen_since_the_previous_step_finish(self) -> None:
        log = "\n".join(
            [
                _step_finish(100, 0),
                _tool_use("bash", {"description": "run tests"}),
                _step_finish(6000, 0),
            ]
        )

        growth = parse_turn_growth(log)

        assert growth[1].after_action == "bash · run tests"

    def test_should_add_the_cache_write_tokens_of_the_step(self) -> None:
        growth = parse_turn_growth(_step_finish(0, 320))

        assert growth[0].added_tokens == 320

    def test_should_return_no_growth_for_a_log_without_step_finish_events(self) -> None:
        assert parse_turn_growth("working\n[AGENT_EXIT] 0\n") == []
