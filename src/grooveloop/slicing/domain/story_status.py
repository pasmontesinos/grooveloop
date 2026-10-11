from __future__ import annotations

from enum import StrEnum


class StoryStatus(StrEnum):
    DRAFT = "draft"
    READY_FOR_IMPLEMENTATION = "ready_for_implementation"
    SLICED = "sliced"
    IN_PROGRESS = "in_progress"
    DONE = "done"
