from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grooveloop.bootstrap import container
from grooveloop.cli import doctor_command
from grooveloop.delivery.infrastructure.github_pull_request_merger_probe import GithubPullRequestMergerProbe
from grooveloop.shared.infrastructure.agent_profiles_probe import AgentProfilesProbe
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.claude_probe import ClaudeProbe
from grooveloop.shared.infrastructure.docker_compose_probe import DockerComposeProbe
from grooveloop.shared.infrastructure.filesystem_agent_profiles import PROFILE_NAMES
from grooveloop.shared.infrastructure.github_auth_probe import GithubAuthProbe
from grooveloop.shared.infrastructure.github_graphql_probe import GithubGraphQLProbe
from grooveloop.shared.infrastructure.github_token import GithubTokenError
from grooveloop.shared.infrastructure.grooveloop_cli_probe import GrooveloopCliProbe
from grooveloop.shared.infrastructure.opencode_probe import OpencodeProbe
from grooveloop.shared.infrastructure.target_repo import TargetRepo
from tests.playground.shared.infrastructure.fake_probe import FailingProbe, PassingProbe

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


def _github_auth_probe_without_token() -> GithubAuthProbe:
    raise GithubTokenError("Could not obtain a GitHub token from `gh auth token`")


def _workdir_whose_profiles_run_on(tmp_path: Path, engine: str, profile_names: list[str]) -> str:
    agents_dir = tmp_path / ".grooveloop" / "agents"
    agents_dir.mkdir(parents=True)
    for name in profile_names:
        (agents_dir / f"{name}.md").write_text(f"---\nengine: {engine}\n---\n")

    return str(tmp_path)


@pytest.fixture
def all_probes_pass() -> Iterator[None]:
    with (
        container.override(GithubAuthProbe, PassingProbe()),
        container.override(GithubGraphQLProbe, PassingProbe()),
        container.override(AgentProfilesProbe, PassingProbe()),
        container.override(ClaudeProbe, PassingProbe()),
        container.override(OpencodeProbe, PassingProbe()),
        container.override(GrooveloopCliProbe, PassingProbe()),
        container.override(DockerComposeProbe, PassingProbe()),
    ):
        yield


@pytest.fixture
def one_probe_fails() -> Iterator[None]:
    with (
        container.override(GithubAuthProbe, PassingProbe()),
        container.override(GithubGraphQLProbe, PassingProbe()),
        container.override(AgentProfilesProbe, PassingProbe()),
        container.override(ClaudeProbe, FailingProbe()),
        container.override(OpencodeProbe, PassingProbe()),
        container.override(GrooveloopCliProbe, PassingProbe()),
        container.override(DockerComposeProbe, PassingProbe()),
    ):
        yield


@pytest.mark.entrypoint
class TestDoctorCommand:
    def test_should_exit_zero_when_all_probes_pass(
        self, all_probes_pass: None, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exit_code = doctor_command.run()

        assert exit_code == 0

    def test_should_check_opencode_when_a_profile_runs_on_it(
        self, all_probes_pass: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        doctor_command.run(workdir=_workdir_whose_profiles_run_on(tmp_path, "opencode", ["developer"]))

        assert "[ok]   opencode-cli" in capsys.readouterr().out

    def test_should_not_check_opencode_when_no_profile_runs_on_it(
        self, all_probes_pass: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with container.override(OpencodeProbe, FailingProbe()):
            exit_code = doctor_command.run(workdir=str(tmp_path))

        assert exit_code == 0
        assert "opencode-cli" not in capsys.readouterr().out

    def test_should_not_check_claude_when_no_profile_runs_on_it(
        self, one_probe_fails: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exit_code = doctor_command.run(workdir=_workdir_whose_profiles_run_on(tmp_path, "opencode", PROFILE_NAMES))

        assert exit_code == 0
        assert "claude-cli" not in capsys.readouterr().out

    def test_should_report_the_docker_compose_probe(
        self, all_probes_pass: None, capsys: pytest.CaptureFixture[str]
    ) -> None:
        doctor_command.run()

        assert "[ok]   docker-compose-cli" in capsys.readouterr().out

    def test_should_bind_the_received_workdir_in_the_root_injector(self, all_probes_pass: None) -> None:
        doctor_command.run(workdir="/wd")

        assert container.get(AgentWorkdir) == AgentWorkdir("/wd")

    def test_should_exit_nonzero_when_a_probe_fails(
        self, one_probe_fails: None, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exit_code = doctor_command.run()

        assert exit_code == 1
        assert "not available" in capsys.readouterr().out

    def test_should_report_a_probe_that_cannot_be_built_as_failed(
        self, all_probes_pass: None, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with container.override(GithubAuthProbe, _github_auth_probe_without_token):
            exit_code = doctor_command.run()

        assert exit_code == 1
        assert "[fail] github-auth: Could not obtain a GitHub token from `gh auth token`" in capsys.readouterr().out

    def test_should_warn_without_failing_when_docker_compose_is_unavailable(
        self, all_probes_pass: None, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with container.override(DockerComposeProbe, FailingProbe()):
            exit_code = doctor_command.run()

        assert exit_code == 0
        assert "[warn] docker-compose-cli: not available" in capsys.readouterr().out

    def test_should_check_the_merger_of_the_given_repo(
        self, all_probes_pass: None, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with container.override(GithubPullRequestMergerProbe, FailingProbe()):
            exit_code = doctor_command.run(repo="acme/sample")

        assert exit_code == 1
        assert "[fail] github-pull-request-merger: not available" in capsys.readouterr().out
        assert container.get(TargetRepo) == TargetRepo("acme/sample")
