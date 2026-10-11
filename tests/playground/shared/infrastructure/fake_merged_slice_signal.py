from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.verification.domain.merged_slice_signal import MergedSliceSignal

if TYPE_CHECKING:
    from grooveloop.verification.domain.merged_slice import MergedSlice


class FakeMergedSliceSignal(MergedSliceSignal):
    def __init__(self, merged_slices: list[MergedSlice] | None = None) -> None:
        self._merged_slices = merged_slices or []

    def merged_slices(self) -> list[MergedSlice]:
        return self._merged_slices
