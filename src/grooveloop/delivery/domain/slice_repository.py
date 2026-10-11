from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.delivery.domain.slice import Slice
    from grooveloop.delivery.domain.slice_id import SliceId
    from grooveloop.delivery.domain.slice_status import SliceStatus
    from grooveloop.delivery.domain.story_id import StoryId


class SliceRepository(ABC):
    @abstractmethod
    def find(self, id: SliceId) -> Slice | None: ...

    @abstractmethod
    def save(self, a_slice: Slice) -> None: ...

    @abstractmethod
    def search(
        self, story_id: StoryId | None = None, status: SliceStatus | None = None, open: bool | None = None
    ) -> list[Slice]: ...
