from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import create_autospec

import pytest
from github.Issue import Issue
from github.IssueComment import IssueComment
from github.PullRequest import PullRequest
from github.Repository import Repository

from grooveloop.learning.domain.conventions_pull_request import ConventionsPullRequest
from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from grooveloop.learning.infrastructure.github_refinement_result import GithubRefinementResult
from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache


def _cache() -> GithubReadCache:
    clock = create_autospec(Clock, spec_set=True, instance=True)
    clock.now.return_value = datetime(2026, 6, 1, tzinfo=UTC)

    return GithubReadCache(clock)


_CAPTURED_AT = datetime(2026, 6, 10, tzinfo=UTC)
_AFTER_THE_CAPTURE = datetime(2026, 6, 11, tzinfo=UTC)
_BEFORE_THE_CAPTURE = datetime(2026, 6, 9, tzinfo=UTC)


def _issue_comment(body: str, created_at: datetime = _AFTER_THE_CAPTURE) -> Any:
    comment = create_autospec(IssueComment, spec_set=True, instance=True)
    comment.body = body
    comment.created_at = created_at

    return comment


def _pull(number: int, issue_comments: list[Any]) -> Any:
    pull = create_autospec(PullRequest, spec_set=True, instance=True)
    pull.number = number
    pull.get_issue_comments.return_value = issue_comments

    return pull


def _pr_issue(number: int, body: str, created_at: datetime = _AFTER_THE_CAPTURE) -> Any:
    issue = create_autospec(Issue, spec_set=True, instance=True)
    issue.number = number
    issue.pull_request = object()
    issue.body = body
    issue.created_at = created_at

    return issue


def _repo(pulls: list[Any], issues: list[Any]) -> Any:
    repo = create_autospec(Repository, spec_set=True, instance=True)
    by_number = {pull.number: pull for pull in pulls}
    repo.get_pull.side_effect = lambda number: by_number[number]
    repo.get_issues.side_effect = lambda state, labels: list(issues)

    return repo


@pytest.mark.integration
class TestGithubRefinementResult:
    def test_reports_learned_with_the_linked_conventions_pull_request(self) -> None:
        conventions = _pr_issue(101, "Refines the convention.\n<!-- grooveloop:lesson pr=42 -->")
        result = GithubRefinementResult(_repo([_pull(42, [])], [conventions]), _cache())

        outcome = result.of(SourcePullRequest(42), _CAPTURED_AT)

        assert outcome is not None
        assert outcome.conventions_pull_request == ConventionsPullRequest(101)
        assert outcome.discarded is False

    def test_reports_discarded_when_the_scribe_left_the_discard_marker(self) -> None:
        pull = _pull(42, [_issue_comment("Nothing to codify.\n<!-- grooveloop:learned discarded -->")])
        result = GithubRefinementResult(_repo([pull], []), _cache())

        outcome = result.of(SourcePullRequest(42), _CAPTURED_AT)

        assert outcome is not None
        assert outcome.conventions_pull_request is None
        assert outcome.discarded is True

    def test_reports_no_result_while_the_scribe_has_not_produced_one(self) -> None:
        result = GithubRefinementResult(_repo([_pull(42, [])], []), _cache())

        assert result.of(SourcePullRequest(42), _CAPTURED_AT) is None

    def test_prefers_the_conventions_pull_request_over_a_discard_marker(self) -> None:
        conventions = _pr_issue(101, "Refines the convention.\n<!-- grooveloop:lesson pr=42 -->")
        pull = _pull(42, [_issue_comment("Nothing to codify.\n<!-- grooveloop:learned discarded -->")])
        result = GithubRefinementResult(_repo([pull], [conventions]), _cache())

        outcome = result.of(SourcePullRequest(42), _CAPTURED_AT)

        assert outcome is not None
        assert outcome.conventions_pull_request == ConventionsPullRequest(101)

    def test_reports_the_conventions_pull_request_opened_after_the_capture_of_the_lesson(self) -> None:
        earlier = _pr_issue(101, "<!-- grooveloop:lesson pr=42 -->", created_at=_BEFORE_THE_CAPTURE)
        later = _pr_issue(120, "<!-- grooveloop:lesson pr=42 -->", created_at=_AFTER_THE_CAPTURE)
        result = GithubRefinementResult(_repo([_pull(42, [])], [later, earlier]), _cache())

        outcome = result.of(SourcePullRequest(42), _CAPTURED_AT)

        assert outcome is not None
        assert outcome.conventions_pull_request == ConventionsPullRequest(120)

    def test_ignores_the_results_of_a_lesson_captured_earlier_from_the_same_pull_request(self) -> None:
        conventions = _pr_issue(101, "<!-- grooveloop:lesson pr=42 -->", created_at=_BEFORE_THE_CAPTURE)
        pull = _pull(
            42, [_issue_comment("Nothing.\n<!-- grooveloop:learned discarded -->", created_at=_BEFORE_THE_CAPTURE)]
        )
        result = GithubRefinementResult(_repo([pull], [conventions]), _cache())

        assert result.of(SourcePullRequest(42), _CAPTURED_AT) is None
