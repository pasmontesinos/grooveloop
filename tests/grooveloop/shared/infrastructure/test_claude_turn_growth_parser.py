from __future__ import annotations

import json

from grooveloop.shared.infrastructure.claude_turn_growth_parser import parse_turn_growth


def _chunk(message_id: str, input_tokens: int, cache_creation: int, block: dict[str, object]) -> str:
    return json.dumps(
        {
            "type": "assistant",
            "message": {
                "id": message_id,
                "usage": {
                    "input_tokens": input_tokens,
                    "cache_creation_input_tokens": cache_creation,
                    "cache_read_input_tokens": 0,
                    "output_tokens": 2,
                },
                "content": [block],
            },
        }
    )


class TestParseTurnGrowth:
    def test_should_dedupe_streaming_chunks_of_the_same_turn_by_message_id(self) -> None:
        log = "\n".join(
            [
                _chunk("m1", 2, 44541, {"type": "thinking", "thinking": "…"}),
                _chunk("m1", 2, 44541, {"type": "tool_use", "name": "Bash", "input": {"description": "seed"}}),
                _chunk("m2", 2, 3122, {"type": "text", "text": "ok"}),
            ]
        )

        growth = parse_turn_growth(log)

        assert [(turn.turn, turn.added_tokens) for turn in growth] == [(1, 44543), (2, 3124)]

    def test_should_mark_the_first_turn_with_no_preceding_action(self) -> None:
        log = _chunk("m1", 2, 100, {"type": "text", "text": "ok"})

        growth = parse_turn_growth(log)

        assert growth[0].after_action is None

    def test_should_attribute_a_turn_to_the_last_tool_use_of_the_previous_turn(self) -> None:
        log = "\n".join(
            [
                _chunk("m1", 2, 100, {"type": "tool_use", "name": "Read", "input": {"file_path": "a.py"}}),
                _chunk("m1", 2, 100, {"type": "tool_use", "name": "Bash", "input": {"description": "run tests"}}),
                _chunk("m2", 2, 6000, {"type": "text", "text": "ok"}),
            ]
        )

        growth = parse_turn_growth(log)

        assert growth[1].after_action == "Bash · run tests"

    def test_should_return_no_growth_for_a_log_without_assistant_events(self) -> None:
        assert parse_turn_growth("working\n[AGENT_EXIT] 0\n") == []
