from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.learning.domain.conventions_pull_request import ConventionsPullRequest
from grooveloop.learning.domain.lesson import Lesson
from grooveloop.learning.domain.lesson_id import LessonId
from grooveloop.learning.domain.lesson_repository import LessonRepository
from grooveloop.learning.domain.lesson_status import LessonStatus
from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from grooveloop.learning.domain.story_id import StoryId
from grooveloop.shared.infrastructure.cached_github_repo import CachedGithubRepo

if TYPE_CHECKING:
    from github.Issue import Issue
    from github.Repository import Repository

    from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache

_MARKER_LABEL = "grooveloop"
_LESSON_LABEL = "lesson"
_SOURCE_PR_LABEL_PREFIX = "source_pr:"
_STATUS_LABEL_PREFIX = "learning:"
_CONVENTIONS_PR_LABEL_PREFIX = "conv_pr:"
_STORY_LABEL_PREFIX = "story:"
_STATUS_VALUES = {status.value for status in LessonStatus}


class GithubLessonRepository(LessonRepository):
    def __init__(self, repo: Repository, cache: GithubReadCache) -> None:
        self._repo = CachedGithubRepo(repo, cache)

    def find(self, id: LessonId) -> Lesson | None:
        issue = self._repo.issue(int(id.value))
        if not self._is_lesson(issue):
            return None

        return self._to_lesson(issue)

    def find_by_source_pull_request(self, source_pull_request: SourcePullRequest) -> Lesson | None:
        target = f"{_SOURCE_PR_LABEL_PREFIX}{source_pull_request.value}"

        for issue in self._lesson_issues():
            if any(label.name == target for label in issue.labels):
                return self._to_lesson(issue)

        return None

    def save(self, lesson: Lesson) -> None:
        existing = self.find_by_source_pull_request(lesson.source_pull_request)
        status_label = f"{_STATUS_LABEL_PREFIX}{lesson.status.value}"

        if existing is None:
            self._repo.create_issue(
                title=self._title(lesson),
                body=self._body(lesson),
                labels=[
                    _MARKER_LABEL,
                    _LESSON_LABEL,
                    f"{_SOURCE_PR_LABEL_PREFIX}{lesson.source_pull_request.value}",
                    status_label,
                    *self._story_labels(lesson),
                ],
            )
        elif existing.id is not None:
            issue = self._repo.issue(int(existing.id.value))
            kept = [label.name for label in issue.labels if not self._is_mutable_label(label.name)]
            issue.set_labels(*kept, status_label, *self._conventions_labels(lesson))
            if existing.is_open and not lesson.is_open:
                self._repo.close_issue(int(existing.id.value))

        self._repo.flush()

    def _story_labels(self, lesson: Lesson) -> list[str]:
        if lesson.story_id is None:
            return []

        return [f"{_STORY_LABEL_PREFIX}{lesson.story_id.value}"]

    def _is_mutable_label(self, name: str) -> bool:
        return name.startswith(_STATUS_LABEL_PREFIX) or name.startswith(_CONVENTIONS_PR_LABEL_PREFIX)

    def _conventions_labels(self, lesson: Lesson) -> list[str]:
        if lesson.conventions_pull_request is None:
            return []

        return [f"{_CONVENTIONS_PR_LABEL_PREFIX}{lesson.conventions_pull_request.value}"]

    def search(self, status: LessonStatus | None = None, story_id: StoryId | None = None) -> list[Lesson]:
        lessons = [self._to_lesson(issue) for issue in self._lesson_issues()]

        if status is not None:
            lessons = [lesson for lesson in lessons if lesson.status == status]

        if story_id is not None:
            lessons = [lesson for lesson in lessons if lesson.story_id == story_id]

        return lessons

    def _lesson_issues(self) -> list[Issue]:
        return [
            issue for issue in self._repo.issues("all", labels=[_MARKER_LABEL, _LESSON_LABEL]) if self._is_lesson(issue)
        ]

    def _is_lesson(self, issue: Issue) -> bool:
        return any(label.name == _LESSON_LABEL for label in issue.labels)

    def _to_lesson(self, issue: Issue) -> Lesson:
        return Lesson(
            id=LessonId(str(issue.number)),
            source_pull_request=self._source_pull_request_of(issue),
            story_id=self._story_id_of(issue),
            status=self._status_of(issue),
            comments=[],
            conventions_pull_request=self._conventions_pull_request_of(issue),
            open=issue.state == "open",
        )

    def _conventions_pull_request_of(self, issue: Issue) -> ConventionsPullRequest | None:
        for label in issue.labels:
            if label.name.startswith(_CONVENTIONS_PR_LABEL_PREFIX):
                return ConventionsPullRequest(int(label.name.removeprefix(_CONVENTIONS_PR_LABEL_PREFIX)))

        return None

    def _story_id_of(self, issue: Issue) -> StoryId | None:
        for label in issue.labels:
            if label.name.startswith(_STORY_LABEL_PREFIX):
                return StoryId(label.name.removeprefix(_STORY_LABEL_PREFIX))

        return None

    def _source_pull_request_of(self, issue: Issue) -> SourcePullRequest:
        for label in issue.labels:
            if label.name.startswith(_SOURCE_PR_LABEL_PREFIX):
                return SourcePullRequest(int(label.name.removeprefix(_SOURCE_PR_LABEL_PREFIX)))

        raise ValueError(f"lesson #{issue.number} lacks its {_SOURCE_PR_LABEL_PREFIX} label")

    def _status_of(self, issue: Issue) -> LessonStatus:
        for label in issue.labels:
            if label.name.startswith(_STATUS_LABEL_PREFIX):
                value = label.name.removeprefix(_STATUS_LABEL_PREFIX)
                if value in _STATUS_VALUES:
                    return LessonStatus(value)

        raise ValueError(f"lesson #{issue.number} lacks its {_STATUS_LABEL_PREFIX} label")

    def _title(self, lesson: Lesson) -> str:
        return f"Lesson from PR #{lesson.source_pull_request.value}"

    def _body(self, lesson: Lesson) -> str:
        rendered = "\n\n".join(comment.body for comment in lesson.comments)
        header = f"Conventions refinement from the Pull Request #{lesson.source_pull_request.value}."

        return f"{header}\n\n{rendered}"
