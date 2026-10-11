from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock, create_autospec

import pytest
from github.Repository import Repository

from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
from grooveloop.verification.domain.pull_request_number import PullRequestNumber
from grooveloop.verification.domain.slice_id import SliceId
from grooveloop.verification.infrastructure.github_merged_slice_signal import GithubMergedSliceSignal
from tests.playground.shared.infrastructure.github_slice_graph import (
    conversation_comment,
    pr_node,
    slice_node,
    wire_slice_graph,
)

_TITLE = "Mark verify-deploy when creating the sub-issues"
_BODY = "- **Observable verification:**\n\n  1. `gh pr view 42`.\n"


def _cache() -> GithubReadCache:
    clock = create_autospec(Clock, spec_set=True, instance=True)
    clock.now.return_value = datetime(2026, 6, 1, tzinfo=UTC)

    return GithubReadCache(clock)


@pytest.fixture
def repo() -> Any:
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.full_name = "owner/repo"

    return repo


def _story() -> Any:
    return slice_node(10, "grooveloop", title="Deploy verification")


@pytest.mark.integration
class TestGithubMergedSliceSignal:
    def test_reads_the_merged_marked_slices(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            _story(),
            slice_node(
                11,
                "story:10",
                "verify-deploy",
                title=_TITLE,
                body=_BODY,
                state="CLOSED",
                pull_request=pr_node(42, state="MERGED", merged=True),
            ),
        )

        merged_slices = GithubMergedSliceSignal(repo, _cache()).merged_slices()

        assert len(merged_slices) == 1
        assert merged_slices[0].slice_id == SliceId("11")
        assert merged_slices[0].pull_request_number == PullRequestNumber(42)
        assert merged_slices[0].title == _TITLE
        assert merged_slices[0].description == _BODY
        assert merged_slices[0].has_report is False

    def test_reports_the_marker_left_in_the_pull_request_conversation(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            _story(),
            slice_node(
                11,
                "story:10",
                "verify-deploy",
                state="CLOSED",
                pull_request=pr_node(
                    42,
                    state="MERGED",
                    merged=True,
                    conversation=[conversation_comment("does not degrade\n<!-- grooveloop:verify-deploy -->")],
                ),
            ),
        )

        merged_slices = GithubMergedSliceSignal(repo, _cache()).merged_slices()

        assert merged_slices[0].has_report is True

    def test_ignores_a_slice_without_the_verify_deploy_label(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            _story(),
            slice_node(11, "story:10", state="CLOSED", pull_request=pr_node(42, state="MERGED", merged=True)),
        )

        assert GithubMergedSliceSignal(repo, _cache()).merged_slices() == []

    def test_ignores_a_marked_slice_whose_pull_request_is_not_merged(self, repo: Mock) -> None:
        wire_slice_graph(repo, _story(), slice_node(11, "story:10", "verify-deploy", pull_request=pr_node(42)))

        assert GithubMergedSliceSignal(repo, _cache()).merged_slices() == []

    def test_ignores_a_marked_slice_without_pull_request(self, repo: Mock) -> None:
        wire_slice_graph(repo, _story(), slice_node(11, "story:10", "verify-deploy"))

        assert GithubMergedSliceSignal(repo, _cache()).merged_slices() == []
