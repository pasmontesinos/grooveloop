from __future__ import annotations

from grooveloop.delivery.application.commands.complete_review import (
    CompleteReviewCommand,
    CompleteReviewCommandHandler,
)
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository


class TestCompleteReviewCommandHandler:
    def test_moves_an_under_review_slice_to_pr_open(self) -> None:
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.UNDER_REVIEW)
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        handler = CompleteReviewCommandHandler(slice_repository=repository)

        handler(CompleteReviewCommand(slice_id="12"))

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.status == SliceStatus.PR_OPEN

    def test_is_idempotent_when_slice_is_not_under_review(self) -> None:
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.PR_OPEN)
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        handler = CompleteReviewCommandHandler(slice_repository=repository)

        handler(CompleteReviewCommand(slice_id="12"))

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.status == SliceStatus.PR_OPEN

    def test_does_nothing_when_slice_is_missing(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): []})
        handler = CompleteReviewCommandHandler(slice_repository=repository)

        handler(CompleteReviewCommand(slice_id="99"))

        assert repository.find(SliceId("99")) is None
