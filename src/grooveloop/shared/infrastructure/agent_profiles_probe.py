from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from grooveloop.shared.application.probes.probe import Probe
from grooveloop.shared.infrastructure.filesystem_agent_profiles import PROFILE_NAMES, SUPPORTED_ENGINES

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_profiles import AgentProfiles

_DEFAULT_PROFILE = "developer"


class AgentProfilesProbe(Probe):
    name = "agent-profiles"

    def __init__(self, agent_profiles: AgentProfiles, workdir: str) -> None:
        self._agent_profiles = agent_profiles
        self._workdir = workdir

    def check(self) -> None:
        profile = self._agent_profiles.find(_DEFAULT_PROFILE)
        if profile is None:
            raise RuntimeError("default developer profile does not parse")

        if profile.engine not in SUPPORTED_ENGINES:
            raise RuntimeError(f"unsupported engine: {profile.engine}")

        self._check_context_files()

    def _check_context_files(self) -> None:
        for name in PROFILE_NAMES:
            profile = self._agent_profiles.find(name)
            if profile is None:
                continue

            missing = [path for path in profile.context_files if not (Path(self._workdir) / path).is_file()]
            if missing:
                raise RuntimeError(f"profile {name} declares missing context files: {', '.join(missing)}")
