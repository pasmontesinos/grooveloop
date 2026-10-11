from __future__ import annotations

from grooveloop.shared.domain.agent_command import AgentCommand

_ENGINE = "opencode"
_BINARY = "opencode"


class OpencodeCommand(AgentCommand):
    @property
    def engine(self) -> str:
        return _ENGINE

    def argv(self, model: str) -> list[str]:
        return [_BINARY, "run", "--format", "json", "-m", model, "--dangerously-skip-permissions"]

    def resume_argv(self, model: str, log_head: str) -> list[str] | None:
        return None
