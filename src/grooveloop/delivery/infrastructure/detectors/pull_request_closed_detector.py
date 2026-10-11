from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.domain.events import PullRequestClosed

if TYPE_CHECKING:
    from collections.abc import Iterator

    from grooveloop.delivery.domain.slice_repository import SliceRepository


class PullRequestClosedDetector:
    def __init__(self, slice_repository: SliceRepository) -> None:
        self._slice_repository = slice_repository

    def detect(self) -> Iterator[PullRequestClosed]:
        for a_slice in self._slice_repository.search():
            if not a_slice.can_be_closed_without_merge():
                continue

            pull_request = a_slice.pull_request
            if pull_request is not None and pull_request.is_closed_without_merge():
                yield PullRequestClosed(slice_id=a_slice.id)
