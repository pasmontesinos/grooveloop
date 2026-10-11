from __future__ import annotations

from grooveloop.shared.domain.agent_task_type import AgentTaskType


class TestAgentTaskType:
    def test_should_expose_the_task_type_string_values(self) -> None:
        assert AgentTaskType.IMPLEMENT_SLICE.value == "implement_slice"
        assert AgentTaskType.ADDRESS_REVIEW.value == "address_review"
