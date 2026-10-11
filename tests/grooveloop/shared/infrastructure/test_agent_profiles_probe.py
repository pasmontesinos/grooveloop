from __future__ import annotations

from pathlib import Path

import pytest

from grooveloop.shared.domain.agent_profile import AgentProfile
from grooveloop.shared.infrastructure.agent_profiles_probe import AgentProfilesProbe
from grooveloop.shared.infrastructure.filesystem_agent_profiles import FilesystemAgentProfiles
from tests.playground.shared.infrastructure.fake_agent_profiles import FakeAgentProfiles


def _profile(name: str = "developer", engine: str = "claude", context_files: list[str] | None = None) -> AgentProfile:
    return AgentProfile(
        name=name, engine=engine, model="opus", skills=[], context_files=context_files or [], persona="p"
    )


def _all_profiles(**overrides: AgentProfile) -> list[AgentProfile]:
    names = ["developer", "reviewer", "scribe", "verifier"]

    return [overrides.get(name, _profile(name=name)) for name in names]


class TestAgentProfilesProbe:
    def test_passes_when_the_default_parses_with_a_supported_engine(self, tmp_path: Path) -> None:
        AgentProfilesProbe(agent_profiles=FakeAgentProfiles(_all_profiles()), workdir=str(tmp_path)).check()

    def test_passes_when_the_engine_is_opencode(self, tmp_path: Path) -> None:
        profiles = _all_profiles(developer=_profile(engine="opencode"))

        AgentProfilesProbe(agent_profiles=FakeAgentProfiles(profiles), workdir=str(tmp_path)).check()

    def test_fails_when_the_default_is_missing(self, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError):
            AgentProfilesProbe(agent_profiles=FakeAgentProfiles(), workdir=str(tmp_path)).check()

    def test_fails_when_the_engine_is_not_supported(self, tmp_path: Path) -> None:
        profiles = _all_profiles(developer=_profile(engine="codex"))

        with pytest.raises(RuntimeError):
            AgentProfilesProbe(agent_profiles=FakeAgentProfiles(profiles), workdir=str(tmp_path)).check()

    def test_passes_when_every_declared_context_file_exists_in_the_workdir(self, tmp_path: Path) -> None:
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "domain.md").write_text("x")
        profiles = _all_profiles(reviewer=_profile(name="reviewer", context_files=["docs/domain.md"]))

        AgentProfilesProbe(agent_profiles=FakeAgentProfiles(profiles), workdir=str(tmp_path)).check()

    def test_fails_naming_the_profile_and_path_when_a_declared_context_file_is_missing(self, tmp_path: Path) -> None:
        profiles = _all_profiles(verifier=_profile(name="verifier", context_files=["docs/no-existe.md"]))

        with pytest.raises(RuntimeError, match=r"verifier.*docs/no-existe\.md"):
            AgentProfilesProbe(agent_profiles=FakeAgentProfiles(profiles), workdir=str(tmp_path)).check()


_REPO_ROOT = Path(__file__).resolve().parents[4]
_CONVENTIONS = sorted(f"docs/conventions/{path.name}" for path in (_REPO_ROOT / "docs" / "conventions").glob("*.md"))


@pytest.mark.integration
class TestAgentProfilesProbeOverThisRepository:
    def test_passes_with_the_versioned_overrides(self) -> None:
        profiles = FilesystemAgentProfiles(workdir=str(_REPO_ROOT))

        AgentProfilesProbe(agent_profiles=profiles, workdir=str(_REPO_ROOT)).check()

    @pytest.mark.parametrize("name", ["developer", "scribe"])
    def test_profile_declares_every_convention(self, name: str) -> None:
        profile = FilesystemAgentProfiles(workdir=str(_REPO_ROOT)).find(name)

        assert profile is not None
        assert sorted(profile.context_files) == _CONVENTIONS

    def test_reviewer_declares_every_convention_but_git_workflow(self) -> None:
        profile = FilesystemAgentProfiles(workdir=str(_REPO_ROOT)).find("reviewer")

        assert profile is not None
        assert sorted(profile.context_files) == [path for path in _CONVENTIONS if not path.endswith("git-workflow.md")]
