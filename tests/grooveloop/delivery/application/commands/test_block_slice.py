from __future__ import annotations

from grooveloop.delivery.application.commands.block_slice import (
    BlockSliceCommand,
    BlockSliceCommandHandler,
)
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository


class TestBlockSliceCommandHandler:
    def test_moves_an_under_review_slice_to_blocked(self) -> None:
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.UNDER_REVIEW)
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        handler = BlockSliceCommandHandler(slice_repository=repository)

        handler(BlockSliceCommand(slice_id="12"))

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.status == SliceStatus.BLOCKED

    def test_is_idempotent_when_the_slice_is_already_blocked(self) -> None:
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.BLOCKED)
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        handler = BlockSliceCommandHandler(slice_repository=repository)

        handler(BlockSliceCommand(slice_id="12"))

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.status == SliceStatus.BLOCKED

    def test_does_nothing_when_the_slice_is_missing(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): []})
        handler = BlockSliceCommandHandler(slice_repository=repository)

        handler(BlockSliceCommand(slice_id="99"))

        assert repository.find(SliceId("99")) is None
