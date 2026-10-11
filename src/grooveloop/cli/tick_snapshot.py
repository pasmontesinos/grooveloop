from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from grooveloop.learning.application.queries.story_lessons import StoryLessonsQuery
from grooveloop.shared.domain.loop_snapshot import LoopSnapshot
from grooveloop.shared.domain.snapshot_lesson import SnapshotLesson
from grooveloop.shared.domain.snapshot_lesson_status import SnapshotLessonStatus
from grooveloop.shared.domain.snapshot_slice_status import SnapshotSliceStatus

if TYPE_CHECKING:
    from grooveloop.cli.story_snapshot import StorySnapshot
    from grooveloop.learning.application.queries.story_lessons import (
        StoryLessonDTO,
        StoryLessonsQueryHandler,
    )
    from grooveloop.shared.domain.loop_snapshots import LoopSnapshots
    from grooveloop.shared.domain.snapshot_story import SnapshotStory
    from grooveloop.shared.domain.snapshot_tick import SnapshotTick


@dataclass(frozen=True)
class SnapshotSource:
    stories: StorySnapshot
    lessons: StoryLessonsQueryHandler


class TickSnapshot:
    def __init__(self, snapshots: LoopSnapshots, repo: str, source: SnapshotSource | None) -> None:
        self._snapshots = snapshots
        self._repo = repo
        self._source = source

    def publish(self, tick: SnapshotTick) -> None:
        self._snapshots.publish(LoopSnapshot(repo=self._repo, tick=tick, stories=self._read()))

    def _read(self) -> list[SnapshotStory]:
        if self._source is None:
            return []

        try:
            return [self._with_lessons(story, self._source) for story in self._source.stories.read()]
        except Exception as error:
            print(f"[warn] tick snapshot read failed in {self._repo}: {error}", file=sys.stderr)

            return []

    def _with_lessons(self, story: SnapshotStory, source: SnapshotSource) -> SnapshotStory:
        return replace(story, lessons=[_lesson(lesson) for lesson in _lessons_of(story, source)])


def _lessons_of(story: SnapshotStory, source: SnapshotSource) -> list[StoryLessonDTO]:
    merged = [a_slice for a_slice in story.slices if a_slice.status is SnapshotSliceStatus.MERGED]
    if len(merged) == 0:
        return []

    return source.lessons(StoryLessonsQuery(story_id=story.number)).lessons


def _lesson(lesson: StoryLessonDTO) -> SnapshotLesson:
    return SnapshotLesson(
        number=lesson.number,
        source_pull_request_number=lesson.source_pull_request_number,
        status=SnapshotLessonStatus(lesson.status),
        conventions_pull_request_number=lesson.conventions_pull_request_number,
        resolved=lesson.resolved,
    )
