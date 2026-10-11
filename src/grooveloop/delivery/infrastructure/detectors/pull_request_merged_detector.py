from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.domain.events import PullRequestMerged

if TYPE_CHECKING:
    from collections.abc import Iterator

    from grooveloop.delivery.domain.slice_repository import SliceRepository


class PullRequestMergedDetector:
    def __init__(self, slice_repository: SliceRepository) -> None:
        self._slice_repository = slice_repository

    def detect(self) -> Iterator[PullRequestMerged]:
        for a_slice in self._slice_repository.search():
            if not a_slice.can_be_merged():
                continue

            pull_request = a_slice.pull_request
            if pull_request is not None and pull_request.is_merged():
                yield PullRequestMerged(slice_id=a_slice.id)
