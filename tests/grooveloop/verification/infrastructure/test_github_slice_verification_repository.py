from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock, create_autospec

import pytest
from github.Issue import Issue
from github.Label import Label
from github.Repository import Repository

from grooveloop.shared.domain.agent_run_cause import AgentRunCause
from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
from grooveloop.verification.domain.slice_id import SliceId
from grooveloop.verification.domain.slice_verification import SliceVerification
from grooveloop.verification.domain.story_id import StoryId
from grooveloop.verification.domain.verification_status import VerificationStatus
from grooveloop.verification.infrastructure.github_slice_verification_repository import (
    GithubSliceVerificationRepository,
)
from tests.playground.shared.infrastructure.github_slice_graph import slice_node, wire_slice_graph

_GITHUB_LABEL_MAX_LENGTH = 50
_AGENT_RUN_UUID = "375108df-7b98-4891-a5c1-42cf1bb62b50"


def _cache() -> GithubReadCache:
    clock = create_autospec(Clock, spec_set=True, instance=True)
    clock.now.return_value = datetime(2026, 6, 1, tzinfo=UTC)

    return GithubReadCache(clock)


def _label(name: str) -> Any:
    label = create_autospec(Label, spec_set=True, instance=True)
    label.name = name

    return label


def _marked_issue(number: int, *label_names: str) -> Any:
    issue = create_autospec(Issue, spec_set=True, instance=True)
    issue.number = number
    issue.labels = [_label(name) for name in label_names]

    return issue


@pytest.fixture
def repo() -> Any:
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.full_name = "owner/repo"

    return repo


@pytest.mark.integration
class TestGithubSliceVerificationRepository:
    def test_find_reads_the_status_from_the_label(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(11, "story:10", "verify-deploy", "verification:running"))
        adapter = GithubSliceVerificationRepository(repo, _cache())

        verification = adapter.find(SliceId("11"))

        assert verification is not None
        assert verification.status == VerificationStatus.RUNNING
        assert verification.story_id == StoryId("10")

    def test_find_treats_a_missing_status_label_as_not_started(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(11, "story:10", "verify-deploy"))
        adapter = GithubSliceVerificationRepository(repo, _cache())

        verification = adapter.find(SliceId("11"))

        assert verification is not None
        assert verification.status == VerificationStatus.EMPTY

    def test_find_returns_none_when_the_slice_is_not_marked(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(11, "story:10"))
        adapter = GithubSliceVerificationRepository(repo, _cache())

        assert adapter.find(SliceId("11")) is None

    def test_find_reads_a_merged_slice_whose_sub_issue_is_closed(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(11, "story:10", "verify-deploy", "merged", state="CLOSED"),
        )
        adapter = GithubSliceVerificationRepository(repo, _cache())

        assert adapter.find(SliceId("11")) is not None

    def test_search_filters_by_story_and_status(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(11, "story:10", "verify-deploy", "verification:running"),
            slice_node(12, "story:10", "verify-deploy", "verification:concluded"),
            slice_node(13, "story:10"),
        )
        adapter = GithubSliceVerificationRepository(repo, _cache())

        verifications = adapter.search(story_id=StoryId("10"), status=VerificationStatus.RUNNING)

        assert [verification.slice_id.value for verification in verifications] == ["11"]

    def test_search_returns_every_marked_slice_of_the_story(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(11, "story:10", "verify-deploy"),
            slice_node(12, "story:10", "verify-deploy", "verification:concluded"),
            slice_node(13, "story:10"),
        )
        adapter = GithubSliceVerificationRepository(repo, _cache())

        verifications = adapter.search(story_id=StoryId("10"))

        assert [verification.slice_id.value for verification in verifications] == ["11", "12"]

    def test_save_replaces_the_status_label_and_keeps_the_others(self, repo: Mock) -> None:
        issue = _marked_issue(11, "grooveloop", "verify-deploy", "verification:running")
        repo.get_issue.return_value = issue
        wire_slice_graph(repo, slice_node(11, "story:10", "verify-deploy", "verification:running"))
        adapter = GithubSliceVerificationRepository(repo, _cache())

        adapter.save(SliceVerification(SliceId("11"), StoryId("10"), VerificationStatus.CONCLUDED))

        issue.set_labels.assert_called_once_with("grooveloop", "verify-deploy", "verification:concluded")

    def test_save_writes_no_status_label_when_the_verification_has_not_started(self, repo: Mock) -> None:
        issue = _marked_issue(11, "grooveloop", "verify-deploy", "verification:running")
        repo.get_issue.return_value = issue
        wire_slice_graph(repo, slice_node(11, "story:10", "verify-deploy"))
        adapter = GithubSliceVerificationRepository(repo, _cache())

        adapter.save(SliceVerification(SliceId("11"), StoryId("10"), VerificationStatus.EMPTY))

        issue.set_labels.assert_called_once_with("grooveloop", "verify-deploy")

    def test_save_writes_the_agent_run_label(self, repo: Mock) -> None:
        issue = _marked_issue(11, "grooveloop", "verify-deploy")
        repo.get_issue.return_value = issue
        wire_slice_graph(repo, slice_node(11, "story:10", "verify-deploy"))
        adapter = GithubSliceVerificationRepository(repo, _cache())

        adapter.save(
            SliceVerification(SliceId("11"), StoryId("10"), VerificationStatus.RUNNING, agent_run_id=_AGENT_RUN_UUID)
        )

        issue.set_labels.assert_called_once_with(
            "grooveloop", "verify-deploy", f"verif-run:{_AGENT_RUN_UUID}", "verification:running"
        )

    def test_save_writes_every_label_within_the_github_length_limit(self, repo: Mock) -> None:
        issue = _marked_issue(11, "grooveloop", "verify-deploy")
        repo.get_issue.return_value = issue
        wire_slice_graph(repo, slice_node(11, "story:10", "verify-deploy"))
        adapter = GithubSliceVerificationRepository(repo, _cache())

        adapter.save(
            SliceVerification(SliceId("11"), StoryId("10"), VerificationStatus.RUNNING, agent_run_id=_AGENT_RUN_UUID)
        )

        written = issue.set_labels.call_args.args
        assert [label for label in written if len(label) > _GITHUB_LABEL_MAX_LENGTH] == []

    def test_find_reads_the_agent_run_from_the_label(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(11, "story:10", "verify-deploy", f"verif-run:{_AGENT_RUN_UUID}", "verification:running"),
        )
        adapter = GithubSliceVerificationRepository(repo, _cache())

        verification = adapter.find(SliceId("11"))

        assert verification is not None
        assert verification.agent_run_id == _AGENT_RUN_UUID
        assert verification.status == VerificationStatus.RUNNING

    def test_save_writes_the_failed_status_with_its_attempts_and_cause(self, repo: Mock) -> None:
        issue = _marked_issue(11, "grooveloop", "verify-deploy", "verif-retry:1", "verification:running")
        repo.get_issue.return_value = issue
        wire_slice_graph(repo, slice_node(11, "story:10", "verify-deploy", "verif-retry:1", "verification:running"))
        adapter = GithubSliceVerificationRepository(repo, _cache())

        adapter.save(
            SliceVerification(
                SliceId("11"),
                StoryId("10"),
                VerificationStatus.FAILED,
                agent_run_id=_AGENT_RUN_UUID,
                retries=2,
                failure_cause=AgentRunCause.NETWORK,
            )
        )

        issue.set_labels.assert_called_once_with(
            "grooveloop",
            "verify-deploy",
            f"verif-run:{_AGENT_RUN_UUID}",
            "verification:failed",
            "verif-retry:2",
            "failure:network",
        )

    def test_find_reads_the_attempts_and_the_cause_from_the_labels(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(11, "story:10", "verify-deploy", "verif-retry:2", "failure:overloaded", "verification:failed"),
        )
        adapter = GithubSliceVerificationRepository(repo, _cache())

        verification = adapter.find(SliceId("11"))

        assert verification is not None
        assert verification.status == VerificationStatus.FAILED
        assert verification.retries == 2
        assert verification.failure_cause == AgentRunCause.OVERLOADED

    def test_find_reads_no_attempts_without_the_retry_label(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(11, "story:10", "verify-deploy", "retry:1", "verification:running"))
        adapter = GithubSliceVerificationRepository(repo, _cache())

        verification = adapter.find(SliceId("11"))

        assert verification is not None
        assert verification.retries == 0
