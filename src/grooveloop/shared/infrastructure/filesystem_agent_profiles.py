from __future__ import annotations

from pathlib import Path

from grooveloop.shared.domain.agent_profile import AgentProfile
from grooveloop.shared.domain.agent_profile_parser import ParsedAgentProfile, parse_agent_profile
from grooveloop.shared.domain.agent_profiles import AgentProfiles

SUPPORTED_ENGINES: frozenset[str] = frozenset({"claude", "opencode"})

_DEFAULTS_DIR = Path(__file__).parent / "agent_profiles"
_OVERRIDE_DIR = Path(".grooveloop") / "agents"

PROFILE_NAMES: list[str] = sorted(path.stem for path in _DEFAULTS_DIR.glob("*.md"))


class FilesystemAgentProfiles(AgentProfiles):
    def __init__(self, workdir: str) -> None:
        self._workdir = workdir

    def find(self, name: str) -> AgentProfile | None:
        default = self._read_default(name)
        if default is None:
            return None

        merged = self._apply_override(name, default)

        return AgentProfile.from_parsed(merged)

    def _read_default(self, name: str) -> ParsedAgentProfile | None:
        path = _DEFAULTS_DIR / f"{name}.md"
        if not path.is_file():
            return None

        return parse_agent_profile(path.read_text())

    def _apply_override(self, name: str, default: ParsedAgentProfile) -> ParsedAgentProfile:
        path = Path(self._workdir) / _OVERRIDE_DIR / f"{name}.md"
        if not path.is_file():
            return default

        override = parse_agent_profile(path.read_text())
        if override is None:
            return default

        return override.merged_over(default)
