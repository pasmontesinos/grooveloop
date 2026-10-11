from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import create_autospec

import pytest
from github.Issue import Issue
from github.Label import Label
from github.Repository import Repository

from grooveloop.learning.domain.conventions_pull_request import ConventionsPullRequest
from grooveloop.learning.domain.lesson_comment import LessonComment
from grooveloop.learning.domain.lesson_id import LessonId
from grooveloop.learning.domain.lesson_status import LessonStatus
from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from grooveloop.learning.domain.story_id import StoryId
from grooveloop.learning.infrastructure.github_lesson_repository import GithubLessonRepository
from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
from tests.grooveloop.learning.mothers.lesson_mother import LessonMother


def _cache() -> GithubReadCache:
    clock = create_autospec(Clock, spec_set=True, instance=True)
    clock.now.return_value = datetime(2026, 6, 1, tzinfo=UTC)

    return GithubReadCache(clock)


def _label(name: str) -> Any:
    label = create_autospec(Label, spec_set=True, instance=True)
    label.name = name

    return label


def _lesson_issue(number: int, label_names: list[str], state: str = "open") -> Any:
    issue = create_autospec(Issue, spec_set=True, instance=True)
    issue.number = number
    issue.pull_request = None
    issue.state = state
    issue.labels = [_label(name) for name in label_names]

    return issue


def _repo(issues: list[Any]) -> Any:
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.get_issues.side_effect = lambda state, labels: list(issues)

    return repo


@pytest.mark.integration
class TestGithubLessonRepository:
    def test_save_creates_a_lesson_sub_issue_with_the_expected_labels(self) -> None:
        repo = create_autospec(Repository, spec_set=True, instance=True)
        repo.get_issues.side_effect = lambda state, labels: []
        repository = GithubLessonRepository(repo, _cache())
        lesson = LessonMother.create(
            source_pull_request=42,
            story_id="277",
            comments=[
                LessonComment(
                    body="/grooveloop-learn: inject through the constructor",
                    path="src/x.py",
                    line=10,
                    diff_hunk="@@ @@",
                ),
            ],
        )

        repository.save(lesson)

        repo.create_issue.assert_called_once()
        labels = repo.create_issue.call_args.kwargs["labels"]
        assert "grooveloop" in labels
        assert "lesson" in labels
        assert "source_pr:42" in labels
        assert "learning:in_progress" in labels
        assert "story:277" in labels

    def test_find_by_source_pull_request_returns_the_lesson_from_its_labels(self) -> None:
        issue = _lesson_issue(500, ["grooveloop", "lesson", "source_pr:42", "learning:in_progress"])
        repository = GithubLessonRepository(_repo([issue]), _cache())

        lesson = repository.find_by_source_pull_request(SourcePullRequest(42))

        assert lesson is not None
        assert lesson.id is not None
        assert lesson.id.value == "500"
        assert lesson.source_pull_request == SourcePullRequest(42)
        assert lesson.status == LessonStatus.IN_PROGRESS

    def test_find_by_source_pull_request_reads_the_story_from_its_label(self) -> None:
        issue = _lesson_issue(500, ["grooveloop", "lesson", "source_pr:42", "learning:in_progress", "story:277"])
        repository = GithubLessonRepository(_repo([issue]), _cache())

        lesson = repository.find_by_source_pull_request(SourcePullRequest(42))

        assert lesson is not None
        assert lesson.story_id == StoryId("277")

    def test_find_by_source_pull_request_reads_a_lesson_predating_the_story_label(self) -> None:
        issue = _lesson_issue(500, ["grooveloop", "lesson", "source_pr:42", "learning:discarded"])
        repository = GithubLessonRepository(_repo([issue]), _cache())

        lesson = repository.find_by_source_pull_request(SourcePullRequest(42))

        assert lesson is not None
        assert lesson.story_id is None

    def test_find_by_source_pull_request_returns_none_when_absent(self) -> None:
        repository = GithubLessonRepository(_repo([]), _cache())

        assert repository.find_by_source_pull_request(SourcePullRequest(42)) is None

    def test_search_filters_by_status(self) -> None:
        in_progress = _lesson_issue(500, ["grooveloop", "lesson", "source_pr:42", "learning:in_progress"])
        learned = _lesson_issue(501, ["grooveloop", "lesson", "source_pr:7", "learning:learned"])
        repository = GithubLessonRepository(_repo([in_progress, learned]), _cache())

        result = repository.search(status=LessonStatus.IN_PROGRESS)

        assert [lesson.source_pull_request.value for lesson in result] == [42]

    def test_search_filters_by_story(self) -> None:
        mine = _lesson_issue(500, ["grooveloop", "lesson", "source_pr:42", "learning:in_progress", "story:277"])
        other = _lesson_issue(501, ["grooveloop", "lesson", "source_pr:7", "learning:learned", "story:246"])
        older = _lesson_issue(502, ["grooveloop", "lesson", "source_pr:9", "learning:learned"])
        repository = GithubLessonRepository(_repo([mine, other, older]), _cache())

        result = repository.search(story_id=StoryId("277"))

        assert [lesson.source_pull_request.value for lesson in result] == [42]

    def test_save_is_idempotent_when_the_lesson_already_exists(self) -> None:
        issue = _lesson_issue(500, ["grooveloop", "lesson", "source_pr:42", "learning:in_progress"])
        repo = _repo([issue])
        repo.get_issue.side_effect = lambda number: issue
        repository = GithubLessonRepository(repo, _cache())
        lesson = LessonMother.create(
            source_pull_request=42,
            story_id="277",
            comments=[LessonComment(body="/grooveloop-learn: x", path="", line=0, diff_hunk="")],
        )

        repository.save(lesson)

        repo.create_issue.assert_not_called()
        issue.set_labels.assert_called_once()

    def test_save_writes_the_conventions_pull_request_label_for_a_learned_lesson(self) -> None:
        issue = _lesson_issue(500, ["grooveloop", "lesson", "source_pr:42", "learning:in_progress"])
        repo = _repo([issue])
        repo.get_issue.side_effect = lambda number: issue
        repository = GithubLessonRepository(repo, _cache())
        lesson = repository.find_by_source_pull_request(SourcePullRequest(42))
        assert lesson is not None
        lesson.learn(ConventionsPullRequest(101))

        repository.save(lesson)

        labels = issue.set_labels.call_args.args
        assert "learning:learned" in labels
        assert "conv_pr:101" in labels
        assert "learning:in_progress" not in labels

    def test_find_reads_the_conventions_pull_request_from_its_label(self) -> None:
        issue = _lesson_issue(501, ["grooveloop", "lesson", "source_pr:7", "learning:learned", "conv_pr:101"])
        repository = GithubLessonRepository(_repo([issue]), _cache())

        lesson = repository.find_by_source_pull_request(SourcePullRequest(7))

        assert lesson is not None
        assert lesson.status == LessonStatus.LEARNED
        assert lesson.conventions_pull_request == ConventionsPullRequest(101)

    def test_find_reflects_a_closed_sub_issue(self) -> None:
        issue = _lesson_issue(500, ["grooveloop", "lesson", "source_pr:42", "learning:discarded"], state="closed")
        repository = GithubLessonRepository(_repo([issue]), _cache())

        lesson = repository.find_by_source_pull_request(SourcePullRequest(42))

        assert lesson is not None
        assert lesson.is_open is False

    def test_save_closes_the_sub_issue_of_a_closed_lesson(self) -> None:
        issue = _lesson_issue(500, ["grooveloop", "lesson", "source_pr:42", "learning:discarded"])
        repo = _repo([issue])
        repo.get_issue.side_effect = lambda number: issue
        repository = GithubLessonRepository(repo, _cache())
        lesson = repository.find_by_source_pull_request(SourcePullRequest(42))
        assert lesson is not None
        lesson.close()

        repository.save(lesson)

        issue.edit.assert_called_once_with(state="closed")

    def test_save_leaves_the_sub_issue_of_an_open_lesson_open(self) -> None:
        issue = _lesson_issue(500, ["grooveloop", "lesson", "source_pr:42", "learning:in_progress"])
        repo = _repo([issue])
        repo.get_issue.side_effect = lambda number: issue
        repository = GithubLessonRepository(repo, _cache())
        lesson = repository.find_by_source_pull_request(SourcePullRequest(42))
        assert lesson is not None
        lesson.discard()

        repository.save(lesson)

        issue.edit.assert_not_called()

    def test_find_fails_when_the_lesson_lacks_its_source_pull_request_label(self) -> None:
        issue = _lesson_issue(500, ["grooveloop", "lesson", "learning:in_progress"])
        repo = _repo([issue])
        repo.get_issue.side_effect = lambda number: issue
        repository = GithubLessonRepository(repo, _cache())

        with pytest.raises(ValueError, match="source_pr"):
            repository.find(LessonId("500"))

    def test_find_fails_when_the_lesson_lacks_its_status_label(self) -> None:
        issue = _lesson_issue(500, ["grooveloop", "lesson", "source_pr:42"])
        repo = _repo([issue])
        repo.get_issue.side_effect = lambda number: issue
        repository = GithubLessonRepository(repo, _cache())

        with pytest.raises(ValueError, match="learning:"):
            repository.find(LessonId("500"))
