from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock, create_autospec, patch

import pytest
from github import Github
from github.File import File
from github.Issue import Issue
from github.Label import Label
from github.PullRequest import PullRequest
from github.Repository import Repository

from grooveloop.bootstrap import container
from grooveloop.cli import loop_command
from grooveloop.cli import tick as tick_module
from grooveloop.cli.story_snapshot import StorySnapshot
from grooveloop.delivery.infrastructure.github_delivery_labels import GithubDeliveryLabels
from grooveloop.delivery.infrastructure.github_pull_request_merger_probe import GithubPullRequestMergerProbe
from grooveloop.shared.domain.agent_runner import AgentRunner
from grooveloop.shared.domain.agent_runner_registry import AgentRunnerRegistry
from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.domain.loop_presence import LoopPresence
from grooveloop.shared.domain.loop_snapshots import LoopSnapshots
from grooveloop.shared.domain.pull_request_details import PullRequestDetails
from grooveloop.shared.domain.story_specs import StorySpecs
from grooveloop.shared.infrastructure.agent_profiles_probe import AgentProfilesProbe
from grooveloop.shared.infrastructure.claude_probe import ClaudeProbe
from grooveloop.shared.infrastructure.cli.exit_code import ExitCode
from grooveloop.shared.infrastructure.docker_compose_probe import DockerComposeProbe
from grooveloop.shared.infrastructure.github_auth_probe import GithubAuthProbe
from grooveloop.shared.infrastructure.github_graphql_probe import GithubGraphQLProbe
from grooveloop.shared.infrastructure.grooveloop_cli_probe import GrooveloopCliProbe
from grooveloop.shared.infrastructure.opencode_probe import OpencodeProbe
from tests.playground.shared.infrastructure.clock import clock_at
from tests.playground.shared.infrastructure.fake_agent_runner import FakeAgentRunner
from tests.playground.shared.infrastructure.fake_agent_runner_registry import FakeAgentRunnerRegistry
from tests.playground.shared.infrastructure.fake_loop_presence import CountingLoopPresence, FakeLoopPresence
from tests.playground.shared.infrastructure.fake_loop_snapshots import FailingLoopSnapshots, FakeLoopSnapshots
from tests.playground.shared.infrastructure.fake_probe import FailingProbe, PassingProbe
from tests.playground.shared.infrastructure.fake_pull_request_details import FakePullRequestDetails
from tests.playground.shared.infrastructure.fake_story_specs import FakeStorySpecs
from tests.playground.shared.infrastructure.github_slice_graph import graph_reads, pr_node, slice_node, wire_slice_graph

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


_T0 = datetime(2026, 8, 25, 12, 0, 0, tzinfo=UTC)


def _tick_waiting_for(event: threading.Event, seen: list[bool]) -> Callable[..., int]:
    def run(*args: Any, **kwargs: Any) -> int:
        seen.append(event.wait(timeout=2))

        return 0

    return run


def _tick_taking(clock: Mock, seconds: float) -> Callable[..., int]:
    def run(*args: Any, **kwargs: Any) -> int:
        clock.now.return_value += timedelta(seconds=seconds)

        return 0

    return run


def _tick_recording(ensured: list[int], labels: Mock) -> Callable[..., int]:
    def run(*args: Any, **kwargs: Any) -> int:
        ensured.append(labels.ensure.call_count)

        return 0

    return run


def _sleep_advancing(clock: Mock, seconds: float, *outcomes: Any) -> Callable[..., None]:
    pending = list(outcomes)

    def sleep(*args: Any, **kwargs: Any) -> None:
        clock.now.return_value += timedelta(seconds=seconds)
        outcome = pending.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome

    return sleep


def _label(name: str) -> Any:
    label = create_autospec(Label, spec_set=True, instance=True)
    label.name = name

    return label


def _issue(number: int, *label_names: str, body: str = "") -> Any:
    issue = create_autospec(Issue, spec_set=True, instance=True)
    issue.number = number
    issue.title = f"issue {number}"
    issue.labels = [_label(name) for name in label_names]
    issue.body = body
    issue.pull_request = None

    return issue


@pytest.fixture(autouse=True)
def every_environment_probe_passes() -> Iterator[None]:
    with (
        container.override(GithubAuthProbe, PassingProbe()),
        container.override(GithubGraphQLProbe, PassingProbe()),
        container.override(ClaudeProbe, PassingProbe()),
        container.override(OpencodeProbe, PassingProbe()),
        container.override(GrooveloopCliProbe, PassingProbe()),
        container.override(AgentProfilesProbe, PassingProbe()),
        container.override(DockerComposeProbe, PassingProbe()),
    ):
        yield


@pytest.fixture
def github_with_a_sliced_story() -> Any:
    parent = _issue(10, "grooveloop", "sliced", body="## Slices\n### First\n")
    slice_merged = _issue(11, "story:10", "merged", "order:1")
    slice_open = _issue(12, "story:10", "pr_open", "order:2")
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.get_issue.side_effect = lambda number: {10: parent, 11: slice_merged, 12: slice_open}[number]
    wire_slice_graph(
        repo,
        slice_node(10, "grooveloop", "sliced", title="issue 10", body="## Slices\n### First\n"),
        slice_node(11, "story:10", "merged", "order:1"),
        slice_node(12, "story:10", "pr_open", "order:2"),
    )
    github = create_autospec(Github, spec_set=True, instance=True)
    github.get_repo.return_value = repo
    with container.override(Github, github):
        yield repo


@pytest.fixture
def github_with_an_open_pull_request() -> Any:
    file = create_autospec(File, spec_set=True, instance=True)
    file.filename = "src/x.py"
    file.status = "modified"
    file.additions = 3
    file.deletions = 1
    file.patch = "@@ -1 +1 @@"
    pull = create_autospec(PullRequest, spec_set=True, instance=True)
    pull.body = "## Summary"
    pull.get_files.return_value = [file]
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.get_pull.return_value = pull
    wire_slice_graph(
        repo,
        slice_node(10, "grooveloop", "sliced", title="issue 10", body="## Slices\n### First\n"),
        slice_node(11, "story:10", "pr_open", "order:1", pull_request=pr_node(60)),
    )
    github = create_autospec(Github, spec_set=True, instance=True)
    github.get_repo.return_value = repo
    with container.override(Github, github):
        yield repo


@pytest.mark.entrypoint
class TestLoopCommand:
    def test_should_ensure_the_delivery_labels_before_the_first_tick(self, github_with_a_sliced_story: Mock) -> None:
        labels = create_autospec(GithubDeliveryLabels, spec_set=True, instance=True)
        ensured_before_tick: list[int] = []
        with (
            container.override(GithubDeliveryLabels, labels),
            patch.object(tick_module, "run", side_effect=_tick_recording(ensured_before_tick, labels)),
        ):
            loop_command.run("acme/sample", once=True)

        assert ensured_before_tick == [1]

    def test_should_ensure_the_delivery_labels_only_once_across_ticks(self, github_with_a_sliced_story: Mock) -> None:
        clock = clock_at(_T0)
        labels = create_autospec(GithubDeliveryLabels, spec_set=True, instance=True)
        with (
            container.override(GithubDeliveryLabels, labels),
            container.override(Clock, clock),
            patch.object(tick_module, "run", return_value=0) as tick,
            patch(
                "grooveloop.cli.loop_command.time.sleep",
                side_effect=_sleep_advancing(clock, 2, None, None, KeyboardInterrupt()),
            ),
        ):
            loop_command.run("acme/sample", interval=2, tick_interval=3)

        assert tick.call_count == 2
        assert labels.ensure.call_count == 1

    def test_should_keep_ticking_when_the_delivery_labels_cannot_be_created(
        self, github_with_a_sliced_story: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        labels = create_autospec(GithubDeliveryLabels, spec_set=True, instance=True)
        labels.ensure.side_effect = RuntimeError("resource not accessible by personal access token")
        with (
            container.override(GithubDeliveryLabels, labels),
            patch.object(tick_module, "run", return_value=0) as tick,
        ):
            exit_code = loop_command.run("acme/sample", once=True)

        assert exit_code == 0
        assert tick.call_count == 1
        assert "delivery labels unavailable" in capsys.readouterr().err

    def test_should_run_an_immediate_tick_on_start(self, github_with_a_sliced_story: Mock) -> None:
        with (
            patch.object(tick_module, "run", return_value=0) as tick,
            patch("grooveloop.cli.loop_command.time.sleep", side_effect=KeyboardInterrupt()),
        ):
            loop_command.run("acme/sample", workdir="/tmp/wd")

        tick.assert_called_once_with(
            "acme/sample",
            "/tmp/wd",
            story=None,
            verify_deploy=False,
            max_review_rounds=0,
            max_parallel_slices=1,
            journal_enabled=False,
            max_retries=0,
            auto_merge=False,
        )

    def test_should_forward_the_journal_flag_to_the_tick(self, github_with_a_sliced_story: Mock) -> None:
        with (
            patch.object(tick_module, "run", return_value=0) as tick,
            patch("grooveloop.cli.loop_command.time.sleep", side_effect=KeyboardInterrupt()),
        ):
            loop_command.run("acme/sample", workdir="/tmp/wd", journal_enabled=True)

        tick.assert_called_once_with(
            "acme/sample",
            "/tmp/wd",
            story=None,
            verify_deploy=False,
            max_review_rounds=0,
            max_parallel_slices=1,
            journal_enabled=True,
            max_retries=0,
            auto_merge=False,
        )

    def test_should_forward_the_max_retries_to_the_tick(self, github_with_a_sliced_story: Mock) -> None:
        with (
            patch.object(tick_module, "run", return_value=0) as tick,
            patch("grooveloop.cli.loop_command.time.sleep", side_effect=KeyboardInterrupt()),
        ):
            loop_command.run("acme/sample", workdir="/tmp/wd", max_retries=2)

        assert tick.call_args.kwargs["max_retries"] == 2

    def test_should_forward_the_auto_merge_flag_to_the_tick(self, github_with_a_sliced_story: Mock) -> None:
        probe = create_autospec(GithubPullRequestMergerProbe, spec_set=True, instance=True)
        with (
            container.override(GithubPullRequestMergerProbe, probe),
            patch.object(tick_module, "run", return_value=0) as tick,
        ):
            loop_command.run("acme/sample", workdir="/tmp/wd", once=True, auto_merge=True)

        assert tick.call_args.kwargs["auto_merge"] is True
        probe.check.assert_called_once_with()

    def test_should_refuse_to_start_when_the_merger_probe_fails(
        self, github_with_a_sliced_story: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        probe = create_autospec(GithubPullRequestMergerProbe, spec_set=True, instance=True)
        probe.name = "github-pull-request-merger"
        probe.check.side_effect = RuntimeError("owner/repo does not allow squash merges")
        with (
            container.override(GithubPullRequestMergerProbe, probe),
            patch.object(tick_module, "run", return_value=0) as tick,
        ):
            exit_code = loop_command.run("acme/sample", workdir="/tmp/wd", once=True, auto_merge=True)

        captured = capsys.readouterr()
        assert exit_code == ExitCode.PREFLIGHT_FAILED
        tick.assert_not_called()
        assert captured.out == ""
        assert "[fail] github-pull-request-merger: owner/repo does not allow squash merges" in captured.err

    def test_should_refuse_to_start_when_a_required_probe_fails(
        self, github_with_a_sliced_story: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        labels = create_autospec(GithubDeliveryLabels, spec_set=True, instance=True)
        with (
            container.override(GithubAuthProbe, FailingProbe()),
            container.override(GithubDeliveryLabels, labels),
            patch.object(tick_module, "run", return_value=0) as tick,
        ):
            exit_code = loop_command.run("acme/sample", workdir="/tmp/wd", once=True)

        captured = capsys.readouterr()
        assert exit_code == ExitCode.PREFLIGHT_FAILED
        tick.assert_not_called()
        labels.ensure.assert_not_called()
        assert captured.out == ""
        assert "[fail] github-auth: not available" in captured.err

    def test_should_start_without_checking_the_merger_when_auto_merge_is_off(
        self, github_with_a_sliced_story: Mock
    ) -> None:
        with (
            container.override(GithubPullRequestMergerProbe, FailingProbe()),
            patch.object(tick_module, "run", return_value=0) as tick,
        ):
            exit_code = loop_command.run("acme/sample", workdir="/tmp/wd", once=True)

        assert exit_code == 0
        tick.assert_called_once()

    def test_should_start_when_only_docker_compose_is_unavailable(
        self, github_with_a_sliced_story: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with (
            container.override(DockerComposeProbe, FailingProbe()),
            patch.object(tick_module, "run", return_value=0) as tick,
        ):
            exit_code = loop_command.run("acme/sample", workdir="/tmp/wd", once=True)

        captured = capsys.readouterr()
        assert exit_code == 0
        tick.assert_called_once()
        assert captured.out == ""
        assert "[warn] docker-compose-cli: not available" in captured.err

    def test_should_run_another_tick_after_the_tick_interval_elapses(self, github_with_a_sliced_story: Mock) -> None:
        clock = clock_at(_T0)
        with (
            container.override(Clock, clock),
            patch.object(tick_module, "run", return_value=0) as tick,
            patch(
                "grooveloop.cli.loop_command.time.sleep",
                side_effect=_sleep_advancing(clock, 2, None, None, KeyboardInterrupt()),
            ),
        ):
            loop_command.run("acme/sample", interval=2, tick_interval=3)

        assert tick.call_count == 2

    def test_should_run_another_tick_when_the_cycle_takes_longer_than_the_nominal_interval(
        self, github_with_a_sliced_story: Mock
    ) -> None:
        clock = clock_at(_T0)
        with (
            container.override(Clock, clock),
            patch.object(tick_module, "run", return_value=0) as tick,
            patch(
                "grooveloop.cli.loop_command.time.sleep",
                side_effect=_sleep_advancing(clock, 10, None, KeyboardInterrupt()),
            ),
        ):
            loop_command.run("acme/sample", interval=1, tick_interval=3)

        assert tick.call_count == 2

    def test_should_materialize_a_ready_story_on_the_immediate_tick(self, capsys: pytest.CaptureFixture[str]) -> None:
        issue = create_autospec(Issue, spec_set=True, instance=True)
        issue.number = 7
        issue.body = "## Slices\n### First\n### Second\n"
        issue.labels = [_label("grooveloop"), _label("ready_for_implementation")]
        issue.pull_request = None
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.return_value = issue
        wire_slice_graph(repo, slice_node(7, "grooveloop", "ready_for_implementation", body=issue.body))
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo

        with (
            container.override(Github, github),
            container.override(AgentRunner, FakeAgentRunner()),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(FakeAgentRunner())),
            patch("grooveloop.cli.loop_command.time.sleep", side_effect=KeyboardInterrupt()),
        ):
            exit_code = loop_command.run("acme/sample", workdir="/tmp/wd")

        assert exit_code == 0
        assert repo.create_issue.call_count == 2

    def test_should_run_ticks_continuously_without_writing_to_stdout(
        self, github_with_a_sliced_story: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with (
            patch.object(tick_module, "run", return_value=0) as tick,
            patch("grooveloop.cli.loop_command.time.sleep", side_effect=[None, KeyboardInterrupt()]),
        ):
            exit_code = loop_command.run("acme/sample", interval=2)

        output = capsys.readouterr().out
        assert exit_code == 0
        assert tick.called
        assert output == ""

    def test_should_make_a_single_pass_without_output_with_once(
        self, github_with_a_sliced_story: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with (
            patch.object(tick_module, "run", return_value=0) as tick,
            patch("grooveloop.cli.loop_command.time.sleep") as sleep,
        ):
            exit_code = loop_command.run("acme/sample", once=True)

        output = capsys.readouterr().out
        assert exit_code == 0
        tick.assert_called_once()
        sleep.assert_not_called()
        assert output == ""

    def test_should_read_the_story_graph_once_per_tick(self, github_with_a_sliced_story: Mock) -> None:
        loop_command.run("acme/sample", once=True)

        assert graph_reads(github_with_a_sliced_story) == 1

    def test_should_scope_the_tick_to_the_given_story(self, github_with_a_sliced_story: Mock) -> None:
        with patch.object(tick_module, "run", return_value=0) as tick:
            loop_command.run("acme/sample", workdir="/tmp/wd", once=True, story=10)

        tick.assert_called_once_with(
            "acme/sample",
            "/tmp/wd",
            story=10,
            verify_deploy=False,
            max_review_rounds=0,
            max_parallel_slices=1,
            journal_enabled=False,
            max_retries=0,
            auto_merge=False,
        )

    def test_should_keep_looping_when_a_tick_raises(self) -> None:
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.side_effect = RuntimeError("boom")
        snapshots = FakeLoopSnapshots()
        with (
            container.override(Github, github),
            container.override(LoopSnapshots, snapshots),
            patch.object(tick_module, "run", side_effect=RuntimeError("boom")),
            patch("grooveloop.cli.loop_command.time.sleep", side_effect=[None, KeyboardInterrupt()]),
        ):
            exit_code = loop_command.run("acme/inexistente", interval=2)

        assert exit_code == 0
        assert snapshots.published[-1].tick.outcome == "failed"

    def test_should_report_why_a_tick_raised_and_keep_looping(
        self, github_with_a_sliced_story: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with (
            patch.object(tick_module, "run", side_effect=[RuntimeError("github is down"), 0]) as tick,
            patch("grooveloop.cli.loop_command.time.sleep", side_effect=[None, KeyboardInterrupt()]),
        ):
            exit_code = loop_command.run("acme/sample", interval=2, tick_interval=0)

        captured = capsys.readouterr()
        assert exit_code == 0
        assert tick.call_count == 2
        assert captured.out == ""
        assert "[fail] run tick in acme/sample: github is down" in captured.err

    def test_should_publish_its_presence_with_once(self, github_with_a_sliced_story: Mock) -> None:
        presence = FakeLoopPresence()
        with (
            container.override(LoopPresence, presence),
            patch.object(tick_module, "run", return_value=0),
        ):
            loop_command.run("acme/sample", once=True)

        assert presence.beats == ["acme/sample"]

    def test_should_keep_beating_while_a_tick_runs(self, github_with_a_sliced_story: Mock) -> None:
        presence = CountingLoopPresence(beats_awaited=3)
        seen: list[bool] = []
        with (
            container.override(LoopPresence, presence),
            patch.object(tick_module, "run", side_effect=_tick_waiting_for(presence.awaited_beats_reached, seen)),
            patch("grooveloop.cli.loop_command.time.sleep", side_effect=KeyboardInterrupt()),
        ):
            exit_code = loop_command.run("acme/sample", interval=0)

        assert exit_code == 0
        assert seen == [True]

    def test_should_stop_beating_when_interrupted(self, github_with_a_sliced_story: Mock) -> None:
        with (
            container.override(LoopPresence, FakeLoopPresence()),
            patch.object(tick_module, "run", return_value=0),
            patch("grooveloop.cli.loop_command.time.sleep", side_effect=KeyboardInterrupt()),
        ):
            exit_code = loop_command.run("acme/sample", interval=0)

        assert exit_code == 0
        assert [thread.name for thread in threading.enumerate() if thread.name == "grooveloop-heartbeat"] == []

    def test_should_keep_beating_when_the_presence_write_fails(
        self, github_with_a_sliced_story: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        presence = CountingLoopPresence(beats_awaited=3, failing=True)
        seen: list[bool] = []
        with (
            container.override(LoopPresence, presence),
            patch.object(tick_module, "run", side_effect=_tick_waiting_for(presence.awaited_beats_reached, seen)),
            patch("grooveloop.cli.loop_command.time.sleep", side_effect=KeyboardInterrupt()),
        ):
            exit_code = loop_command.run("acme/sample", interval=0)

        captured = capsys.readouterr()
        assert exit_code == 0
        assert seen == [True]
        assert captured.out == ""
        assert "[warn] presence heartbeat failed in acme/sample" in captured.err

    def test_should_publish_the_snapshot_of_the_tick(self, github_with_a_sliced_story: Mock) -> None:
        clock = clock_at(_T0)
        snapshots = FakeLoopSnapshots()
        with (
            container.override(Clock, clock),
            container.override(LoopSnapshots, snapshots),
            patch.object(tick_module, "run", side_effect=_tick_taking(clock, 38)),
        ):
            loop_command.run("acme/sample", once=True)

        published = snapshots.published[-1]
        assert published.repo == "acme/sample"
        assert published.tick.outcome == "ok"
        assert published.tick.duration_seconds == 38
        assert [story.number for story in published.stories] == ["10"]
        assert [a_slice.number for a_slice in published.stories[0].slices] == ["11", "12"]

    def test_should_publish_the_detail_of_every_open_pull_request_after_the_tick(
        self, github_with_an_open_pull_request: Mock
    ) -> None:
        details = FakePullRequestDetails()
        with (
            container.override(PullRequestDetails, details),
            container.override(LoopSnapshots, FakeLoopSnapshots()),
            patch.object(tick_module, "run", return_value=0),
        ):
            loop_command.run("acme/sample", once=True)

        detail = details.find("acme/sample", 60)
        assert detail is not None
        assert detail.body == "## Summary"
        assert [file.filename for file in detail.files] == ["src/x.py"]

    def test_should_publish_the_spec_of_every_story_after_the_tick(self, github_with_a_sliced_story: Mock) -> None:
        specs = FakeStorySpecs()
        with (
            container.override(StorySpecs, specs),
            container.override(LoopSnapshots, FakeLoopSnapshots()),
            patch.object(tick_module, "run", return_value=0),
        ):
            loop_command.run("acme/sample", once=True)

        assert specs.find("acme/sample", 10) == "## Slices\n### First\n"

    def test_should_publish_the_tick_interval_it_runs_with(self, github_with_a_sliced_story: Mock) -> None:
        snapshots = FakeLoopSnapshots()
        with (
            container.override(LoopSnapshots, snapshots),
            patch.object(tick_module, "run", return_value=0),
        ):
            loop_command.run("acme/sample", once=True, tick_interval=1800)

        assert snapshots.published[-1].tick.interval_seconds == 1800

    def test_should_publish_the_failed_outcome_and_exit_with_failure_when_the_single_tick_fails(self) -> None:
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.side_effect = RuntimeError("boom")
        snapshots = FakeLoopSnapshots()
        with (
            container.override(Github, github),
            container.override(LoopSnapshots, snapshots),
            patch.object(tick_module, "run", return_value=1),
        ):
            exit_code = loop_command.run("acme/inexistente", once=True)

        assert exit_code == ExitCode.FAILURE
        assert snapshots.published[-1].tick.outcome == "failed"
        assert snapshots.published[-1].stories == []

    def test_should_warn_and_keep_ticking_when_the_repository_cannot_be_loaded(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.side_effect = RuntimeError("bad credentials")
        with (
            container.override(Github, github),
            container.override(LoopSnapshots, FakeLoopSnapshots()),
            patch.object(tick_module, "run", return_value=0) as tick,
        ):
            exit_code = loop_command.run("acme/inexistente", once=True)

        captured = capsys.readouterr()
        assert exit_code == 0
        assert tick.called
        assert captured.out == ""
        assert "[warn] target repository unavailable in acme/inexistente: bad credentials" in captured.err

    def test_should_resolve_the_repository_once(self, github_with_a_sliced_story: Mock) -> None:
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = github_with_a_sliced_story
        with (
            container.override(Github, github),
            container.override(LoopSnapshots, FakeLoopSnapshots()),
            patch.object(tick_module, "run", return_value=0),
        ):
            loop_command.run("acme/sample", once=True)

        assert github.get_repo.call_count == 1

    def test_should_warn_when_the_snapshot_cannot_be_read(
        self, github_with_a_sliced_story: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        stories = create_autospec(StorySnapshot, spec_set=True, instance=True)
        stories.read.side_effect = RuntimeError("boom")
        snapshots = FakeLoopSnapshots()
        with (
            container.override(LoopSnapshots, snapshots),
            patch.object(loop_command, "StorySnapshot", return_value=stories),
            patch.object(tick_module, "run", return_value=0),
        ):
            exit_code = loop_command.run("acme/sample", once=True)

        captured = capsys.readouterr()
        assert exit_code == 0
        assert snapshots.published[-1].stories == []
        assert "[warn] tick snapshot read failed in acme/sample" in captured.err

    def test_should_keep_ticking_when_the_snapshot_cannot_be_published(
        self, github_with_a_sliced_story: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with (
            container.override(LoopSnapshots, FailingLoopSnapshots()),
            patch.object(tick_module, "run", return_value=0) as tick,
        ):
            exit_code = loop_command.run("acme/sample", once=True)

        assert exit_code == 0
        assert tick.called
        assert "snapshot" in capsys.readouterr().err
