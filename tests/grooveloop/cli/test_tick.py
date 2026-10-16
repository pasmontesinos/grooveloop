from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

import pytest
from github import Github
from github.Issue import Issue
from github.Label import Label
from github.Repository import Repository

from grooveloop.bootstrap import container
from grooveloop.cli import tick
from grooveloop.delivery.domain.mergeability import Mergeability
from grooveloop.delivery.domain.pull_request_merger import PullRequestMerger
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.infrastructure.auto_merge import AutoMerge
from grooveloop.delivery.infrastructure.journal_enabled import JournalEnabled
from grooveloop.delivery.infrastructure.max_parallel_slices import MaxParallelSlices
from grooveloop.delivery.infrastructure.max_review_rounds import MaxReviewRounds
from grooveloop.shared.domain.abandoned_agent_runs import AbandonedAgentRuns
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.agent_run_cause import AgentRunCause
from grooveloop.shared.domain.agent_run_verdict import AgentRunVerdict
from grooveloop.shared.domain.agent_runner import AgentRunner
from grooveloop.shared.domain.agent_runner_registry import AgentRunnerRegistry
from grooveloop.shared.domain.agent_task_type import AgentTaskType
from grooveloop.shared.domain.agent_workspaces import AgentWorkspaces
from grooveloop.shared.domain.workspace_containers import WorkspaceContainers
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.cli.exit_code import ExitCode
from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
from grooveloop.shared.infrastructure.github_story_graph import GithubStoryGraph
from grooveloop.shared.infrastructure.max_retries import MaxRetries
from grooveloop.shared.infrastructure.target_repo import TargetRepo
from grooveloop.slicing.infrastructure.verify_deploy import VerifyDeploy
from tests.playground.shared.infrastructure.fake_abandoned_agent_runs import (
    FailingAbandonedAgentRuns,
    FakeAbandonedAgentRuns,
)
from tests.playground.shared.infrastructure.fake_agent_runner import FailingAgentRunner, FakeAgentRunner
from tests.playground.shared.infrastructure.fake_agent_runner_registry import FakeAgentRunnerRegistry
from tests.playground.shared.infrastructure.fake_agent_workspaces import FailingAgentWorkspaces, FakeAgentWorkspaces
from tests.playground.shared.infrastructure.fake_pull_request_merger import (
    FailingPullRequestMerger,
    FakePullRequestMerger,
)
from tests.playground.shared.infrastructure.fake_workspace_containers import FakeWorkspaceContainers
from tests.playground.shared.infrastructure.github_slice_graph import (
    conversation_comment,
    graph_reads,
    inline_comment,
    pr_node,
    reaction_group,
    reactions_added,
    slice_node,
    wire_slice_graph,
)

if TYPE_CHECKING:
    from unittest.mock import Mock


def _label(name: str) -> Any:
    label = create_autospec(Label, spec_set=True, instance=True)
    label.name = name

    return label


def _sub_issue(number: int, *label_names: str) -> Any:
    issue = create_autospec(Issue, spec_set=True, instance=True)
    issue.number = number
    issue.body = ""
    issue.labels = [_label(name) for name in label_names]
    issue.pull_request = None

    return issue


def _mutable_sub_issue(number: int, node: dict[str, Any], *label_names: str) -> Any:
    issue = _sub_issue(number, *label_names)
    issue.set_labels.side_effect = lambda *labels: node["labels"].__setitem__(
        "nodes", [{"name": name} for name in labels]
    )

    return issue


_DEPENDS_ON_BASELINE = "<!-- grooveloop:depends-on -->\n**Depends on:** #11"


def _two_independent_pending_slices() -> tuple[Any, Any, Any]:
    story_issue = create_autospec(Issue, spec_set=True, instance=True)
    story_issue.body = ""
    story_issue.labels = []
    baseline_node = slice_node(11, "story:7", "merged", state="CLOSED")
    first_node = slice_node(12, "story:7", "pending", body=_DEPENDS_ON_BASELINE)
    second_node = slice_node(13, "story:7", "pending", body=_DEPENDS_ON_BASELINE)
    baseline = _sub_issue(11, "story:7", "merged")
    first = _mutable_sub_issue(12, first_node, "story:7", "pending")
    second = _mutable_sub_issue(13, second_node, "story:7", "pending")
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.get_issue.side_effect = {7: story_issue, 11: baseline, 12: first, 13: second}.__getitem__
    wire_slice_graph(repo, baseline_node, first_node, second_node)
    github = create_autospec(Github, spec_set=True, instance=True)
    github.get_repo.return_value = repo

    return github, first, second


def _sliced_story_with_one_merged_slice_marked_for_verification(*verification_labels: str) -> tuple[Any, Any, Any]:
    story_node = slice_node(7, "grooveloop", "sliced", title="feature", body="## Slices\n### First\n")
    story_issue = create_autospec(Issue, spec_set=True, instance=True)
    story_issue.number = 7
    story_issue.title = "feature"
    story_issue.body = story_node["body"]
    story_issue.labels = [_label("grooveloop"), _label("sliced")]
    story_issue.pull_request = None
    story_issue.edit.side_effect = lambda state: story_node.__setitem__("state", state.upper())
    sub_issue = _sub_issue(12, "grooveloop", "story:7", "verify-deploy", "merged", *verification_labels)
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
    wire_slice_graph(
        repo,
        story_node,
        slice_node(
            12,
            "grooveloop",
            "story:7",
            "verify-deploy",
            "merged",
            *verification_labels,
            title="First",
            state="CLOSED",
            pull_request=pr_node(42, state="MERGED", merged=True),
        ),
    )
    github = create_autospec(Github, spec_set=True, instance=True)
    github.get_repo.return_value = repo

    return github, story_issue, sub_issue


@pytest.fixture
def github_with_ready_story() -> Any:
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
    with container.override(Github, github):
        yield repo


def _under_review_slice_with_a_blocking_verdict(*extra_labels: str) -> tuple[Any, Any]:
    story_issue = create_autospec(Issue, spec_set=True, instance=True)
    story_issue.body = ""
    story_issue.labels = []
    sub_issue = _sub_issue(12, "story:7", "under_review", "pr:42", "review:blocking", *extra_labels)
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
    wire_slice_graph(
        repo,
        slice_node(
            12,
            "story:7",
            "under_review",
            "pr:42",
            "review:blocking",
            *extra_labels,
            pull_request=pr_node(42, conversation=[conversation_comment("<!-- grooveloop:review -->\nsummary")]),
        ),
    )
    github = create_autospec(Github, spec_set=True, instance=True)
    github.get_repo.return_value = repo

    return github, sub_issue


def _slice_with_a_rebutted_blocking_verdict(status: str, *conversation: Any) -> tuple[Any, Any]:
    story_issue = create_autospec(Issue, spec_set=True, instance=True)
    story_issue.body = ""
    story_issue.labels = []
    labels = ("story:7", status, "pr:42", "review:blocking", "review-round:1")
    sub_issue = _sub_issue(12, *labels)
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
    wire_slice_graph(
        repo,
        slice_node(
            12,
            *labels,
            pull_request=pr_node(
                42,
                conversation=[
                    conversation_comment("<!-- grooveloop:review -->\nsummary", day=2),
                    conversation_comment("The finding does not apply\n\n<!-- grooveloop:no-changes -->", day=3),
                    *conversation,
                ],
                commit_dates=["2026-06-01T00:00:00Z"],
            ),
        ),
    )
    github = create_autospec(Github, spec_set=True, instance=True)
    github.get_repo.return_value = repo

    return github, sub_issue


def _corrected_slice_with_a_spent_review_round() -> tuple[Any, Any]:
    story_issue = create_autospec(Issue, spec_set=True, instance=True)
    story_issue.body = ""
    story_issue.labels = []
    sub_issue = _sub_issue(12, "story:7", "changes_requested", "pr:42", "review:blocking", "review-round:1")
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
    wire_slice_graph(
        repo,
        slice_node(
            12,
            "story:7",
            "changes_requested",
            "pr:42",
            "review:blocking",
            "review-round:1",
            pull_request=pr_node(
                42,
                conversation=[conversation_comment("<!-- grooveloop:review -->\nsummary", day=2)],
                commit_dates=["2026-06-03T00:00:00Z"],
            ),
        ),
    )
    github = create_autospec(Github, spec_set=True, instance=True)
    github.get_repo.return_value = repo

    return github, sub_issue


def _dispatched_slice_whose_implementation_was_interrupted() -> tuple[Any, Any]:
    story_node = slice_node(7, "grooveloop", "sliced", title="feature", body="## Slices\n### First\n")
    story_issue = create_autospec(Issue, spec_set=True, instance=True)
    story_issue.number = 7
    story_issue.title = "feature"
    story_issue.body = story_node["body"]
    story_issue.labels = [_label("grooveloop"), _label("sliced")]
    story_issue.pull_request = None
    sub_issue = _sub_issue(12, "grooveloop", "story:7", "dispatched", "run:run-1")
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
    wire_slice_graph(
        repo, story_node, slice_node(12, "grooveloop", "story:7", "dispatched", "run:run-1", title="First")
    )
    github = create_autospec(Github, spec_set=True, instance=True)
    github.get_repo.return_value = repo

    return github, sub_issue


_INTERRUPTED_LONG_AGO = AgentRunVerdict(
    AgentOutcome.INTERRUPTED, AgentRunCause.NETWORK, finished_at=datetime(2026, 1, 1, tzinfo=UTC)
)


_SUCCEEDED_LONG_AGO = AgentRunVerdict(AgentOutcome.SUCCEEDED, finished_at=datetime(2026, 1, 1, tzinfo=UTC))


def _pending_slice_before_an_approved_pr_open_slice() -> tuple[Any, Any]:
    story_issue = create_autospec(Issue, spec_set=True, instance=True)
    story_issue.body = ""
    story_issue.labels = []
    approved = _sub_issue(12, "story:7", "pr:42", "run:run-1", "pr_open", "review:approve")
    pending_node = slice_node(11, "story:7", "pending")
    pending = _mutable_sub_issue(11, pending_node, "story:7", "pending")
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.get_issue.side_effect = {7: story_issue, 11: pending, 12: approved}.__getitem__
    wire_slice_graph(
        repo,
        pending_node,
        slice_node(12, "story:7", "pr:42", "run:run-1", "pr_open", "review:approve", pull_request=pr_node(42)),
    )
    github = create_autospec(Github, spec_set=True, instance=True)
    github.get_repo.return_value = repo

    return github, pending


def _slice_in_a_review_phase(*labels: str, pull_request: dict[str, Any] | None = None) -> tuple[Any, Any]:
    story_issue = create_autospec(Issue, spec_set=True, instance=True)
    story_issue.body = ""
    story_issue.labels = []
    sub_issue = _sub_issue(12, "story:7", "pr:42", "run:run-1", *labels)
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
    wire_slice_graph(
        repo, slice_node(12, "story:7", "pr:42", "run:run-1", *labels, pull_request=pull_request or pr_node(42))
    )
    github = create_autospec(Github, spec_set=True, instance=True)
    github.get_repo.return_value = repo

    return github, sub_issue


def _pending_slice_beside_a_merged_slice_marked_for_verification() -> tuple[Any, Any, Any]:
    story_node = slice_node(7, "grooveloop", "sliced", title="feature", body="## Slices\n### First\n### Second\n")
    story_issue = create_autospec(Issue, spec_set=True, instance=True)
    story_issue.number = 7
    story_issue.title = "feature"
    story_issue.body = story_node["body"]
    story_issue.labels = [_label("grooveloop"), _label("sliced")]
    story_issue.pull_request = None
    merged_issue = _sub_issue(11, "grooveloop", "story:7", "verify-deploy", "merged")
    pending_node = slice_node(12, "grooveloop", "story:7", "pending", title="Second")
    pending_issue = _mutable_sub_issue(12, pending_node, "grooveloop", "story:7", "pending")
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.get_issue.side_effect = {7: story_issue, 11: merged_issue, 12: pending_issue}.__getitem__
    wire_slice_graph(
        repo,
        story_node,
        slice_node(
            11,
            "grooveloop",
            "story:7",
            "verify-deploy",
            "merged",
            title="First",
            state="CLOSED",
            pull_request=pr_node(42, state="MERGED", merged=True),
        ),
        pending_node,
    )
    github = create_autospec(Github, spec_set=True, instance=True)
    github.get_repo.return_value = repo

    return github, merged_issue, pending_issue


@pytest.mark.entrypoint
class TestTick:
    def test_should_bind_the_invocation_inputs_in_the_root_injector(self) -> None:
        repo = create_autospec(Repository, spec_set=True, instance=True)
        wire_slice_graph(repo)
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo

        with container.override(Github, github):
            tick.run(
                "acme/sample",
                "/tmp/wd",
                verify_deploy=True,
                max_review_rounds=2,
                max_parallel_slices=3,
                journal_enabled=True,
                max_retries=2,
                auto_merge=True,
            )

        assert container.get(AutoMerge) == AutoMerge(True)
        assert container.get(TargetRepo) == TargetRepo("acme/sample")
        assert container.get(AgentWorkdir) == AgentWorkdir("/tmp/wd")
        assert container.get(VerifyDeploy) == VerifyDeploy(True)
        assert container.get(MaxReviewRounds) == MaxReviewRounds(2)
        assert container.get(MaxParallelSlices) == MaxParallelSlices(3)
        assert container.get(JournalEnabled) == JournalEnabled(True)
        assert container.get(MaxRetries) == MaxRetries(2)

    def test_should_create_a_sub_issue_per_slice(self, github_with_ready_story: Mock) -> None:
        exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert github_with_ready_story.create_issue.call_count == 2

    def test_should_target_the_requested_repo_and_story(self, github_with_ready_story: Mock) -> None:
        tick.run("acme/sample", "/tmp/wd")

        github_with_ready_story.get_issue.assert_any_call(7)

    def test_should_read_github_again_instead_of_the_graph_cached_by_the_panel(
        self, github_with_ready_story: Mock
    ) -> None:
        wire_slice_graph(github_with_ready_story)
        GithubStoryGraph(github_with_ready_story, container.get(GithubReadCache)).nodes()
        wire_slice_graph(
            github_with_ready_story,
            slice_node(7, "grooveloop", "ready_for_implementation", body="## Slices\n### First\n### Second\n"),
        )

        exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert github_with_ready_story.create_issue.call_count == 2

    def test_should_dispatch_the_agent_and_reflect_requested_changes(self) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.body = ""
        story_issue.labels = []
        sub_issue = _sub_issue(12, "story:7", "pr_open", "pr:42")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
        wire_slice_graph(
            repo,
            slice_node(
                12,
                "story:7",
                "pr_open",
                "pr:42",
                pull_request=pr_node(
                    42, inline=[inline_comment("/grooveloop-implement: use the SliceRepository port")]
                ),
            ),
        )
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert agent_runner.dispatched_count == 1
        assert agent_runner.last_workdir == "/tmp/wd"
        labels_set = sub_issue.set_labels.call_args.args
        assert "changes_requested" in labels_set
        assert reactions_added(repo) == [("inline-555", "EYES")]

    def test_should_fail_a_changes_requested_slice_when_the_agent_finished_without_pushing(self) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.body = ""
        story_issue.labels = []
        sub_issue = _sub_issue(12, "story:7", "changes_requested", "pr:42", "run:run-1")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
        wire_slice_graph(
            repo, slice_node(12, "story:7", "changes_requested", "pr:42", "run:run-1", pull_request=pr_node(42))
        )
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_runner = FakeAgentRunner(outcome=AgentOutcome.FAILED)

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert agent_runner.dispatched_count == 0
        labels_set = sub_issue.set_labels.call_args.args
        assert "failed" in labels_set

    def test_should_fail_a_dispatched_slice_when_the_agent_finished_without_opening_a_pull_request(self) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.body = ""
        story_issue.labels = []
        sub_issue = _sub_issue(12, "story:7", "dispatched", "run:run-1")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
        wire_slice_graph(repo, slice_node(12, "story:7", "dispatched", "run:run-1"))
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_runner = FakeAgentRunner(outcome=AgentOutcome.FAILED)

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert agent_runner.dispatched_count == 0
        labels_set = sub_issue.set_labels.call_args.args
        assert "failed" in labels_set

    def test_should_redispatch_an_interrupted_implementation_with_retries_left(self) -> None:
        github, sub_issue = _dispatched_slice_whose_implementation_was_interrupted()
        agent_runner = FakeAgentRunner(verdict=_INTERRUPTED_LONG_AGO)

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_retries=2)

        assert exit_code == 0
        assert agent_runner.dispatched_count == 1
        labels_set = sub_issue.set_labels.call_args.args
        assert "dispatched" in labels_set
        assert "run:fake-run" in labels_set
        assert "retry:1" in labels_set

    def test_should_fail_an_interrupted_implementation_with_its_cause_without_retries(self) -> None:
        github, sub_issue = _dispatched_slice_whose_implementation_was_interrupted()
        agent_runner = FakeAgentRunner(verdict=_INTERRUPTED_LONG_AGO)

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert agent_runner.dispatched_count == 0
        labels_set = sub_issue.set_labels.call_args.args
        assert "failed" in labels_set
        assert "failure:network" in labels_set

    def test_should_warn_without_failing_the_tick_when_a_redispatch_fails(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        github, sub_issue = _dispatched_slice_whose_implementation_was_interrupted()
        agent_runner = FailingAgentRunner(verdict=_INTERRUPTED_LONG_AGO)

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_retries=2)

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "[warn] dispatch failed for slice 12 in acme/sample: git fetch failed" in captured.err
        sub_issue.set_labels.assert_not_called()

    def test_should_resume_an_implementation_that_finished_without_pull_request(self) -> None:
        github, sub_issue = _dispatched_slice_whose_implementation_was_interrupted()
        agent_runner = FakeAgentRunner(verdict=_SUCCEEDED_LONG_AGO, resumable=True)

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_retries=2)

        assert exit_code == 0
        assert agent_runner.resumed_count == 1
        assert agent_runner.last_resumed_run_id == "run-1"
        labels_set = sub_issue.set_labels.call_args.args
        assert "dispatched" in labels_set
        assert "run:resumed-run" in labels_set
        assert "retry:1" in labels_set

    def test_should_fail_an_implementation_without_pull_request_as_incomplete_once_the_retries_are_spent(
        self,
    ) -> None:
        github, sub_issue = _dispatched_slice_whose_implementation_was_interrupted()
        agent_runner = FakeAgentRunner(verdict=_SUCCEEDED_LONG_AGO, resumable=True)
        sub_issue.labels.append(_label("retry:2"))
        wire_slice_graph(
            github.get_repo.return_value,
            slice_node(7, "grooveloop", "sliced", title="feature", body="## Slices\n### First\n"),
            slice_node(12, "grooveloop", "story:7", "dispatched", "run:run-1", "retry:2", title="First"),
        )

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_retries=2)

        assert exit_code == 0
        assert agent_runner.resumed_count == 0
        labels_set = sub_issue.set_labels.call_args.args
        assert "failed" in labels_set
        assert "failure:incomplete" in labels_set

    def test_should_warn_without_failing_the_tick_when_the_fallback_redispatch_of_a_resume_fails(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        github, sub_issue = _dispatched_slice_whose_implementation_was_interrupted()
        agent_runner = FailingAgentRunner(verdict=_SUCCEEDED_LONG_AGO)

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_retries=2)

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "[warn] dispatch failed for slice 12 in acme/sample: git fetch failed" in captured.err
        sub_issue.set_labels.assert_not_called()

    def test_should_redispatch_an_interrupted_reviewer_keeping_the_slice_under_review(self) -> None:
        github, sub_issue = _slice_in_a_review_phase("under_review")
        agent_runner = FakeAgentRunner(verdict=_INTERRUPTED_LONG_AGO)

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_retries=2)

        assert exit_code == 0
        assert agent_runner.dispatched_count == 1
        assert agent_runner.last_task_type == AgentTaskType.REVIEW_SLICE
        labels_set = sub_issue.set_labels.call_args.args
        assert "under_review" in labels_set
        assert "run:fake-run" in labels_set
        assert "retry:1" in labels_set

    def test_should_squash_merge_an_approved_clean_pull_request_with_auto_merge(self) -> None:
        github, _ = _slice_in_a_review_phase("pr_open", "review:approve")
        merger = FakePullRequestMerger(Mergeability.CLEAN)

        with container.override(Github, github), container.override(PullRequestMerger, merger):
            exit_code = tick.run("acme/sample", "/tmp/wd", auto_merge=True)

        assert exit_code == 0
        assert merger.merged == [PullRequestNumber(42)]

    def test_should_run_the_later_detectors_when_the_merge_fails(self, capsys: pytest.CaptureFixture[str]) -> None:
        github, pending = _pending_slice_before_an_approved_pr_open_slice()
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(PullRequestMerger, FailingPullRequestMerger(Mergeability.CLEAN)),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", auto_merge=True, max_parallel_slices=2)

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "[warn] dispatch failed for slice 12 in acme/sample: 405" in captured.err
        assert "dispatched" in pending.set_labels.call_args.args

    def test_should_not_consult_the_pull_request_without_auto_merge(self) -> None:
        github, _ = _slice_in_a_review_phase("pr_open", "review:approve")
        merger = FakePullRequestMerger(Mergeability.CLEAN)

        with container.override(Github, github), container.override(PullRequestMerger, merger):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert merger.consulted == []

    def test_should_redispatch_an_interrupted_correction_without_spending_a_review_round(self) -> None:
        github, sub_issue = _slice_in_a_review_phase("changes_requested", "review-round:1")
        agent_runner = FakeAgentRunner(verdict=_INTERRUPTED_LONG_AGO)

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_retries=2, max_review_rounds=2)

        assert exit_code == 0
        assert agent_runner.dispatched_count == 1
        assert agent_runner.last_task_type == AgentTaskType.ADDRESS_REVIEW
        labels_set = sub_issue.set_labels.call_args.args
        assert "changes_requested" in labels_set
        assert "retry:1" in labels_set
        assert "review-round:1" in labels_set

    def test_should_resume_a_reviewer_that_finished_without_a_verdict(self) -> None:
        github, sub_issue = _slice_in_a_review_phase("under_review")
        agent_runner = FakeAgentRunner(verdict=_SUCCEEDED_LONG_AGO, resumable=True)

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_retries=2)

        assert exit_code == 0
        assert agent_runner.resumed_count == 1
        labels_set = sub_issue.set_labels.call_args.args
        assert "under_review" in labels_set
        assert "run:resumed-run" in labels_set
        assert "retry:1" in labels_set

    def test_should_resume_a_correction_that_finished_without_new_commits(self) -> None:
        github, sub_issue = _slice_in_a_review_phase("changes_requested", "review-round:1")
        agent_runner = FakeAgentRunner(verdict=_SUCCEEDED_LONG_AGO, resumable=True)

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_retries=2, max_review_rounds=2)

        assert exit_code == 0
        assert agent_runner.resumed_count == 1
        labels_set = sub_issue.set_labels.call_args.args
        assert "changes_requested" in labels_set
        assert "retry:1" in labels_set
        assert "review-round:1" in labels_set

    def test_should_fail_an_interrupted_reviewer_with_its_cause_without_retries(self) -> None:
        github, sub_issue = _slice_in_a_review_phase("under_review")
        agent_runner = FakeAgentRunner(verdict=_INTERRUPTED_LONG_AGO)

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert agent_runner.dispatched_count == 0
        labels_set = sub_issue.set_labels.call_args.args
        assert "failed" in labels_set
        assert "failure:network" in labels_set

    def test_should_warn_without_failing_the_tick_when_the_redispatch_of_a_reviewer_fails(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        github, sub_issue = _slice_in_a_review_phase("under_review")
        agent_runner = FailingAgentRunner(verdict=_INTERRUPTED_LONG_AGO)

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_retries=2)

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "[warn] dispatch failed for slice 12 in acme/sample: git fetch failed" in captured.err
        sub_issue.set_labels.assert_not_called()

    def test_should_drop_the_retries_when_the_retried_review_opens_the_pull_request(self) -> None:
        github, sub_issue = _slice_in_a_review_phase(
            "under_review",
            "retry:1",
            pull_request=pr_node(42, conversation=[conversation_comment("<!-- grooveloop:review -->\nsummary")]),
        )
        agent_runner = FakeAgentRunner(outcome=AgentOutcome.SUCCEEDED)

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_retries=2)

        assert exit_code == 0
        labels_set = sub_issue.set_labels.call_args.args
        assert "pr_open" in labels_set
        assert not any(label.startswith("retry:") for label in labels_set[0])

    def test_should_start_the_review_of_a_dispatched_slice_with_a_linked_pull_request(self) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.body = ""
        story_issue.labels = []
        sub_issue = _sub_issue(12, "story:7", "dispatched")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
        wire_slice_graph(repo, slice_node(12, "story:7", "dispatched", pull_request=pr_node(99, state="OPEN")))
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert agent_runner.dispatched_count == 1
        assert agent_runner.last_task_type == AgentTaskType.REVIEW_SLICE
        labels_set = sub_issue.set_labels.call_args.args
        assert "under_review" in labels_set
        assert "pr:99" in labels_set

    def test_should_start_the_review_of_a_dispatched_slice_with_a_pull_request_labeled_with_the_slice(
        self,
    ) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.body = ""
        story_issue.labels = []
        sub_issue = _sub_issue(12, "story:7", "dispatched")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
        wire_slice_graph(
            repo,
            slice_node(12, "story:7", "dispatched"),
            pull_requests=[pr_node(99, labels=["grooveloop", "slice:12"])],
        )
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert agent_runner.last_task_type == AgentTaskType.REVIEW_SLICE
        labels_set = sub_issue.set_labels.call_args.args
        assert "under_review" in labels_set
        assert "pr:99" in labels_set

    def test_should_open_the_pull_request_of_an_under_review_slice_with_a_review_summary(self) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.body = ""
        story_issue.labels = []
        sub_issue = _sub_issue(12, "story:7", "under_review", "pr:42")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
        wire_slice_graph(
            repo,
            slice_node(
                12,
                "story:7",
                "under_review",
                "pr:42",
                pull_request=pr_node(
                    42, conversation=[conversation_comment("Verdict: OK\n\n<!-- grooveloop:review -->", day=1)]
                ),
            ),
        )
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo

        with (
            container.override(Github, github),
            container.override(AgentRunner, FakeAgentRunner()),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(FakeAgentRunner())),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        labels_set = sub_issue.set_labels.call_args.args
        assert "pr_open" in labels_set

    def test_should_mark_a_pr_open_slice_as_merged_when_its_pull_request_is_merged(self) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.body = ""
        story_issue.labels = []
        sub_issue = _sub_issue(12, "story:7", "pr_open", "pr:42")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
        wire_slice_graph(
            repo, slice_node(12, "story:7", "pr_open", "pr:42", pull_request=pr_node(42, state="MERGED", merged=True))
        )
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        labels_set = sub_issue.set_labels.call_args.args
        assert "merged" in labels_set

    def test_should_fail_a_pr_open_slice_when_its_pull_request_is_closed_without_merge(self) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.body = ""
        story_issue.labels = []
        sub_issue = _sub_issue(12, "story:7", "pr_open", "pr:42")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
        wire_slice_graph(repo, slice_node(12, "story:7", "pr_open", "pr:42", pull_request=pr_node(42, state="CLOSED")))
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert agent_runner.dispatched_count == 0
        labels_set = sub_issue.set_labels.call_args.args
        assert "failed" in labels_set

    def test_should_dispatch_the_next_dispatchable_pending_slice(self) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.body = ""
        story_issue.labels = []
        sub_issue = _sub_issue(12, "story:7", "pending")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
        wire_slice_graph(repo, slice_node(12, "story:7", "pending"))
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert agent_runner.dispatched_count == 1
        assert agent_runner.last_workdir == "/tmp/wd"
        labels_set = sub_issue.set_labels.call_args.args
        assert "dispatched" in labels_set

    def test_should_dispatch_a_pending_slice_when_the_story_is_already_sliced(self) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.body = ""
        story_issue.labels = [_label("sliced")]
        sub_issue = _sub_issue(12, "story:7", "pending")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
        wire_slice_graph(repo, slice_node(12, "story:7", "pending"))
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert agent_runner.dispatched_count == 1
        labels_set = sub_issue.set_labels.call_args.args
        assert "dispatched" in labels_set

    def test_should_dispatch_only_one_of_two_dispatchable_slices_by_default(self) -> None:
        github, _, _ = _two_independent_pending_slices()
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert agent_runner.dispatched_count == 1

    def test_should_dispatch_both_dispatchable_slices_up_to_the_parallel_limit(self) -> None:
        github, _, _ = _two_independent_pending_slices()
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_parallel_slices=2)

        assert exit_code == 0
        assert agent_runner.dispatched_count == 2

    def test_should_run_the_later_detectors_when_a_dispatch_fails(self, capsys: pytest.CaptureFixture[str]) -> None:
        github, merged_issue, pending_issue = _pending_slice_beside_a_merged_slice_marked_for_verification()
        agent_runner = FailingAgentRunner(failing_slice_id="12")

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "[warn] dispatch failed for slice 12 in acme/sample: git fetch failed" in captured.err
        assert "[ok]   ran tick in acme/sample" in captured.out
        assert "verification:running" in merged_issue.set_labels.call_args.args
        pending_issue.set_labels.assert_not_called()

    def test_should_dispatch_another_dispatchable_slice_when_a_dispatch_fails(self) -> None:
        github, first, second = _two_independent_pending_slices()
        agent_runner = FailingAgentRunner(failing_slice_id="12")

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_parallel_slices=2)

        assert exit_code == 0
        assert agent_runner.last_slice_id == "13"
        first.set_labels.assert_not_called()
        assert "dispatched" in second.set_labels.call_args.args

    def test_should_close_the_story_when_all_its_slices_are_merged(self) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.number = 7
        story_issue.title = "feature"
        story_issue.body = "## Slices\n### First\n### Second\n"
        story_issue.labels = [_label("grooveloop"), _label("sliced")]
        story_issue.pull_request = None
        first = _sub_issue(12, "story:7", "merged")
        second = _sub_issue(13, "story:7", "merged")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: first, 13: second}.__getitem__
        wire_slice_graph(
            repo,
            slice_node(7, "grooveloop", "sliced", title="feature", body=story_issue.body),
            slice_node(12, "story:7", "merged", state="CLOSED"),
            slice_node(13, "story:7", "merged", state="CLOSED"),
        )
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        labels_set = story_issue.set_labels.call_args.args
        assert "done" in labels_set
        assert "sliced" not in labels_set
        story_issue.edit.assert_called_once_with(state="closed")

    def test_should_not_close_a_story_with_a_pending_slice(self) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.number = 7
        story_issue.title = "feature"
        story_issue.body = "## Slices\n### First\n### Second\n"
        story_issue.labels = [_label("grooveloop"), _label("sliced")]
        story_issue.pull_request = None
        first = _sub_issue(12, "story:7", "merged")
        second = _sub_issue(13, "story:7", "pending")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: first, 13: second}.__getitem__
        wire_slice_graph(
            repo,
            slice_node(7, "grooveloop", "sliced", title="feature", body=story_issue.body),
            slice_node(12, "story:7", "merged", state="CLOSED"),
            slice_node(13, "story:7", "pending"),
        )
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        story_issue.edit.assert_not_called()

    def test_should_not_close_a_story_whose_merged_pull_request_has_an_uncaptured_lesson(self) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.number = 7
        story_issue.title = "feature"
        story_issue.body = "## Slices\n### First\n"
        story_issue.labels = [_label("grooveloop"), _label("sliced")]
        story_issue.pull_request = None
        first = _sub_issue(12, "story:7", "merged", "pr:40")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: first}.__getitem__
        wire_slice_graph(
            repo,
            slice_node(7, "grooveloop", "sliced", title="feature", body=story_issue.body),
            slice_node(
                12,
                "story:7",
                "merged",
                "pr:40",
                state="CLOSED",
                pull_request=pr_node(
                    40,
                    state="MERGED",
                    merged=True,
                    conversation=[conversation_comment("/grooveloop-learn do not repeat this")],
                ),
            ),
        )
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        story_issue.edit.assert_not_called()

    def test_should_drive_only_the_targeted_story_when_a_story_is_given(self) -> None:
        targeted = _sub_issue(12, "story:7", "pr_open", "pr:42")
        other = _sub_issue(13, "story:8", "pr_open", "pr:43")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {12: targeted, 13: other}.__getitem__
        wire_slice_graph(
            repo,
            slice_node(12, "story:7", "pr_open", "pr:42", pull_request=pr_node(42, state="MERGED", merged=True)),
            slice_node(13, "story:8", "pr_open", "pr:43", pull_request=pr_node(43, state="MERGED", merged=True)),
        )
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", story=7)

        assert exit_code == 0
        assert "merged" in targeted.set_labels.call_args.args
        other.set_labels.assert_not_called()

    def test_should_dispatch_the_targeted_story_even_when_another_story_is_listed_first(self) -> None:
        targeted_story = create_autospec(Issue, spec_set=True, instance=True)
        targeted_story.body = ""
        targeted_story.labels = []
        other_story = create_autospec(Issue, spec_set=True, instance=True)
        other_story.body = ""
        other_story.labels = []
        other_node = slice_node(22, "story:8", "pending")
        targeted_node = slice_node(12, "story:7", "pending")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {
            7: targeted_story,
            8: other_story,
            12: _sub_issue(12, "story:7", "pending"),
            22: _sub_issue(22, "story:8", "pending"),
        }.__getitem__
        wire_slice_graph(repo, other_node, targeted_node)
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", story=7)

        assert exit_code == 0
        assert agent_runner.last_slice_id == "12"

    def test_should_close_the_sub_issue_of_a_resolved_lesson(self) -> None:
        lesson_issue = _sub_issue(500, "grooveloop", "lesson", "source_pr:42", "story:7", "learning:discarded")
        lesson_issue.state = "open"
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {500: lesson_issue}.__getitem__
        repo.get_issues.return_value = [lesson_issue]
        wire_slice_graph(repo)
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo

        with (
            container.override(Github, github),
            container.override(AgentRunner, FakeAgentRunner()),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(FakeAgentRunner())),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        lesson_issue.edit.assert_called_once_with(state="closed")

    def test_should_close_the_sub_issue_of_a_resolved_lesson_of_the_targeted_story(self) -> None:
        lesson_issue = _sub_issue(500, "grooveloop", "lesson", "source_pr:42", "story:7", "learning:discarded")
        lesson_issue.state = "open"
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {500: lesson_issue}.__getitem__
        repo.get_issues.return_value = [lesson_issue]
        wire_slice_graph(repo)
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo

        with (
            container.override(Github, github),
            container.override(AgentRunner, FakeAgentRunner()),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(FakeAgentRunner())),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", story=7)

        assert exit_code == 0
        lesson_issue.edit.assert_called_once_with(state="closed")

    def test_should_leave_a_resolved_lesson_of_another_story_untouched(self) -> None:
        lesson_issue = _sub_issue(500, "grooveloop", "lesson", "source_pr:42", "story:8", "learning:discarded")
        lesson_issue.state = "open"
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {500: lesson_issue}.__getitem__
        repo.get_issues.return_value = [lesson_issue]
        wire_slice_graph(repo)
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo

        with (
            container.override(Github, github),
            container.override(AgentRunner, FakeAgentRunner()),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(FakeAgentRunner())),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", story=7)

        assert exit_code == 0
        lesson_issue.edit.assert_not_called()

    def test_should_read_the_graph_once_within_a_single_tick(self) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.body = ""
        story_issue.labels = []
        sub_issue = _sub_issue(12, "story:7", "pr_open", "pr:42")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
        repo.get_issues.return_value = []
        wire_slice_graph(repo, slice_node(12, "story:7", "pr_open", "pr:42", pull_request=pr_node(42, state="OPEN")))
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo

        with (
            container.override(Github, github),
            container.override(AgentRunner, FakeAgentRunner()),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(FakeAgentRunner())),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert graph_reads(repo) == 1

    def test_should_capture_a_lesson_only_once_across_two_ticks(self) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.number = 7
        story_issue.title = "feature"
        story_issue.body = "## Slices\n### First\n"
        story_issue.labels = [_label("grooveloop"), _label("sliced")]
        story_issue.pull_request = None
        first = _sub_issue(12, "story:7", "merged", "pr:40")
        lesson_issue = _sub_issue(500, "grooveloop", "lesson", "source_pr:40", "story:7", "learning:in_progress")
        lesson_issue.state = "open"
        indexed: list[Any] = []
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: first, 500: lesson_issue}.__getitem__
        repo.get_issues.side_effect = lambda *args, **kwargs: list(indexed)
        wire_slice_graph(
            repo,
            slice_node(7, "grooveloop", "sliced", title="feature", body=story_issue.body),
            slice_node(
                12,
                "story:7",
                "merged",
                "pr:40",
                state="CLOSED",
                pull_request=pr_node(
                    40,
                    state="MERGED",
                    merged=True,
                    conversation=[conversation_comment("/grooveloop-learn do not repeat this")],
                ),
            ),
        )
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo

        with (
            container.override(Github, github),
            container.override(AgentRunner, FakeAgentRunner()),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(FakeAgentRunner())),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            tick.run("acme/sample", "/tmp/wd")
            indexed.append(lesson_issue)
            tick.run("acme/sample", "/tmp/wd")

        assert repo.create_issue.call_count == 1

    def test_should_capture_a_second_lesson_with_only_the_learn_comment_written_after_the_first(self) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.number = 7
        story_issue.title = "feature"
        story_issue.body = "## Slices\n### First\n"
        story_issue.labels = [_label("grooveloop"), _label("sliced")]
        story_issue.pull_request = None
        first = _sub_issue(12, "story:7", "merged", "pr:40")
        lesson_issue = _sub_issue(500, "grooveloop", "lesson", "source_pr:40", "story:7", "learning:discarded")
        lesson_issue.state = "closed"
        lesson_issue.created_at = datetime(2026, 6, 3, tzinfo=UTC)
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: first, 500: lesson_issue}.__getitem__
        repo.get_issues.side_effect = lambda *args, **kwargs: [lesson_issue]
        wire_slice_graph(
            repo,
            slice_node(7, "grooveloop", "sliced", title="feature", body=story_issue.body),
            slice_node(
                12,
                "story:7",
                "merged",
                "pr:40",
                state="CLOSED",
                pull_request=pr_node(
                    40,
                    state="MERGED",
                    merged=True,
                    conversation=[
                        conversation_comment("/grooveloop-learn already captured", day=2, node_id="IC_OLD"),
                        conversation_comment("/grooveloop-learn written after the capture", day=5, node_id="IC_NEW"),
                    ],
                ),
            ),
        )
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo

        with (
            container.override(Github, github),
            container.override(AgentRunner, FakeAgentRunner()),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(FakeAgentRunner())),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            tick.run("acme/sample", "/tmp/wd")

        repo.create_issue.assert_called_once()
        body = repo.create_issue.call_args.kwargs["body"]
        assert "written after the capture" in body
        assert "already captured" not in body
        assert "source_pr:40" in repo.create_issue.call_args.kwargs["labels"]
        assert reactions_added(repo) == [("IC_NEW", "ROCKET")]

    def test_should_read_github_again_on_the_tick_that_follows_another_tick(self) -> None:
        lesson_issue = _sub_issue(500, "grooveloop", "lesson", "source_pr:42", "story:7", "learning:in_progress")
        lesson_issue.state = "open"
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {500: lesson_issue}.__getitem__
        repo.get_issues.return_value = [lesson_issue]
        wire_slice_graph(repo)
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo

        with (
            container.override(Github, github),
            container.override(AgentRunner, FakeAgentRunner()),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(FakeAgentRunner())),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            tick.run("acme/sample", "/tmp/wd")
            reads_of_the_first_tick = repo.get_issues.call_count
            tick.run("acme/sample", "/tmp/wd")

        assert reads_of_the_first_tick > 0
        assert repo.get_issues.call_count > reads_of_the_first_tick

    def test_should_review_again_a_human_correction_when_commits_follow_the_review(self) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.body = ""
        story_issue.labels = []
        sub_issue = _sub_issue(12, "story:7", "changes_requested", "pr:42")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
        wire_slice_graph(
            repo,
            slice_node(
                12,
                "story:7",
                "changes_requested",
                "pr:42",
                pull_request=pr_node(
                    42,
                    inline=[inline_comment("/grooveloop-implement: use the SliceRepository port", day=2)],
                    commit_dates=["2026-06-03T00:00:00Z"],
                ),
            ),
        )
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert agent_runner.dispatched_count == 1
        assert agent_runner.last_task_type == AgentTaskType.REVIEW_SLICE
        labels_set = sub_issue.set_labels.call_args.args
        assert "under_review" in labels_set

    def test_should_mark_as_addressed_only_the_taken_directive_when_the_correction_goes_back_to_the_reviewer(
        self,
    ) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.body = ""
        story_issue.labels = []
        sub_issue = _sub_issue(12, "story:7", "changes_requested", "pr:42")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
        wire_slice_graph(
            repo,
            slice_node(
                12,
                "story:7",
                "changes_requested",
                "pr:42",
                pull_request=pr_node(
                    42,
                    conversation=[
                        conversation_comment(
                            "/grooveloop-implement: use the SliceRepository port",
                            day=2,
                            reactions=[reaction_group("EYES")],
                        ),
                        conversation_comment("/grooveloop-implement: and rename it", day=4),
                    ],
                    commit_dates=["2026-06-03T00:00:00Z"],
                ),
            ),
        )
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert agent_runner.last_task_type == AgentTaskType.REVIEW_SLICE
        assert "under_review" in sub_issue.set_labels.call_args.args
        assert reactions_added(repo) == [("conversation-2", "ROCKET")]

    def test_should_not_send_back_to_the_reviewer_a_correction_whose_directive_was_taken_after_the_last_commit(
        self,
    ) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.body = ""
        story_issue.labels = []
        sub_issue = _sub_issue(12, "story:7", "changes_requested", "pr:42")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
        wire_slice_graph(
            repo,
            slice_node(
                12,
                "story:7",
                "changes_requested",
                "pr:42",
                pull_request=pr_node(
                    42,
                    conversation=[
                        conversation_comment(
                            "/grooveloop-implement: use the SliceRepository port",
                            day=2,
                            reactions=[
                                reaction_group("EYES", reacted_at="2026-06-03T00:00:00Z"),
                                reaction_group("ROCKET"),
                            ],
                        ),
                        conversation_comment(
                            "/grooveloop-implement: and rename it",
                            day=4,
                            reactions=[reaction_group("EYES", reacted_at="2026-06-07T00:00:00Z")],
                        ),
                        conversation_comment("<!-- grooveloop:review -->\nsummary", day=5),
                    ],
                    commit_dates=["2026-06-06T00:00:00Z"],
                ),
            ),
        )
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert agent_runner.dispatched_count == 0
        assert reactions_added(repo) == []

    def test_should_take_again_a_re_opened_directive_without_sending_its_correction_back_to_the_reviewer(
        self,
    ) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.body = ""
        story_issue.labels = []
        node = slice_node(
            12,
            "story:7",
            "pr_open",
            "pr:42",
            pull_request=pr_node(
                42,
                conversation=[
                    conversation_comment(
                        "/grooveloop-implement: use the SliceRepository port",
                        day=1,
                        reactions=[reaction_group("EYES", reacted_at="2026-06-02T00:00:00Z")],
                    ),
                    conversation_comment("<!-- grooveloop:review -->\nsummary", day=4),
                ],
                commit_dates=["2026-06-06T00:00:00Z"],
            ),
        )
        sub_issue = _mutable_sub_issue(12, node, "story:7", "pr_open", "pr:42")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
        wire_slice_graph(repo, node)
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert agent_runner.dispatched_count == 1
        assert agent_runner.last_task_type == AgentTaskType.ADDRESS_REVIEW
        assert "changes_requested" in sub_issue.set_labels.call_args.args
        assert reactions_added(repo) == [("conversation-1", "EYES")]

    def test_should_send_back_to_the_reviewer_a_correction_that_declines_the_changes_with_a_marked_reply(
        self,
    ) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.body = ""
        story_issue.labels = []
        sub_issue = _sub_issue(12, "story:7", "changes_requested", "pr:42")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
        wire_slice_graph(
            repo,
            slice_node(
                12,
                "story:7",
                "changes_requested",
                "pr:42",
                pull_request=pr_node(
                    42,
                    conversation=[
                        conversation_comment("<!-- grooveloop:review -->\nsummary", day=2),
                        conversation_comment(
                            "/grooveloop-implement: use the SliceRepository port",
                            day=3,
                            reactions=[reaction_group("EYES", reacted_at="2026-06-03T00:00:00Z")],
                        ),
                        conversation_comment("The port is already used\n\n<!-- grooveloop:no-changes -->", day=4),
                    ],
                    commit_dates=["2026-06-01T00:00:00Z"],
                ),
            ),
        )
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert agent_runner.last_task_type == AgentTaskType.REVIEW_SLICE
        assert "declined to change code" in agent_runner.last_instruction
        assert "under_review" in sub_issue.set_labels.call_args.args
        assert reactions_added(repo) == [("conversation-3", "ROCKET")]

    def test_should_keep_under_review_a_declined_correction_until_its_new_summary_appears(self) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.body = ""
        story_issue.labels = []
        sub_issue = _sub_issue(12, "story:7", "under_review", "pr:42")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
        wire_slice_graph(
            repo,
            slice_node(
                12,
                "story:7",
                "under_review",
                "pr:42",
                pull_request=pr_node(
                    42,
                    conversation=[
                        conversation_comment("<!-- grooveloop:review -->\nsummary", day=2),
                        conversation_comment(
                            "/grooveloop-implement: use the SliceRepository port",
                            day=3,
                            reactions=[reaction_group("EYES"), reaction_group("ROCKET")],
                        ),
                        conversation_comment("The port is already used\n\n<!-- grooveloop:no-changes -->", day=4),
                    ],
                    commit_dates=["2026-06-01T00:00:00Z"],
                ),
            ),
        )
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert agent_runner.dispatched_count == 0
        sub_issue.set_labels.assert_not_called()

    def test_should_open_for_the_human_an_approved_declined_correction_without_another_correction(self) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.body = ""
        story_issue.labels = []
        node = slice_node(
            12,
            "story:7",
            "under_review",
            "pr:42",
            "review:approve",
            pull_request=pr_node(
                42,
                conversation=[
                    conversation_comment("<!-- grooveloop:review -->\nsummary", day=2),
                    conversation_comment(
                        "/grooveloop-implement: use the SliceRepository port",
                        day=3,
                        reactions=[reaction_group("EYES"), reaction_group("ROCKET")],
                    ),
                    conversation_comment("The port is already used\n\n<!-- grooveloop:no-changes -->", day=4),
                    conversation_comment("The reason holds\n\n<!-- grooveloop:review -->", day=5),
                ],
                commit_dates=["2026-06-01T00:00:00Z"],
            ),
        )
        sub_issue = _mutable_sub_issue(12, node, "story:7", "under_review", "pr:42", "review:approve")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
        wire_slice_graph(repo, node)
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert agent_runner.dispatched_count == 0
        assert "pr_open" in sub_issue.set_labels.call_args.args
        assert reactions_added(repo) == []

    def test_should_correct_a_blocking_verdict_whose_summary_quotes_the_declined_reply(self) -> None:
        story_issue = create_autospec(Issue, spec_set=True, instance=True)
        story_issue.body = ""
        story_issue.labels = []
        sub_issue = _sub_issue(12, "story:7", "under_review", "pr:42", "review:blocking")
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issue.side_effect = {7: story_issue, 12: sub_issue}.__getitem__
        wire_slice_graph(
            repo,
            slice_node(
                12,
                "story:7",
                "under_review",
                "pr:42",
                "review:blocking",
                pull_request=pr_node(
                    42,
                    conversation=[
                        conversation_comment("<!-- grooveloop:review -->\nsummary", day=2),
                        conversation_comment(
                            "/grooveloop-implement: use the SliceRepository port",
                            day=3,
                            reactions=[reaction_group("EYES"), reaction_group("ROCKET")],
                        ),
                        conversation_comment("The port is already used\n\n<!-- grooveloop:no-changes -->", day=4),
                        conversation_comment(
                            "The reply that ends with `<!-- grooveloop:no-changes -->` does not hold\n\n"
                            "<!-- grooveloop:review -->",
                            day=5,
                        ),
                    ],
                    commit_dates=["2026-06-01T00:00:00Z"],
                ),
            ),
        )
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_review_rounds=1)

        assert exit_code == 0
        assert agent_runner.dispatched_count == 1
        assert "changes_requested" in sub_issue.set_labels.call_args.args

    def test_should_send_back_to_the_reviewer_a_blocking_verdict_rebutted_with_a_marked_reply(self) -> None:
        github, sub_issue = _slice_with_a_rebutted_blocking_verdict("changes_requested")
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_review_rounds=2)

        assert exit_code == 0
        assert agent_runner.dispatched_count == 1
        assert agent_runner.last_task_type == AgentTaskType.REVIEW_SLICE
        assert "declined to change code" in agent_runner.last_instruction
        assert "findings of the previous review" in agent_runner.last_instruction
        labels_set = sub_issue.set_labels.call_args.args
        assert "under_review" in labels_set
        assert "review-round:1" in labels_set

    def test_should_spend_a_round_on_a_new_blocking_verdict_of_a_rebutted_correction(self) -> None:
        github, sub_issue = _slice_with_a_rebutted_blocking_verdict(
            "under_review", conversation_comment("The finding still applies\n\n<!-- grooveloop:review -->", day=4)
        )
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_review_rounds=2)

        assert exit_code == 0
        assert agent_runner.dispatched_count == 1
        labels_set = sub_issue.set_labels.call_args.args
        assert "changes_requested" in labels_set
        assert "review-round:2" in labels_set

    def test_should_leave_to_the_human_a_new_blocking_verdict_of_a_rebutted_correction_without_rounds_left(
        self,
    ) -> None:
        github, sub_issue = _slice_with_a_rebutted_blocking_verdict(
            "under_review", conversation_comment("The finding still applies\n\n<!-- grooveloop:review -->", day=4)
        )
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_review_rounds=1)

        assert exit_code == 0
        assert agent_runner.dispatched_count == 0
        labels_set = sub_issue.set_labels.call_args.args
        assert "pr_open" in labels_set
        assert "review-round:1" in labels_set

    def test_should_sweep_the_workspace_of_a_finished_run(self) -> None:
        repo = create_autospec(Repository, spec_set=True, instance=True)
        wire_slice_graph(repo)
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_workspaces = FakeAgentWorkspaces(["run-1", "run-2"])

        with (
            container.override(Github, github),
            container.override(AgentWorkspaces, agent_workspaces),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert agent_workspaces.removed == ["run-1", "run-2"]

    def test_should_sweep_workspaces_even_when_the_tick_targets_one_story(self) -> None:
        repo = create_autospec(Repository, spec_set=True, instance=True)
        wire_slice_graph(repo)
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_workspaces = FakeAgentWorkspaces(["run-1"])

        with (
            container.override(Github, github),
            container.override(AgentWorkspaces, agent_workspaces),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", story=7)

        assert exit_code == 0
        assert agent_workspaces.removed == ["run-1"]

    def test_should_warn_without_failing_the_tick_when_the_sweep_fails(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = create_autospec(Repository, spec_set=True, instance=True)
        wire_slice_graph(repo)
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_workspaces = create_autospec(AgentWorkspaces, spec_set=True, instance=True)
        agent_workspaces.finished_run_ids.side_effect = OSError("read-only run dir")

        with (
            container.override(Github, github),
            container.override(AgentWorkspaces, agent_workspaces),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "[warn] sweep failed in acme/sample: read-only run dir" in captured.err
        assert "[ok]   ran tick in acme/sample" in captured.out

    def test_should_sweep_the_healthy_workspaces_when_one_of_the_pass_fails(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = create_autospec(Repository, spec_set=True, instance=True)
        wire_slice_graph(repo)
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_workspaces = FailingAgentWorkspaces(["run-1", "run-2", "run-3"], failing_run_id="run-1")

        with (
            container.override(Github, github),
            container.override(AgentWorkspaces, agent_workspaces),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        captured = capsys.readouterr()
        assert exit_code == 0
        assert agent_workspaces.removed == ["run-2", "run-3"]
        assert "[warn] sweep failed for run run-1 in acme/sample: read-only run dir" in captured.err
        assert "[ok]   ran tick in acme/sample" in captured.out

    def test_should_warn_naming_the_run_and_sweep_the_workspace_when_docker_fails(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = create_autospec(Repository, spec_set=True, instance=True)
        wire_slice_graph(repo)
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_workspaces = FakeAgentWorkspaces(["run-1"])
        workspace_containers = FakeWorkspaceContainers(failure=RuntimeError("docker compose -p shop down failed"))

        with (
            container.override(Github, github),
            container.override(AgentWorkspaces, agent_workspaces),
            container.override(WorkspaceContainers, workspace_containers),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        captured = capsys.readouterr()
        assert exit_code == 0
        assert agent_workspaces.removed == ["run-1"]
        assert "[warn] sweep failed for run run-1 in acme/sample: docker compose -p shop down failed" in captured.err

    def test_should_sweep_the_workspace_when_a_domain_detector_fails(self, capsys: pytest.CaptureFixture[str]) -> None:
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.full_name = "acme/sample"
        repo.requester.graphql_query.side_effect = RuntimeError("github is down")
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        agent_workspaces = FakeAgentWorkspaces(["run-1"])

        with (
            container.override(Github, github),
            container.override(AgentWorkspaces, agent_workspaces),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == ExitCode.FAILURE
        assert "[fail] run tick in acme/sample: github is down" in capsys.readouterr().err
        assert agent_workspaces.removed == ["run-1"]

    def test_should_close_the_abandoned_runs_of_the_repo(self) -> None:
        repo = create_autospec(Repository, spec_set=True, instance=True)
        wire_slice_graph(repo)
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        abandoned_agent_runs = FakeAbandonedAgentRuns({"acme/sample": ["run-1", "run-2"], "acme/other": ["run-3"]})

        with (
            container.override(Github, github),
            container.override(AbandonedAgentRuns, abandoned_agent_runs),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert abandoned_agent_runs.closed == ["run-1", "run-2"]

    def test_should_close_the_abandoned_runs_before_the_detectors_read_github(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        steps: list[str] = []
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.full_name = "acme/sample"

        def read_github(*args: Any, **kwargs: Any) -> Any:
            steps.append("detect")
            raise RuntimeError("github is down")

        repo.requester.graphql_query.side_effect = read_github
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        abandoned_agent_runs = create_autospec(AbandonedAgentRuns, spec_set=True, instance=True)
        abandoned_agent_runs.abandoned_run_ids.return_value = ["run-1"]
        abandoned_agent_runs.close.side_effect = lambda run_id: steps.append(f"close {run_id}")

        with (
            container.override(Github, github),
            container.override(AbandonedAgentRuns, abandoned_agent_runs),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == ExitCode.FAILURE
        assert steps[:2] == ["close run-1", "detect"]

    def test_should_warn_without_failing_the_tick_when_listing_the_abandoned_runs_fails(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = create_autospec(Repository, spec_set=True, instance=True)
        wire_slice_graph(repo)
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        abandoned_agent_runs = create_autospec(AbandonedAgentRuns, spec_set=True, instance=True)
        abandoned_agent_runs.abandoned_run_ids.side_effect = OSError("read-only run dir")

        with (
            container.override(Github, github),
            container.override(AbandonedAgentRuns, abandoned_agent_runs),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "[warn] closing abandoned runs failed in acme/sample: read-only run dir" in captured.err
        assert "[ok]   ran tick in acme/sample" in captured.out

    def test_should_close_the_other_abandoned_runs_when_closing_one_fails(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = create_autospec(Repository, spec_set=True, instance=True)
        wire_slice_graph(repo)
        github = create_autospec(Github, spec_set=True, instance=True)
        github.get_repo.return_value = repo
        abandoned_agent_runs = FailingAbandonedAgentRuns(
            {"acme/sample": ["run-1", "run-2", "run-3"]}, failing_run_id="run-1"
        )

        with (
            container.override(Github, github),
            container.override(AbandonedAgentRuns, abandoned_agent_runs),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        captured = capsys.readouterr()
        assert exit_code == 0
        assert abandoned_agent_runs.closed == ["run-2", "run-3"]
        assert "[warn] closing failed for run run-1 in acme/sample: read-only run dir" in captured.err
        assert "[ok]   ran tick in acme/sample" in captured.out

    def test_should_label_sub_issues_for_deploy_verification_when_requested(
        self, github_with_ready_story: Mock
    ) -> None:
        tick.run("acme/sample", "/tmp/wd", verify_deploy=True)

        assert all(
            "verify-deploy" in call.kwargs["labels"] for call in github_with_ready_story.create_issue.call_args_list
        )

    def test_should_not_label_sub_issues_for_deploy_verification_by_default(
        self, github_with_ready_story: Mock
    ) -> None:
        tick.run("acme/sample", "/tmp/wd")

        assert all(
            "verify-deploy" not in call.kwargs["labels"] for call in github_with_ready_story.create_issue.call_args_list
        )

    def test_should_dispatch_the_verifier_of_the_last_merged_slice(self) -> None:
        github, _, sub_issue = _sliced_story_with_one_merged_slice_marked_for_verification()
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert agent_runner.last_task_type == AgentTaskType.VERIFY_DEPLOY
        assert "verification:running" in sub_issue.set_labels.call_args.args

    def test_should_not_close_the_story_while_a_slice_verification_is_pending(self) -> None:
        github, story_issue, _ = _sliced_story_with_one_merged_slice_marked_for_verification("verification:running")
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        story_issue.edit.assert_not_called()

    def test_should_close_the_story_when_every_slice_verification_has_concluded(self) -> None:
        github, story_issue, _ = _sliced_story_with_one_merged_slice_marked_for_verification("verification:concluded")
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        story_issue.edit.assert_called_once_with(state="closed")

    def test_should_resume_a_verification_that_finished_without_its_report(self) -> None:
        github, _, sub_issue = _sliced_story_with_one_merged_slice_marked_for_verification(
            "verification:running", "verif-run:run-1"
        )
        agent_runner = FakeAgentRunner(verdict=_SUCCEEDED_LONG_AGO, resumable=True)

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_retries=2)

        assert exit_code == 0
        assert agent_runner.resumed_count == 1
        labels_set = sub_issue.set_labels.call_args.args
        assert "verification:running" in labels_set
        assert "verif-run:resumed-run" in labels_set
        assert "verif-retry:1" in labels_set

    def test_should_redispatch_an_interrupted_verification_with_retries_left(self) -> None:
        github, _, sub_issue = _sliced_story_with_one_merged_slice_marked_for_verification(
            "verification:running", "verif-run:run-1"
        )
        agent_runner = FakeAgentRunner(verdict=_INTERRUPTED_LONG_AGO)

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_retries=2)

        assert exit_code == 0
        assert agent_runner.last_task_type == AgentTaskType.VERIFY_DEPLOY
        labels_set = sub_issue.set_labels.call_args.args
        assert "verification:running" in labels_set
        assert "verif-run:fake-run" in labels_set
        assert "verif-retry:1" in labels_set

    def test_should_fail_an_interrupted_verification_without_retries_and_keep_the_story_open(self) -> None:
        github, story_issue, sub_issue = _sliced_story_with_one_merged_slice_marked_for_verification(
            "verification:running", "verif-run:run-1"
        )
        agent_runner = FakeAgentRunner(verdict=_INTERRUPTED_LONG_AGO)

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert agent_runner.dispatched_count == 0
        labels_set = sub_issue.set_labels.call_args.args
        assert "verification:failed" in labels_set
        assert "failure:network" in labels_set
        story_issue.edit.assert_not_called()

    def test_should_warn_without_failing_the_tick_when_a_verification_redispatch_fails(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        github, _, sub_issue = _sliced_story_with_one_merged_slice_marked_for_verification(
            "verification:running", "verif-run:run-1"
        )
        agent_runner = FailingAgentRunner(verdict=_INTERRUPTED_LONG_AGO)

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_retries=2)

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "[warn] dispatch failed for slice 12 in acme/sample: git fetch failed" in captured.err
        sub_issue.set_labels.assert_not_called()

    def test_should_correct_the_blocking_verdict_when_a_review_round_is_available(self) -> None:
        github, sub_issue = _under_review_slice_with_a_blocking_verdict()
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_review_rounds=1)

        assert exit_code == 0
        assert agent_runner.dispatched_count == 1
        labels_set = sub_issue.set_labels.call_args.args
        assert "changes_requested" in labels_set
        assert "review-round:1" in labels_set

    def test_should_leave_the_blocking_verdict_to_the_human_without_review_rounds(self) -> None:
        github, sub_issue = _under_review_slice_with_a_blocking_verdict()
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd")

        assert exit_code == 0
        assert agent_runner.dispatched_count == 0
        labels_set = sub_issue.set_labels.call_args.args
        assert "pr_open" in labels_set
        assert [label for label in labels_set if label.startswith("review-round:")] == []

    def test_should_not_correct_the_blocking_verdict_once_the_review_round_is_spent(self) -> None:
        github, sub_issue = _under_review_slice_with_a_blocking_verdict("review-round:1")
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_review_rounds=1)

        assert exit_code == 0
        assert agent_runner.dispatched_count == 0
        labels_set = sub_issue.set_labels.call_args.args
        assert "pr_open" in labels_set
        assert "review-round:1" in labels_set

    def test_should_review_the_correction_again_when_a_review_round_is_still_left(self) -> None:
        github, sub_issue = _corrected_slice_with_a_spent_review_round()
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_review_rounds=2)

        assert exit_code == 0
        assert agent_runner.dispatched_count == 1
        assert agent_runner.last_task_type == AgentTaskType.REVIEW_SLICE
        labels_set = sub_issue.set_labels.call_args.args
        assert "under_review" in labels_set
        assert "review-round:1" in labels_set
        assert [label for label in labels_set if label.startswith("review:")] == []

    def test_should_review_the_correction_again_when_the_last_review_round_is_spent(self) -> None:
        github, sub_issue = _corrected_slice_with_a_spent_review_round()
        agent_runner = FakeAgentRunner()

        with (
            container.override(Github, github),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        ):
            exit_code = tick.run("acme/sample", "/tmp/wd", max_review_rounds=1)

        assert exit_code == 0
        assert agent_runner.dispatched_count == 1
        assert agent_runner.last_task_type == AgentTaskType.REVIEW_SLICE
        labels_set = sub_issue.set_labels.call_args.args
        assert "under_review" in labels_set
        assert "review-round:1" in labels_set
