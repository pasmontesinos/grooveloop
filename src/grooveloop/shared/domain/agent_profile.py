from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_profile_parser import ParsedAgentProfile

_FOREGROUND_COMMANDS = (
    "Do not run commands in the background or end your turn waiting for a task or a notification: "
    "wait in the foreground for each long command to finish, even if it takes a while, and continue with its result."
)


@dataclass(frozen=True)
class AgentProfile:
    name: str
    engine: str
    model: str
    skills: list[str]
    context_files: list[str]
    persona: str

    @classmethod
    def from_parsed(cls, parsed: ParsedAgentProfile) -> Self | None:
        if parsed.name is None or parsed.engine is None or parsed.model is None:
            return None

        return cls(
            name=parsed.name,
            engine=parsed.engine,
            model=parsed.model,
            skills=parsed.skills or [],
            context_files=parsed.context_files or [],
            persona=parsed.persona or "",
        )

    def render(self, task: str) -> str:
        sections = [self.persona.strip(), self._references(), _FOREGROUND_COMMANDS, task.strip()]

        return "\n\n".join(section for section in sections if section)

    def _references(self) -> str:
        lines = []
        if self.skills:
            lines.append("Before you start, load each of these skills with the Skill tool:")
            lines.extend(f"- {skill}" for skill in self.skills)

        if self.context_files:
            lines.append("Before you start, read each of these files with the Read tool:")
            lines.extend(f"- {path}" for path in self.context_files)

        return "\n".join(lines)
