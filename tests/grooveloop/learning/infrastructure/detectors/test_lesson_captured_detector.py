from __future__ import annotations

from datetime import UTC, datetime

from grooveloop.learning.domain.lesson_comment import LessonComment
from grooveloop.learning.domain.lesson_status import LessonStatus
from grooveloop.learning.domain.story_id import StoryId
from grooveloop.learning.infrastructure.detectors.lesson_captured_detector import LessonCapturedDetector
from tests.grooveloop.learning.mothers.lesson_mother import LessonMother
from tests.playground.shared.infrastructure.fake_learn_signal import FakeLearnSignal
from tests.playground.shared.infrastructure.fake_lesson_repository import FakeLessonRepository


def _comments() -> list[LessonComment]:
    return [
        LessonComment(
            body="/grooveloop-learn: x",
            path="src/x.py",
            line=10,
            diff_hunk="@@ @@",
            id=None,
            written_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    ]


_CAPTURE = datetime(2026, 10, 16, 10, 0, tzinfo=UTC)


def _learn_comment(id: str, hour: int, captured: bool = False) -> LessonComment:
    return LessonComment(
        body=f"/grooveloop-learn: {id}",
        path="",
        line=0,
        diff_hunk="",
        id=id,
        written_at=datetime(2026, 10, 16, hour, 0, tzinfo=UTC),
        captured=captured,
    )


class TestLessonCapturedDetector:
    def test_emits_one_lesson_captured_per_pull_request_without_lesson(self) -> None:
        detector = LessonCapturedDetector(
            learn_signal=FakeLearnSignal({42: _comments(), 7: _comments()}),
            lesson_repository=FakeLessonRepository(),
        )

        events = list(detector.detect())

        assert [event.source_pull_request.value for event in events] == [42, 7]
        assert events[0].comments == _comments()

    def test_emits_the_story_the_pull_request_belongs_to(self) -> None:
        detector = LessonCapturedDetector(
            learn_signal=FakeLearnSignal({42: _comments()}, stories={42: "277"}),
            lesson_repository=FakeLessonRepository(),
        )

        events = list(detector.detect())

        assert events[0].story_id == StoryId("277")

    def test_does_not_read_the_comments_of_a_pull_request_with_a_lesson_in_progress(self) -> None:
        repository = FakeLessonRepository(lessons=[LessonMother.create(source_pull_request=42, captured_at=_CAPTURE)])
        signal = FakeLearnSignal({42: [_learn_comment("a", 12)], 7: _comments()})
        detector = LessonCapturedDetector(learn_signal=signal, lesson_repository=repository)

        events = list(detector.detect())

        assert [event.source_pull_request.value for event in events] == [7]
        assert signal.read == [7]

    def test_emits_nothing_for_a_pull_request_learned_before_the_marks_without_new_learn_comments(self) -> None:
        lesson = LessonMother.create(source_pull_request=42, status=LessonStatus.LEARNED, captured_at=_CAPTURE)
        detector = LessonCapturedDetector(
            learn_signal=FakeLearnSignal({42: [_learn_comment("a", 8), _learn_comment("b", 9)]}),
            lesson_repository=FakeLessonRepository(lessons=[lesson]),
        )

        assert list(detector.detect()) == []

    def test_emits_a_new_lesson_with_only_the_learn_comments_written_after_the_capture(self) -> None:
        lesson = LessonMother.create(source_pull_request=42, status=LessonStatus.DISCARDED, captured_at=_CAPTURE)
        later = _learn_comment("c", 12)
        detector = LessonCapturedDetector(
            learn_signal=FakeLearnSignal({42: [_learn_comment("a", 9), _learn_comment("b", 11, captured=True), later]}),
            lesson_repository=FakeLessonRepository(lessons=[lesson]),
        )

        events = list(detector.detect())

        assert [event.source_pull_request.value for event in events] == [42]
        assert events[0].comments == [later]

    def test_does_not_emit_when_the_pull_request_has_no_learn_comments(self) -> None:
        detector = LessonCapturedDetector(
            learn_signal=FakeLearnSignal({42: []}),
            lesson_repository=FakeLessonRepository(),
        )

        assert list(detector.detect()) == []

    def test_does_not_emit_without_any_signal(self) -> None:
        detector = LessonCapturedDetector(
            learn_signal=FakeLearnSignal(),
            lesson_repository=FakeLessonRepository(),
        )

        assert list(detector.detect()) == []
