from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from grooveloop.bootstrap import container
from grooveloop.delivery.infrastructure.github_pull_request_merger_probe import GithubPullRequestMergerProbe
from grooveloop.shared.domain.agent_profiles import AgentProfiles
from grooveloop.shared.infrastructure.agent_profiles_probe import AgentProfilesProbe
from grooveloop.shared.infrastructure.claude_probe import ClaudeProbe
from grooveloop.shared.infrastructure.docker_compose_probe import DockerComposeProbe
from grooveloop.shared.infrastructure.filesystem_agent_profiles import PROFILE_NAMES
from grooveloop.shared.infrastructure.github_auth_probe import GithubAuthProbe
from grooveloop.shared.infrastructure.github_graphql_probe import GithubGraphQLProbe
from grooveloop.shared.infrastructure.grooveloop_cli_probe import GrooveloopCliProbe
from grooveloop.shared.infrastructure.opencode_probe import OpencodeProbe

if TYPE_CHECKING:
    from grooveloop.shared.application.probes.probe import Probe

_GITHUB_PROBES: list[type[Probe]] = [GithubAuthProbe, GithubGraphQLProbe]
_ENGINE_PROBES: dict[str, type[Probe]] = {"claude": ClaudeProbe, "opencode": OpencodeProbe}
_LOCAL_PROBES: list[type[Probe]] = [GrooveloopCliProbe, AgentProfilesProbe]
_OPTIONAL_PROBES: list[type[Probe]] = [DockerComposeProbe]


class ProbeStatus(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True)
class ProbeOutcome:
    name: str
    status: ProbeStatus
    error: str = ""

    def line(self) -> str:
        if self.status is ProbeStatus.OK:
            return f"[ok]   {self.name}"

        return f"[{self.status}] {self.name}: {self.error}"


@dataclass(frozen=True)
class PreflightReport:
    outcomes: list[ProbeOutcome]

    def passed(self) -> bool:
        return all(outcome.status is not ProbeStatus.FAIL for outcome in self.outcomes)


def run_preflight(*, with_merger: bool) -> PreflightReport:
    return PreflightReport(
        outcomes=[_outcome_of(probe_type, ProbeStatus.FAIL) for probe_type in _required_probes(with_merger)]
        + [_outcome_of(probe_type, ProbeStatus.WARN) for probe_type in _OPTIONAL_PROBES]
    )


def _required_probes(with_merger: bool) -> list[type[Probe]]:
    engines = _engines_in_use()
    engine_probes = [probe_type for engine, probe_type in _ENGINE_PROBES.items() if engine in engines]
    merger_probes: list[type[Probe]] = [GithubPullRequestMergerProbe] if with_merger else []

    return _GITHUB_PROBES + engine_probes + _LOCAL_PROBES + merger_probes


def _engines_in_use() -> set[str]:
    agent_profiles = container.get(AgentProfiles)
    profiles = [agent_profiles.find(name) for name in PROFILE_NAMES]

    return {profile.engine for profile in profiles if profile is not None}


def _outcome_of(probe_type: type[Probe], status_on_error: ProbeStatus) -> ProbeOutcome:
    try:
        container.get(probe_type).check()
    except Exception as error:
        return ProbeOutcome(name=probe_type.name, status=status_on_error, error=str(error))

    return ProbeOutcome(name=probe_type.name, status=ProbeStatus.OK)
