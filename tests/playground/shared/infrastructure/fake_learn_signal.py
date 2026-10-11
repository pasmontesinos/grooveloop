from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.learning.domain.learn_signal import LearnSignal
from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from grooveloop.learning.domain.story_id import StoryId

if TYPE_CHECKING:
    from grooveloop.learning.domain.lesson_comment import LessonComment

_DEFAULT_STORY = "10"


class FakeLearnSignal(LearnSignal):
    def __init__(
        self, comments: dict[int, list[LessonComment]] | None = None, stories: dict[int, str] | None = None
    ) -> None:
        self._comments = dict(comments or {})
        self._stories = dict(stories or {})
        self.read: list[int] = []

    def merged_pull_requests(self) -> list[SourcePullRequest]:
        return [SourcePullRequest(number) for number in self._comments]

    def story_of(self, source_pull_request: SourcePullRequest) -> StoryId:
        return StoryId(self._stories.get(source_pull_request.value, _DEFAULT_STORY))

    def comments_of(self, source_pull_request: SourcePullRequest) -> list[LessonComment]:
        self.read.append(source_pull_request.value)

        return list(self._comments.get(source_pull_request.value, []))
