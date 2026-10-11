from __future__ import annotations

from grooveloop.shared.infrastructure.agent_action import describe_action


class TestDescribeAction:
    def test_should_describe_the_tool_with_its_description(self) -> None:
        assert describe_action("Bash", {"command": "ls", "description": "List files"}) == "Bash · List files"

    def test_should_fall_back_to_the_file_path_when_there_is_no_description(self) -> None:
        assert describe_action("read", {"filePath": "src/main.py"}) == "read · src/main.py"

    def test_should_collapse_the_whitespace_of_the_detail(self) -> None:
        assert describe_action("Bash", {"command": "make test\n && make lint"}) == "Bash · make test && make lint"

    def test_should_truncate_a_long_detail(self) -> None:
        described = describe_action("Bash", {"description": "x" * 200})

        assert described == f"Bash · {'x' * 80}…"

    def test_should_fall_back_to_the_invoked_skill(self) -> None:
        assert describe_action("Skill", {"skill": "superpowers:brainstorming"}) == "Skill · superpowers:brainstorming"

    def test_should_describe_the_tool_alone_when_no_detail_is_recognized(self) -> None:
        assert describe_action("TodoWrite", {"todos": [{"content": "write"}]}) == "TodoWrite"

    def test_should_describe_the_tool_alone_when_the_input_is_not_a_mapping(self) -> None:
        assert describe_action("Bash", None) == "Bash"

    def test_should_not_describe_a_tool_without_a_name(self) -> None:
        assert describe_action("", {"description": "List files"}) is None
