from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.domain.snapshot_slice_status import SnapshotSliceStatus

if TYPE_CHECKING:
    from grooveloop.shared.domain.snapshot_slice import SnapshotSlice


def learning_gate(slices: list[SnapshotSlice], pending: set[int]) -> tuple[int, int] | None:
    for index, a_slice in enumerate(slices):
        previous = slices[:index]
        if a_slice.status is not SnapshotSliceStatus.PENDING:
            continue

        if not all(dependency.status is SnapshotSliceStatus.MERGED for dependency in previous):
            return None

        blocking = [
            order
            for order, dependency in enumerate(previous, start=1)
            if dependency.pr_number is not None and int(dependency.pr_number) in pending
        ]
        if len(blocking) == 0:
            return None

        return index + 1, blocking[0]

    return None
