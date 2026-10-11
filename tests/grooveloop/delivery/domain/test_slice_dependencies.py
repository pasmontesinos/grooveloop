from __future__ import annotations

from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_status import SliceStatus
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother


class TestSliceDispatchability:
    def test_should_be_dispatchable_when_pending_and_has_no_previous_slices(self) -> None:
        a_slice = SliceMother.create(slice_id="11", status=SliceStatus.PENDING)

        assert a_slice.is_dispatchable([a_slice]) is True

    def test_should_not_be_dispatchable_when_not_pending(self) -> None:
        a_slice = SliceMother.create(slice_id="11", status=SliceStatus.DISPATCHED)

        assert a_slice.is_dispatchable([a_slice]) is False

    def test_should_not_be_dispatchable_without_marker_when_a_previous_slice_is_not_merged(self) -> None:
        previous = SliceMother.create(slice_id="11", status=SliceStatus.DISPATCHED)
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.PENDING)

        assert a_slice.is_dispatchable([previous, a_slice]) is False

    def test_should_be_dispatchable_without_marker_when_every_previous_slice_is_merged(self) -> None:
        previous = SliceMother.create(slice_id="11", status=SliceStatus.MERGED)
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.PENDING)

        assert a_slice.is_dispatchable([previous, a_slice]) is True

    def test_should_be_dispatchable_when_declared_dependencies_are_merged_even_if_another_previous_slice_is_not(
        self,
    ) -> None:
        merged_dependency = SliceMother.create(slice_id="11", status=SliceStatus.MERGED)
        unrelated_previous = SliceMother.create(slice_id="12", status=SliceStatus.PR_OPEN)
        a_slice = SliceMother.create(slice_id="13", status=SliceStatus.PENDING, depends_on=[SliceId("11")])

        assert a_slice.is_dispatchable([merged_dependency, unrelated_previous, a_slice]) is True

    def test_should_not_be_dispatchable_when_a_declared_dependency_is_not_merged(self) -> None:
        pending_dependency = SliceMother.create(slice_id="11", status=SliceStatus.PR_OPEN)
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.PENDING, depends_on=[SliceId("11")])

        assert a_slice.is_dispatchable([pending_dependency, a_slice]) is False

    def test_should_not_be_dispatchable_when_a_declared_dependency_does_not_resolve(self) -> None:
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.PENDING, depends_on=[SliceId("999")])

        assert a_slice.is_dispatchable([a_slice]) is False

    def test_should_be_dispatchable_when_declared_independent_and_a_previous_slice_is_not_merged(self) -> None:
        previous = SliceMother.create(slice_id="11", status=SliceStatus.PR_OPEN)
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.PENDING, depends_on=[])

        assert a_slice.is_dispatchable([previous, a_slice]) is True

    def test_should_report_no_dependencies_when_declared_independent(self) -> None:
        previous = SliceMother.create(slice_id="11", status=SliceStatus.PR_OPEN)
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.PENDING, depends_on=[])

        assert a_slice.dependencies([previous, a_slice]) == []
