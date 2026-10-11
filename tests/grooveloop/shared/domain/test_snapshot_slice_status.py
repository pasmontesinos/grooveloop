from __future__ import annotations

from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.shared.domain.snapshot_slice_status import SnapshotSliceStatus


class TestSnapshotSliceStatus:
    def test_should_publish_the_same_values_as_the_slice_life_cycle(self) -> None:
        assert [status.value for status in SnapshotSliceStatus] == [status.value for status in SliceStatus]
