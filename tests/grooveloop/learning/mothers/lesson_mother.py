from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.learning.domain.lesson import Lesson
from grooveloop.learning.domain.lesson_comment import LessonComment
from grooveloop.learning.domain.lesson_id import LessonId
from grooveloop.learning.domain.lesson_status import LessonStatus
from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from grooveloop.learning.domain.story_id import StoryId

if TYPE_CHECKING:
    from grooveloop.learning.domain.conventions_pull_request import ConventionsPullRequest


class LessonMother:
    @staticmethod
    def create(
        lesson_id: str | None = None,
        source_pull_request: int = 42,
        story_id: str | None = "10",
        status: LessonStatus = LessonStatus.IN_PROGRESS,
        comments: list[LessonComment] | None = None,
        conventions_pull_request: ConventionsPullRequest | None = None,
        open: bool = True,
    ) -> Lesson:
        return Lesson(
            id=LessonId(lesson_id) if lesson_id is not None else None,
            source_pull_request=SourcePullRequest(source_pull_request),
            story_id=StoryId(story_id) if story_id is not None else None,
            status=status,
            comments=comments if comments is not None else [LessonComment(body="x", path="", line=0, diff_hunk="")],
            conventions_pull_request=conventions_pull_request,
            open=open,
        )
