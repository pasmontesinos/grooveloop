from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.delivery.domain.slice_id import SliceId


class SliceLabels(ABC):
    @abstractmethod
    def ensure(self, slice_id: SliceId) -> None: ...
