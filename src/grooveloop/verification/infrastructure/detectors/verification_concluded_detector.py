from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.verification.domain.events import VerificationConcluded
from grooveloop.verification.domain.verification_status import VerificationStatus

if TYPE_CHECKING:
    from collections.abc import Iterator

    from grooveloop.verification.domain.merged_slice_signal import MergedSliceSignal
    from grooveloop.verification.domain.slice_verification_repository import SliceVerificationRepository


class VerificationConcludedDetector:
    def __init__(
        self,
        merged_slice_signal: MergedSliceSignal,
        slice_verification_repository: SliceVerificationRepository,
    ) -> None:
        self._merged_slice_signal = merged_slice_signal
        self._slice_verification_repository = slice_verification_repository

    def detect(self) -> Iterator[VerificationConcluded]:
        running = {
            verification.slice_id
            for verification in self._slice_verification_repository.search(status=VerificationStatus.RUNNING)
        }

        for merged_slice in self._merged_slice_signal.merged_slices():
            if merged_slice.has_report and merged_slice.slice_id in running:
                yield VerificationConcluded(slice_id=merged_slice.slice_id)
