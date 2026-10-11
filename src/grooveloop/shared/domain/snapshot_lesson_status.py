from __future__ import annotations

from enum import StrEnum


class SnapshotLessonStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    LEARNED = "learned"
    DISCARDED = "discarded"
