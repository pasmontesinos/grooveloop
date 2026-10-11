from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.domain.agent_profiles import AgentProfiles

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_profile import AgentProfile


class FakeAgentProfiles(AgentProfiles):
    def __init__(self, profiles: list[AgentProfile] | None = None) -> None:
        self._profiles = {profile.name: profile for profile in profiles or []}

    def find(self, name: str) -> AgentProfile | None:
        return self._profiles.get(name)
