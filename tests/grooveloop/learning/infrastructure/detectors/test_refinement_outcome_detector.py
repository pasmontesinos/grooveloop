from __future__ import annotations

from datetime import UTC, datetime

from grooveloop.learning.domain.conventions_pull_request import ConventionsPullRequest
from grooveloop.learning.domain.events import LessonDiscarded, LessonLearned
from grooveloop.learning.domain.lesson import Lesson
from grooveloop.learning.domain.lesson_comment import LessonComment
from grooveloop.learning.domain.lesson_status import LessonStatus
from grooveloop.learning.domain.refinement_outcome import RefinementOutcome
from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from grooveloop.learning.domain.story_id import StoryId
from grooveloop.learning.infrastructure.detectors.refinement_outcome_detector import RefinementOutcomeDetector
from tests.playground.shared.infrastructure.fake_lesson_repository import FakeLessonRepository
from tests.playground.shared.infrastructure.fake_refinement_result import FakeRefinementResult

_STORY = StoryId("10")


def _in_progress(
    number: int, story_id: StoryId | None = _STORY, captured_at: datetime = datetime(2026, 1, 1, tzinfo=UTC)
) -> Lesson:
    return Lesson(
        id=None,
        source_pull_request=SourcePullRequest(number),
        story_id=story_id,
        status=LessonStatus.IN_PROGRESS,
        comments=[LessonComment(body="x", path="", line=0, diff_hunk="", id=None)],
        conventions_pull_request=None,
        open=True,
        captured_at=captured_at,
    )


class TestRefinementOutcomeDetector:
    def test_asks_for_the_result_produced_since_the_capture_of_each_lesson(self) -> None:
        captured_at = datetime(2026, 10, 16, 10, 0, tzinfo=UTC)
        refinement_result = FakeRefinementResult()
        detector = RefinementOutcomeDetector(
            refinement_result=refinement_result,
            lesson_repository=FakeLessonRepository(lessons=[_in_progress(42, captured_at=captured_at)]),
        )

        list(detector.detect())

        assert refinement_result.asked == [(42, captured_at)]

    def test_emits_lesson_learned_with_the_conventions_pull_request(self) -> None:
        repository = FakeLessonRepository()
        repository.save(_in_progress(42))
        detector = RefinementOutcomeDetector(
            refinement_result=FakeRefinementResult(
                {42: RefinementOutcome(conventions_pull_request=ConventionsPullRequest(99), discarded=False)}
            ),
            lesson_repository=repository,
        )

        events = list(detector.detect())

        assert events == [
            LessonLearned(
                source_pull_request=SourcePullRequest(42),
                story_id=_STORY,
                conventions_pull_request=ConventionsPullRequest(99),
            )
        ]

    def test_emits_lesson_discarded_when_the_scribe_discards(self) -> None:
        repository = FakeLessonRepository()
        repository.save(_in_progress(42))
        detector = RefinementOutcomeDetector(
            refinement_result=FakeRefinementResult(
                {42: RefinementOutcome(conventions_pull_request=None, discarded=True)}
            ),
            lesson_repository=repository,
        )

        events = list(detector.detect())

        assert events == [LessonDiscarded(source_pull_request=SourcePullRequest(42), story_id=_STORY)]

    def test_does_not_emit_while_the_scribe_has_not_produced_a_result(self) -> None:
        repository = FakeLessonRepository()
        repository.save(_in_progress(42))
        detector = RefinementOutcomeDetector(
            refinement_result=FakeRefinementResult({}),
            lesson_repository=repository,
        )

        assert list(detector.detect()) == []

    def test_only_reconciles_lessons_still_in_progress(self) -> None:
        repository = FakeLessonRepository()
        learned = _in_progress(42)
        learned.learn(ConventionsPullRequest(99))
        repository.save(learned)
        detector = RefinementOutcomeDetector(
            refinement_result=FakeRefinementResult(
                {42: RefinementOutcome(conventions_pull_request=ConventionsPullRequest(99), discarded=False)}
            ),
            lesson_repository=repository,
        )

        assert list(detector.detect()) == []

    def test_does_not_emit_for_a_lesson_predating_the_story_label(self) -> None:
        repository = FakeLessonRepository()
        repository.save(_in_progress(42, story_id=None))
        detector = RefinementOutcomeDetector(
            refinement_result=FakeRefinementResult(
                {42: RefinementOutcome(conventions_pull_request=ConventionsPullRequest(99), discarded=False)}
            ),
            lesson_repository=repository,
        )

        assert list(detector.detect()) == []
