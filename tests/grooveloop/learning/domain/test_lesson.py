from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from grooveloop.learning.domain.conventions_pull_request import ConventionsPullRequest
from grooveloop.learning.domain.exceptions import IllegalLessonTransitionError
from grooveloop.learning.domain.lesson import Lesson
from grooveloop.learning.domain.lesson_comment import LessonComment
from grooveloop.learning.domain.lesson_status import LessonStatus
from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from grooveloop.learning.domain.story_id import StoryId

_comments = st.lists(
    st.builds(
        LessonComment,
        body=st.text(),
        path=st.text(),
        line=st.integers(min_value=0),
        diff_hunk=st.text(),
    ),
    min_size=1,
    max_size=5,
)


class TestLesson:
    @given(number=st.integers(min_value=1), comments=_comments)
    def test_create_starts_in_progress_without_identity_aggregating_every_comment(
        self, number: int, comments: list[LessonComment]
    ) -> None:
        lesson = Lesson.create(SourcePullRequest(number), StoryId("10"), comments)

        assert lesson.id is None
        assert lesson.status == LessonStatus.IN_PROGRESS
        assert lesson.source_pull_request == SourcePullRequest(number)
        assert lesson.comments == comments
        assert lesson.conventions_pull_request is None
        assert lesson.is_open is True

    def test_learn_moves_to_learned_keeping_the_conventions_pull_request(self) -> None:
        lesson = Lesson.create(
            SourcePullRequest(42), StoryId("10"), [LessonComment(body="x", path="", line=0, diff_hunk="")]
        )

        lesson.learn(ConventionsPullRequest(99))

        assert lesson.status == LessonStatus.LEARNED
        assert lesson.conventions_pull_request == ConventionsPullRequest(99)

    def test_discard_moves_to_discarded_without_conventions_pull_request(self) -> None:
        lesson = Lesson.create(
            SourcePullRequest(42), StoryId("10"), [LessonComment(body="x", path="", line=0, diff_hunk="")]
        )

        lesson.discard()

        assert lesson.status == LessonStatus.DISCARDED
        assert lesson.conventions_pull_request is None

    def test_learn_is_rejected_when_the_lesson_is_no_longer_in_progress(self) -> None:
        lesson = Lesson.create(
            SourcePullRequest(42), StoryId("10"), [LessonComment(body="x", path="", line=0, diff_hunk="")]
        )
        lesson.discard()

        with pytest.raises(IllegalLessonTransitionError):
            lesson.learn(ConventionsPullRequest(99))

    def test_discard_is_rejected_when_the_lesson_is_no_longer_in_progress(self) -> None:
        lesson = Lesson.create(
            SourcePullRequest(42), StoryId("10"), [LessonComment(body="x", path="", line=0, diff_hunk="")]
        )
        lesson.learn(ConventionsPullRequest(99))

        with pytest.raises(IllegalLessonTransitionError):
            lesson.discard()
