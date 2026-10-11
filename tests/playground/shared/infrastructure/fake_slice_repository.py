from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.domain.slice_repository import SliceRepository

if TYPE_CHECKING:
    from grooveloop.delivery.domain.slice import Slice
    from grooveloop.delivery.domain.slice_id import SliceId
    from grooveloop.delivery.domain.slice_status import SliceStatus
    from grooveloop.delivery.domain.story_id import StoryId


class FakeSliceRepository(SliceRepository):
    def __init__(
        self,
        by_story: dict[StoryId, list[Slice]],
        closed: set[SliceId] | None = None,
    ) -> None:
        self._by_story = by_story
        self._by_id = {a_slice.id: a_slice for slices in by_story.values() for a_slice in slices}
        self._closed = closed or set()

    def find(self, id: SliceId) -> Slice | None:
        return self._by_id.get(id)

    def save(self, a_slice: Slice) -> None:
        self._by_id[a_slice.id] = a_slice

    def search(
        self, story_id: StoryId | None = None, status: SliceStatus | None = None, open: bool | None = None
    ) -> list[Slice]:
        slices = self._by_story.get(story_id, []) if story_id is not None else list(self._by_id.values())

        if open is not None:
            slices = [a_slice for a_slice in slices if (a_slice.id not in self._closed) is open]

        if status is not None:
            slices = [a_slice for a_slice in slices if a_slice.status == status]

        return slices
