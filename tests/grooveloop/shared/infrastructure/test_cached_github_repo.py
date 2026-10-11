from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

import pytest
from github.Commit import Commit
from github.Issue import Issue
from github.IssueComment import IssueComment
from github.PullRequest import PullRequest
from github.PullRequestReview import PullRequestReview
from github.Repository import Repository

from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.infrastructure.cached_github_repo import CachedGithubRepo
from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache

if TYPE_CHECKING:
    from unittest.mock import Mock


def _pull(number: int) -> Any:
    pull = create_autospec(PullRequest, spec_set=True, instance=True)
    pull.number = number

    return pull


@pytest.fixture
def repo() -> Any:
    return create_autospec(Repository, spec_set=True, instance=True)


@pytest.fixture
def cache() -> GithubReadCache:
    clock = create_autospec(Clock, spec_set=True, instance=True)
    clock.now.return_value = datetime(2026, 6, 1, tzinfo=UTC)

    return GithubReadCache(clock)


@pytest.mark.integration
class TestCachedGithubRepo:
    def test_issues_are_read_from_the_edge_once_within_ttl(self, repo: Mock, cache: GithubReadCache) -> None:
        repo.get_issues.return_value = [create_autospec(Issue, spec_set=True, instance=True)]
        cached = CachedGithubRepo(repo, cache)

        cached.issues("open")
        cached.issues("open")

        repo.get_issues.assert_called_once_with(state="open")

    def test_issues_returns_a_materialized_list(self, repo: Mock, cache: GithubReadCache) -> None:
        issue = create_autospec(Issue, spec_set=True, instance=True)
        repo.get_issues.return_value = iter([issue])
        cached = CachedGithubRepo(repo, cache)

        assert cached.issues("open") == [issue]

    def test_each_issue_state_is_cached_separately(self, repo: Mock, cache: GithubReadCache) -> None:
        repo.get_issues.return_value = []
        cached = CachedGithubRepo(repo, cache)

        cached.issues("open")
        cached.issues("all")

        assert repo.get_issues.call_count == 2

    def test_issues_can_be_filtered_by_labels_at_the_edge(self, repo: Mock, cache: GithubReadCache) -> None:
        repo.get_issues.return_value = []
        cached = CachedGithubRepo(repo, cache)

        cached.issues("open", labels=["grooveloop"])

        repo.get_issues.assert_called_once_with(state="open", labels=["grooveloop"])

    def test_each_label_set_is_cached_separately(self, repo: Mock, cache: GithubReadCache) -> None:
        repo.get_issues.return_value = []
        cached = CachedGithubRepo(repo, cache)

        cached.issues("open", labels=["grooveloop"])
        cached.issues("open", labels=["grooveloop", "story:7"])

        assert repo.get_issues.call_count == 2

    def test_the_same_label_set_hits_the_edge_once_within_ttl(self, repo: Mock, cache: GithubReadCache) -> None:
        repo.get_issues.return_value = []
        cached = CachedGithubRepo(repo, cache)

        cached.issues("open", labels=["grooveloop"])
        cached.issues("open", labels=["grooveloop"])

        repo.get_issues.assert_called_once_with(state="open", labels=["grooveloop"])

    def test_issue_is_read_from_the_edge_once_within_ttl(self, repo: Mock, cache: GithubReadCache) -> None:
        repo.get_issue.return_value = create_autospec(Issue, spec_set=True, instance=True)
        cached = CachedGithubRepo(repo, cache)

        cached.issue(5)
        cached.issue(5)

        repo.get_issue.assert_called_once_with(5)

    def test_pull_is_read_from_the_edge_once_within_ttl(self, repo: Mock, cache: GithubReadCache) -> None:
        repo.get_pull.return_value = _pull(7)
        cached = CachedGithubRepo(repo, cache)

        cached.pull(7)
        cached.pull(7)

        repo.get_pull.assert_called_once_with(7)

    def test_reviews_of_materializes_and_caches_by_pull_number(self, repo: Mock, cache: GithubReadCache) -> None:
        review = create_autospec(PullRequestReview, spec_set=True, instance=True)
        pull = _pull(7)
        pull.get_reviews.return_value = [review]
        repo.get_pull.return_value = pull
        cached = CachedGithubRepo(repo, cache)

        first = cached.reviews_of(7)
        cached.reviews_of(7)

        assert first == [review]
        pull.get_reviews.assert_called_once_with()

    def test_commits_of_materializes_and_caches_by_pull_number(self, repo: Mock, cache: GithubReadCache) -> None:
        commit = create_autospec(Commit, spec_set=True, instance=True)
        pull = _pull(7)
        pull.get_commits.return_value = [commit]
        repo.get_pull.return_value = pull
        cached = CachedGithubRepo(repo, cache)

        first = cached.commits_of(7)
        cached.commits_of(7)

        assert first == [commit]
        pull.get_commits.assert_called_once_with()

    def test_flush_forces_the_next_read_to_requery_the_edge(self, repo: Mock, cache: GithubReadCache) -> None:
        repo.get_issues.return_value = []
        cached = CachedGithubRepo(repo, cache)

        cached.issues("open")
        cached.flush()
        cached.issues("open")

        assert repo.get_issues.call_count == 2

    def test_create_issue_forwards_to_the_edge_and_returns_it(self, repo: Mock, cache: GithubReadCache) -> None:
        created = create_autospec(Issue, spec_set=True, instance=True)
        repo.create_issue.return_value = created
        cached = CachedGithubRepo(repo, cache)

        result = cached.create_issue(title="First", body="a body", labels=["story:7", "pending"])

        repo.create_issue.assert_called_once_with(title="First", body="a body", labels=["story:7", "pending"])
        assert result is created

    def test_create_issue_invalidates_the_issues_list_so_the_next_read_sees_it(
        self, repo: Mock, cache: GithubReadCache
    ) -> None:
        repo.get_issues.return_value = []
        repo.create_issue.return_value = create_autospec(Issue, spec_set=True, instance=True)
        cached = CachedGithubRepo(repo, cache)
        cached.issues("open")

        cached.create_issue(title="First", body="a body", labels=["story:7", "pending"])
        cached.issues("open")

        assert repo.get_issues.call_count == 2

    def test_set_issue_labels_writes_to_the_edge_and_a_later_read_sees_it(
        self, repo: Mock, cache: GithubReadCache
    ) -> None:
        issue = create_autospec(Issue, spec_set=True, instance=True)
        repo.get_issue.return_value = issue
        cached = CachedGithubRepo(repo, cache)
        cached.issue(5)

        cached.set_issue_labels(5, ["story:10", "dispatched"])
        cached.issue(5)

        issue.set_labels.assert_called_once_with("story:10", "dispatched")
        assert repo.get_issue.call_count == 2

    def test_set_issue_labels_invalidates_the_issues_list(self, repo: Mock, cache: GithubReadCache) -> None:
        repo.get_issue.return_value = create_autospec(Issue, spec_set=True, instance=True)
        repo.get_issues.return_value = []
        cached = CachedGithubRepo(repo, cache)
        cached.issues("open")

        cached.set_issue_labels(5, ["dispatched"])
        cached.issues("open")

        assert repo.get_issues.call_count == 2

    def test_set_issue_labels_does_not_invalidate_unrelated_pull_reads(
        self, repo: Mock, cache: GithubReadCache
    ) -> None:
        repo.get_issue.return_value = create_autospec(Issue, spec_set=True, instance=True)
        repo.get_pull.return_value = _pull(7)
        cached = CachedGithubRepo(repo, cache)
        cached.pull(7)

        cached.set_issue_labels(5, ["dispatched"])
        cached.pull(7)

        repo.get_pull.assert_called_once_with(7)

    def test_add_issue_labels_writes_to_the_edge_and_a_later_read_sees_it(
        self, repo: Mock, cache: GithubReadCache
    ) -> None:
        issue = create_autospec(Issue, spec_set=True, instance=True)
        repo.get_issue.return_value = issue
        cached = CachedGithubRepo(repo, cache)
        cached.issue(5)

        cached.add_issue_labels(5, ["sliced"])
        cached.issue(5)

        issue.add_to_labels.assert_called_once_with("sliced")
        assert repo.get_issue.call_count == 2

    def test_close_issue_edits_the_state_and_a_later_read_sees_it(self, repo: Mock, cache: GithubReadCache) -> None:
        issue = create_autospec(Issue, spec_set=True, instance=True)
        repo.get_issue.return_value = issue
        cached = CachedGithubRepo(repo, cache)
        cached.issue(5)

        cached.close_issue(5)
        cached.issue(5)

        issue.edit.assert_called_once_with(state="closed")
        assert repo.get_issue.call_count == 2

    def test_issue_comments_of_materializes_and_caches_by_pull_number(self, repo: Mock, cache: GithubReadCache) -> None:
        comment = create_autospec(IssueComment, spec_set=True, instance=True)
        pull = _pull(7)
        pull.get_issue_comments.return_value = [comment]
        repo.get_pull.return_value = pull
        cached = CachedGithubRepo(repo, cache)

        first = cached.issue_comments_of(7)
        cached.issue_comments_of(7)

        assert first == [comment]
        pull.get_issue_comments.assert_called_once_with()

    def test_comment_on_creates_the_comment_at_the_edge(self, repo: Mock, cache: GithubReadCache) -> None:
        pull = _pull(7)
        repo.get_pull.return_value = pull
        cached = CachedGithubRepo(repo, cache)

        cached.comment_on(7, "a note")

        pull.create_issue_comment.assert_called_once_with("a note")

    def test_a_read_after_comment_on_sees_the_freshly_posted_comment(self, repo: Mock, cache: GithubReadCache) -> None:
        existing = create_autospec(IssueComment, spec_set=True, instance=True)
        posted = create_autospec(IssueComment, spec_set=True, instance=True)
        pull = _pull(7)
        pull.get_issue_comments.side_effect = [[existing], [existing, posted]]
        repo.get_pull.return_value = pull
        cached = CachedGithubRepo(repo, cache)
        cached.issue_comments_of(7)

        cached.comment_on(7, "a note")

        assert cached.issue_comments_of(7) == [existing, posted]

    def test_comment_on_does_not_invalidate_other_cached_reads(self, repo: Mock, cache: GithubReadCache) -> None:
        review = create_autospec(PullRequestReview, spec_set=True, instance=True)
        pull = _pull(7)
        pull.get_reviews.return_value = [review]
        repo.get_pull.return_value = pull
        cached = CachedGithubRepo(repo, cache)
        cached.reviews_of(7)

        cached.comment_on(7, "a note")
        cached.reviews_of(7)

        pull.get_reviews.assert_called_once_with()
