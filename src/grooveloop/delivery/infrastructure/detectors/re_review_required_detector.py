from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.domain.events import ReReviewRequired
from grooveloop.delivery.domain.slice_status import SliceStatus

if TYPE_CHECKING:
    from collections.abc import Iterator

    from grooveloop.delivery.domain.slice_repository import SliceRepository


class ReReviewRequiredDetector:
    def __init__(self, slice_repository: SliceRepository) -> None:
        self._slice_repository = slice_repository

    def detect(self) -> Iterator[ReReviewRequired]:
        for a_slice in self._slice_repository.search(status=SliceStatus.CHANGES_REQUESTED, open=True):
            pull_request = a_slice.pull_request
            if pull_request is None or not a_slice.has_commits_after_review():
                continue

            yield ReReviewRequired(slice_id=a_slice.id, pull_request_number=pull_request.number)
