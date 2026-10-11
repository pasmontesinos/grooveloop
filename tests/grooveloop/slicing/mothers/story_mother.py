from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.slicing.domain.slice_spec_item import SliceSpecItem
from grooveloop.slicing.domain.spec import Spec
from grooveloop.slicing.domain.story import Story
from grooveloop.slicing.domain.story_id import StoryId
from grooveloop.slicing.domain.story_status import StoryStatus

if TYPE_CHECKING:
    from grooveloop.slicing.domain.slice import Slice


class StoryMother:
    @staticmethod
    def create(
        story_id: str = "story-1",
        status: StoryStatus = StoryStatus.READY_FOR_IMPLEMENTATION,
        slice_count: int = 1,
        slices: list[Slice] | None = None,
    ) -> Story:
        spec = Spec(items=[SliceSpecItem(title=f"slice {index}", order=index) for index in range(1, slice_count + 1)])

        return Story(id=StoryId(story_id), spec=spec, status=status, slices=slices or [])
