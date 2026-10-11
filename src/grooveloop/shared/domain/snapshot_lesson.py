from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.shared.domain.snapshot_lesson_status import SnapshotLessonStatus


@dataclass(frozen=True)
class SnapshotLesson:
    number: str | None
    source_pull_request_number: int
    status: SnapshotLessonStatus
    conventions_pull_request_number: int | None
    resolved: bool
