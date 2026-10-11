from __future__ import annotations

import json

from grooveloop.shared.domain.agent_command import AgentCommand
from grooveloop.shared.infrastructure.claude_session_id_parser import parse_session_id

_ENGINE = "claude"
_BINARY = "claude"
_SETTINGS = json.dumps(
    {
        "outputStyle": "Concise",
        "permissions": {"allow": ["Bash(grooveloop note:*)", "Bash(grooveloop journal:*)"]},
        "env": {"BASH_DEFAULT_TIMEOUT_MS": "600000", "BASH_MAX_TIMEOUT_MS": "3600000"},
    }
)


class ClaudeCommand(AgentCommand):
    @property
    def engine(self) -> str:
        return _ENGINE

    def argv(self, model: str) -> list[str]:
        return [
            _BINARY,
            "--print",
            "--output-format",
            "stream-json",
            "--verbose",
            "--strict-mcp-config",
            "--model",
            model,
            "--settings",
            _SETTINGS,
        ]

    def resume_argv(self, model: str, log_head: str) -> list[str] | None:
        session_id = parse_session_id(log_head)
        if session_id is None:
            return None

        return [*self.argv(model), "--resume", session_id]
