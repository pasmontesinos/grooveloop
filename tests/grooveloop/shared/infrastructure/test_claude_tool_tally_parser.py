from __future__ import annotations

import json

from grooveloop.shared.infrastructure.claude_tool_tally_parser import parse_tool_tallies


def _assistant(message_id: str, content: list[dict[str, object]]) -> str:
    return json.dumps({"type": "assistant", "message": {"id": message_id, "content": content}})


class TestParseToolTallies:
    def test_should_tally_the_tool_use_blocks_by_name(self) -> None:
        log = "\n".join(
            [
                _assistant("m1", [{"type": "tool_use", "name": "Bash", "input": {}}]),
                _assistant("m2", [{"type": "tool_use", "name": "Read", "input": {}}]),
                _assistant("m3", [{"type": "tool_use", "name": "Bash", "input": {}}]),
            ]
        )

        _, tools = parse_tool_tallies(log)

        assert {tool.name: tool.count for tool in tools} == {"Bash": 2, "Read": 1}

    def test_should_not_double_count_a_tool_use_block_repeated_by_id(self) -> None:
        log = "\n".join(
            [
                _assistant("m1", [{"type": "tool_use", "id": "toolu_1", "name": "Bash", "input": {}}]),
                _assistant("m1", [{"type": "tool_use", "id": "toolu_1", "name": "Bash", "input": {}}]),
            ]
        )

        _, tools = parse_tool_tallies(log)

        assert [tool.count for tool in tools if tool.name == "Bash"] == [1]

    def test_should_count_every_tool_use_block_of_a_message_with_parallel_calls(self) -> None:
        log = "\n".join(
            [
                _assistant("m1", [{"type": "tool_use", "id": "toolu_1", "name": "Read", "input": {}}]),
                _assistant("m1", [{"type": "tool_use", "id": "toolu_2", "name": "Bash", "input": {}}]),
            ]
        )

        _, tools = parse_tool_tallies(log)

        assert {tool.name: tool.count for tool in tools} == {"Read": 1, "Bash": 1}

    def test_should_collect_the_skills_invoked_in_order_of_first_use_without_repeats(self) -> None:
        log = "\n".join(
            [
                _assistant("m1", [{"type": "tool_use", "name": "Skill", "input": {"skill": "brainstorming"}}]),
                _assistant("m2", [{"type": "tool_use", "name": "Skill", "input": {"skill": "testing"}}]),
                _assistant("m3", [{"type": "tool_use", "name": "Skill", "input": {"skill": "brainstorming"}}]),
            ]
        )

        skills, _ = parse_tool_tallies(log)

        assert skills == ["brainstorming", "testing"]

    def test_should_return_no_skills_or_tools_for_a_log_without_tool_use(self) -> None:
        assert parse_tool_tallies("working\n[AGENT_EXIT] 0\n") == ([], [])

    def test_should_ignore_assistant_events_without_a_dict_message(self) -> None:
        log = json.dumps({"type": "assistant", "message": "not-a-dict"})

        assert parse_tool_tallies(log) == ([], [])
