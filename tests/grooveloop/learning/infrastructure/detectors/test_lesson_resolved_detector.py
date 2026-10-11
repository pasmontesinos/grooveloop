from __future__ import annotations

from grooveloop.learning.domain.conventions_pull_request import ConventionsPullRequest
from grooveloop.learning.domain.events import LessonResolved
from grooveloop.learning.domain.lesson import Lesson
from grooveloop.learning.domain.lesson_id import LessonId
from grooveloop.learning.domain.lesson_status import LessonStatus
from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from grooveloop.learning.domain.story_id import StoryId
from grooveloop.learning.infrastructure.detectors.lesson_resolved_detector import LessonResolvedDetector
from tests.playground.shared.infrastructure.fake_conventions_pull_request_status import (
    FakeConventionsPullRequestStatus,
)
from tests.playground.shared.infrastructure.fake_lesson_repository import FakeLessonRepository

_STORY = StoryId("10")


def _lesson(
    number: int,
    status: LessonStatus,
    conventions_pull_request: int | None = None,
    open: bool = True,
    story_id: StoryId | None = _STORY,
) -> Lesson:
    return Lesson(
        id=LessonId(str(number + 1000)),
        source_pull_request=SourcePullRequest(number),
        story_id=story_id,
        status=status,
        comments=[],
        conventions_pull_request=(
            ConventionsPullRequest(conventions_pull_request) if conventions_pull_request is not None else None
        ),
        open=open,
    )


class TestLessonResolvedDetector:
    def test_emits_resolved_for_a_discarded_lesson_with_an_open_sub_issue(self) -> None:
        repository = FakeLessonRepository(lessons=[_lesson(42, LessonStatus.DISCARDED)])
        detector = LessonResolvedDetector(
            lesson_repository=repository,
            conventions_pull_request_status=FakeConventionsPullRequestStatus(),
        )

        assert list(detector.detect()) == [LessonResolved(lesson_id=LessonId("1042"), story_id=_STORY)]

    def test_emits_resolved_for_a_learned_lesson_whose_conventions_pull_request_is_resolved(self) -> None:
        repository = FakeLessonRepository(lessons=[_lesson(42, LessonStatus.LEARNED, conventions_pull_request=101)])
        detector = LessonResolvedDetector(
            lesson_repository=repository,
            conventions_pull_request_status=FakeConventionsPullRequestStatus(open_pull_requests=set()),
        )

        assert list(detector.detect()) == [LessonResolved(lesson_id=LessonId("1042"), story_id=_STORY)]

    def test_does_not_emit_for_a_learned_lesson_with_an_open_conventions_pull_request(self) -> None:
        repository = FakeLessonRepository(lessons=[_lesson(42, LessonStatus.LEARNED, conventions_pull_request=101)])
        detector = LessonResolvedDetector(
            lesson_repository=repository,
            conventions_pull_request_status=FakeConventionsPullRequestStatus(open_pull_requests={101}),
        )

        assert list(detector.detect()) == []

    def test_does_not_emit_for_an_in_progress_lesson(self) -> None:
        repository = FakeLessonRepository(lessons=[_lesson(42, LessonStatus.IN_PROGRESS)])
        detector = LessonResolvedDetector(
            lesson_repository=repository,
            conventions_pull_request_status=FakeConventionsPullRequestStatus(),
        )

        assert list(detector.detect()) == []

    def test_does_not_emit_for_a_resolved_lesson_whose_sub_issue_is_already_closed(self) -> None:
        repository = FakeLessonRepository(lessons=[_lesson(42, LessonStatus.DISCARDED, open=False)])
        detector = LessonResolvedDetector(
            lesson_repository=repository,
            conventions_pull_request_status=FakeConventionsPullRequestStatus(),
        )

        assert list(detector.detect()) == []

    def test_does_not_emit_for_a_lesson_predating_the_story_label(self) -> None:
        repository = FakeLessonRepository(lessons=[_lesson(42, LessonStatus.DISCARDED, story_id=None)])
        detector = LessonResolvedDetector(
            lesson_repository=repository,
            conventions_pull_request_status=FakeConventionsPullRequestStatus(),
        )

        assert list(detector.detect()) == []
