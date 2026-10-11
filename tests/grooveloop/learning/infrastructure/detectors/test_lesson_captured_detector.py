from __future__ import annotations

from grooveloop.learning.domain.lesson_comment import LessonComment
from grooveloop.learning.domain.story_id import StoryId
from grooveloop.learning.infrastructure.detectors.lesson_captured_detector import LessonCapturedDetector
from tests.grooveloop.learning.mothers.lesson_mother import LessonMother
from tests.playground.shared.infrastructure.fake_learn_signal import FakeLearnSignal
from tests.playground.shared.infrastructure.fake_lesson_repository import FakeLessonRepository


def _comments() -> list[LessonComment]:
    return [LessonComment(body="/grooveloop-learn: x", path="src/x.py", line=10, diff_hunk="@@ @@")]


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

    def test_does_not_read_the_comments_of_a_pull_request_that_already_has_a_lesson(self) -> None:
        repository = FakeLessonRepository()
        repository.save(LessonMother.create(source_pull_request=42, story_id="10", comments=_comments()))
        signal = FakeLearnSignal({42: _comments(), 7: _comments()})
        detector = LessonCapturedDetector(learn_signal=signal, lesson_repository=repository)

        events = list(detector.detect())

        assert [event.source_pull_request.value for event in events] == [7]
        assert signal.read == [7]

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
