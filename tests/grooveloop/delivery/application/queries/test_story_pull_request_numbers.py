from __future__ import annotations

from grooveloop.delivery.application.queries.story_pull_request_numbers import (
    StoryPullRequestNumbersQueryHandler,
)
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.shared.application.queries.story_pull_request_numbers import StoryPullRequestNumbersQuery
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository


class TestStoryPullRequestNumbersQueryHandler:
    def test_returns_the_pull_request_numbers_of_the_story_slices(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(slice_id="11", status=SliceStatus.MERGED, pull_request_number=100),
                    SliceMother.create(slice_id="12", status=SliceStatus.MERGED, pull_request_number=101),
                ]
            }
        )
        handler = StoryPullRequestNumbersQueryHandler(slice_repository=repository)

        result = handler(StoryPullRequestNumbersQuery(story_id="10"))

        assert result.pull_request_numbers == [100, 101]

    def test_omits_slices_without_a_pull_request(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(slice_id="11", status=SliceStatus.MERGED, pull_request_number=100),
                    SliceMother.create(slice_id="12", status=SliceStatus.PENDING),
                ]
            }
        )
        handler = StoryPullRequestNumbersQueryHandler(slice_repository=repository)

        result = handler(StoryPullRequestNumbersQuery(story_id="10"))

        assert result.pull_request_numbers == [100]

    def test_returns_empty_for_a_story_without_slices(self) -> None:
        repository = FakeSliceRepository({})
        handler = StoryPullRequestNumbersQueryHandler(slice_repository=repository)

        result = handler(StoryPullRequestNumbersQuery(story_id="10"))

        assert result.pull_request_numbers == []
