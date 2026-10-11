from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.shared.domain.snapshot_lesson import SnapshotLesson
    from grooveloop.shared.domain.snapshot_slice import SnapshotSlice
    from grooveloop.shared.domain.snapshot_story_status import SnapshotStoryStatus


@dataclass(frozen=True)
class SnapshotStory:
    number: str
    status: SnapshotStoryStatus
    title: str
    slices: list[SnapshotSlice]
    lessons: list[SnapshotLesson]
