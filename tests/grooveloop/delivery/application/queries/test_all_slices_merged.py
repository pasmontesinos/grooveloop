from __future__ import annotations

from grooveloop.delivery.application.queries.all_slices_merged import AllSlicesMergedQueryHandler
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.shared.application.queries.all_slices_merged import AllSlicesMergedQuery
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository


class TestAllSlicesMergedQueryHandler:
    def test_should_report_merged_when_every_slice_is_merged(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(slice_id="11", status=SliceStatus.MERGED),
                    SliceMother.create(slice_id="12", status=SliceStatus.MERGED),
                ]
            }
        )
        handler = AllSlicesMergedQueryHandler(slice_repository=repository)

        result = handler(AllSlicesMergedQuery(story_id="10"))

        assert result.all_merged is True

    def test_should_report_not_merged_when_any_slice_is_pending(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(slice_id="11", status=SliceStatus.MERGED),
                    SliceMother.create(slice_id="12", status=SliceStatus.PENDING),
                ]
            }
        )
        handler = AllSlicesMergedQueryHandler(slice_repository=repository)

        result = handler(AllSlicesMergedQuery(story_id="10"))

        assert result.all_merged is False

    def test_should_report_not_merged_when_the_story_has_no_slices(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): []})
        handler = AllSlicesMergedQueryHandler(slice_repository=repository)

        result = handler(AllSlicesMergedQuery(story_id="10"))

        assert result.all_merged is False
