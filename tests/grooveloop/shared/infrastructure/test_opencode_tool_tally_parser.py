from __future__ import annotations

import json
from typing import Any

from grooveloop.shared.domain.tool_tally import ToolTally
from grooveloop.shared.infrastructure.opencode_tool_tally_parser import parse_tool_tallies


def _tool_use(tool: str, tool_input: dict[str, Any] | None = None) -> str:
    return json.dumps(
        {"type": "tool_use", "part": {"type": "tool", "tool": tool, "state": {"input": tool_input or {}}}}
    )


class TestParseToolTallies:
    def test_should_tally_the_tool_use_events_by_tool_name(self) -> None:
        log = "\n".join([_tool_use("bash"), _tool_use("read"), _tool_use("bash")])

        _, tools = parse_tool_tallies(log)

        assert {tool.name: tool.count for tool in tools} == {"bash": 2, "read": 1}

    def test_should_collect_the_skills_invoked_in_order_of_first_use_without_repeats(self) -> None:
        log = "\n".join(
            [
                _tool_use("skill", {"name": "writing-plans"}),
                _tool_use("skill", {"name": "testing"}),
                _tool_use("skill", {"name": "writing-plans"}),
            ]
        )

        skills, _ = parse_tool_tallies(log)

        assert skills == ["writing-plans", "testing"]

    def test_should_include_the_skill_and_task_tools_in_the_general_tally(self) -> None:
        log = "\n".join([_tool_use("skill", {"name": "writing-plans"}), _tool_use("task", {})])

        _, tools = parse_tool_tallies(log)

        assert tools == [ToolTally(name="skill", count=1), ToolTally(name="task", count=1)]

    def test_should_return_no_skills_or_tools_for_a_log_without_tool_use(self) -> None:
        assert parse_tool_tallies("working\n[AGENT_EXIT] 0\n") == ([], [])

    def test_should_ignore_tool_use_events_without_a_dict_part(self) -> None:
        log = json.dumps({"type": "tool_use", "part": "not-a-dict"})

        assert parse_tool_tallies(log) == ([], [])
