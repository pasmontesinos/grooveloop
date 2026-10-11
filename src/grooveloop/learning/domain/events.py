from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.shared.domain.event import Event

if TYPE_CHECKING:
    from grooveloop.learning.domain.conventions_pull_request import ConventionsPullRequest
    from grooveloop.learning.domain.lesson_comment import LessonComment
    from grooveloop.learning.domain.lesson_id import LessonId
    from grooveloop.learning.domain.source_pull_request import SourcePullRequest
    from grooveloop.learning.domain.story_id import StoryId


@dataclass(frozen=True)
class LessonCaptured(Event):
    source_pull_request: SourcePullRequest
    story_id: StoryId
    comments: list[LessonComment]


@dataclass(frozen=True)
class LessonLearned(Event):
    source_pull_request: SourcePullRequest
    story_id: StoryId
    conventions_pull_request: ConventionsPullRequest


@dataclass(frozen=True)
class LessonDiscarded(Event):
    source_pull_request: SourcePullRequest
    story_id: StoryId


@dataclass(frozen=True)
class LessonResolved(Event):
    lesson_id: LessonId
    story_id: StoryId
