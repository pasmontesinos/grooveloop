from __future__ import annotations

from typing import TYPE_CHECKING, Self

from grooveloop.learning.domain.exceptions import IllegalLessonTransitionError
from grooveloop.learning.domain.lesson_status import LessonStatus

if TYPE_CHECKING:
    from datetime import datetime

    from grooveloop.learning.domain.conventions_pull_request import ConventionsPullRequest
    from grooveloop.learning.domain.lesson_comment import LessonComment
    from grooveloop.learning.domain.lesson_id import LessonId
    from grooveloop.learning.domain.source_pull_request import SourcePullRequest
    from grooveloop.learning.domain.story_id import StoryId


class Lesson:
    def __init__(
        self,
        id: LessonId | None,
        source_pull_request: SourcePullRequest,
        story_id: StoryId | None,
        status: LessonStatus,
        comments: list[LessonComment],
        conventions_pull_request: ConventionsPullRequest | None,
        open: bool,
        captured_at: datetime,
    ) -> None:
        self._id = id
        self._source_pull_request = source_pull_request
        self._story_id = story_id
        self._status = status
        self._comments = comments
        self._conventions_pull_request = conventions_pull_request
        self._open = open
        self._captured_at = captured_at

    @classmethod
    def create(
        cls,
        source_pull_request: SourcePullRequest,
        story_id: StoryId,
        comments: list[LessonComment],
        captured_at: datetime,
    ) -> Self:
        return cls(
            id=None,
            source_pull_request=source_pull_request,
            story_id=story_id,
            status=LessonStatus.IN_PROGRESS,
            comments=comments,
            conventions_pull_request=None,
            open=True,
            captured_at=captured_at,
        )

    @property
    def id(self) -> LessonId | None:
        return self._id

    @property
    def source_pull_request(self) -> SourcePullRequest:
        return self._source_pull_request

    @property
    def story_id(self) -> StoryId | None:
        return self._story_id

    @property
    def status(self) -> LessonStatus:
        return self._status

    @property
    def comments(self) -> list[LessonComment]:
        return self._comments

    @property
    def conventions_pull_request(self) -> ConventionsPullRequest | None:
        return self._conventions_pull_request

    @property
    def is_open(self) -> bool:
        return self._open

    @property
    def captured_at(self) -> datetime:
        return self._captured_at

    def is_in_progress(self) -> bool:
        return self._status is LessonStatus.IN_PROGRESS

    def is_resolved(self, conventions_pull_request_open: bool) -> bool:
        if self._status is LessonStatus.DISCARDED:
            return True

        if self._status is LessonStatus.LEARNED and self._conventions_pull_request is not None:
            return not conventions_pull_request_open

        return False

    def learn(self, conventions_pull_request: ConventionsPullRequest) -> None:
        self._guard_in_progress(LessonStatus.LEARNED)
        self._status = LessonStatus.LEARNED
        self._conventions_pull_request = conventions_pull_request

    def discard(self) -> None:
        self._guard_in_progress(LessonStatus.DISCARDED)
        self._status = LessonStatus.DISCARDED

    def close(self) -> None:
        self._open = False

    def _guard_in_progress(self, target: LessonStatus) -> None:
        if self._status is not LessonStatus.IN_PROGRESS:
            raise IllegalLessonTransitionError(
                f"Cannot move lesson for pull request {self._source_pull_request.value} from {self._status} to {target}"
            )
