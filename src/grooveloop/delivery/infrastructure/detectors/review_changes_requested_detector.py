from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.domain.events import ReviewChangesRequested

if TYPE_CHECKING:
    from collections.abc import Iterator

    from grooveloop.delivery.domain.slice_repository import SliceRepository


class ReviewChangesRequestedDetector:
    def __init__(self, slice_repository: SliceRepository) -> None:
        self._slice_repository = slice_repository

    def detect(self) -> Iterator[ReviewChangesRequested]:
        for a_slice in self._slice_repository.search(open=True):
            if a_slice.awaits_requested_changes():
                yield ReviewChangesRequested(slice_id=a_slice.id)
