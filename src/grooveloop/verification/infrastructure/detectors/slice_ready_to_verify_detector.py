from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.verification.domain.events import SliceReadyToVerify
from grooveloop.verification.domain.verification_status import VerificationStatus

if TYPE_CHECKING:
    from collections.abc import Iterator

    from grooveloop.verification.domain.merged_slice_signal import MergedSliceSignal
    from grooveloop.verification.domain.slice_verification_repository import SliceVerificationRepository


class SliceReadyToVerifyDetector:
    def __init__(
        self,
        merged_slice_signal: MergedSliceSignal,
        slice_verification_repository: SliceVerificationRepository,
    ) -> None:
        self._merged_slice_signal = merged_slice_signal
        self._slice_verification_repository = slice_verification_repository

    def detect(self) -> Iterator[SliceReadyToVerify]:
        not_started = {
            verification.slice_id
            for verification in self._slice_verification_repository.search(status=VerificationStatus.EMPTY)
        }

        for merged_slice in self._merged_slice_signal.merged_slices():
            if merged_slice.slice_id in not_started:
                yield SliceReadyToVerify(
                    slice_id=merged_slice.slice_id,
                    pull_request_number=merged_slice.pull_request_number,
                    title=merged_slice.title,
                    description=merged_slice.description,
                )
