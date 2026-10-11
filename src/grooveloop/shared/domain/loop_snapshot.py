from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.shared.domain.snapshot_story import SnapshotStory
    from grooveloop.shared.domain.snapshot_tick import SnapshotTick


@dataclass(frozen=True)
class LoopSnapshot:
    repo: str
    tick: SnapshotTick
    stories: list[SnapshotStory]
