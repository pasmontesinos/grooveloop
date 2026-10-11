from __future__ import annotations

from grooveloop.delivery.application.queries.next_dispatchable_slices import (
    NextDispatchableSlicesQuery,
    NextDispatchableSlicesQueryHandler,
)
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository


class TestNextDispatchableSlicesQueryHandler:
    def test_should_return_the_first_pending_slice_when_every_previous_slice_is_merged(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(slice_id="11", status=SliceStatus.MERGED, story_id="10"),
                    SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10"),
                ]
            }
        )
        handler = NextDispatchableSlicesQueryHandler(slice_repository=repository)

        result = handler(NextDispatchableSlicesQuery(story_id="10"))

        assert [dto.id for dto in result.slices] == ["12"]

    def test_should_not_return_a_pending_slice_when_a_previous_slice_is_not_merged(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(slice_id="11", status=SliceStatus.PR_OPEN, story_id="10"),
                    SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10"),
                ]
            }
        )
        handler = NextDispatchableSlicesQueryHandler(slice_repository=repository)

        result = handler(NextDispatchableSlicesQuery(story_id="10"))

        assert result.slices == []

    def test_should_return_a_slice_whose_declared_dependency_is_merged_even_if_another_previous_slice_is_not(
        self,
    ) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(slice_id="11", status=SliceStatus.MERGED, story_id="10"),
                    SliceMother.create(slice_id="12", status=SliceStatus.PR_OPEN, story_id="10"),
                    SliceMother.create(
                        slice_id="13", status=SliceStatus.PENDING, story_id="10", depends_on=[SliceId("11")]
                    ),
                ]
            }
        )
        handler = NextDispatchableSlicesQueryHandler(slice_repository=repository)

        result = handler(NextDispatchableSlicesQuery(story_id="10"))

        assert [dto.id for dto in result.slices] == ["13"]

    def test_should_see_a_merged_dependency_even_when_it_is_already_closed(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(slice_id="11", status=SliceStatus.MERGED, story_id="10"),
                    SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10"),
                ]
            },
            closed={SliceId("11")},
        )
        handler = NextDispatchableSlicesQueryHandler(slice_repository=repository)

        result = handler(NextDispatchableSlicesQuery(story_id="10"))

        assert [dto.id for dto in result.slices] == ["12"]
