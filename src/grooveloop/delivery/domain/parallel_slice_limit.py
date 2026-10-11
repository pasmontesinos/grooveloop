from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.delivery.domain.slice import Slice


@dataclass(frozen=True)
class ParallelSliceLimit:
    value: int

    def is_reached_by(self, story_slices: list[Slice]) -> bool:
        in_progress = [a_slice for a_slice in story_slices if a_slice.is_in_progress()]

        return len(in_progress) >= self.value
