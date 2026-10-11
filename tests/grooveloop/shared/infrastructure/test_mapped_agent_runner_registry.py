from __future__ import annotations

import pytest

from grooveloop.shared.domain.exceptions import UnsupportedEngineError
from grooveloop.shared.infrastructure.mapped_agent_runner_registry import MappedAgentRunnerRegistry
from tests.playground.shared.infrastructure.fake_agent_runner import FakeAgentRunner


class TestMappedAgentRunnerRegistry:
    def test_should_resolve_the_runner_registered_for_the_engine(self) -> None:
        claude = FakeAgentRunner()
        opencode = FakeAgentRunner()
        registry = MappedAgentRunnerRegistry({"claude": claude, "opencode": opencode})

        assert registry.runner_for("opencode") is opencode
        assert registry.runner_for("claude") is claude

    def test_should_raise_when_the_engine_is_not_registered(self) -> None:
        registry = MappedAgentRunnerRegistry({"claude": FakeAgentRunner()})

        with pytest.raises(UnsupportedEngineError):
            registry.runner_for("codex")
