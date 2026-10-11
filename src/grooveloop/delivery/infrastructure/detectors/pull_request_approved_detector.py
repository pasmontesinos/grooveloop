from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.domain.events import PullRequestApproved
from grooveloop.delivery.domain.slice_status import SliceStatus

if TYPE_CHECKING:
    from collections.abc import Iterator

    from grooveloop.delivery.domain.slice_repository import SliceRepository
    from grooveloop.delivery.infrastructure.auto_merge import AutoMerge


class PullRequestApprovedDetector:
    def __init__(self, slice_repository: SliceRepository, auto_merge: AutoMerge) -> None:
        self._slice_repository = slice_repository
        self._auto_merge = auto_merge

    def detect(self) -> Iterator[PullRequestApproved]:
        if not self._auto_merge.value:
            return

        for a_slice in self._slice_repository.search(status=SliceStatus.PR_OPEN, open=True):
            if a_slice.is_auto_mergeable():
                yield PullRequestApproved(slice_id=a_slice.id)
