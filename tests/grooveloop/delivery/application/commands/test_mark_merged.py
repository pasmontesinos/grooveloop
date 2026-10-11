from __future__ import annotations

from grooveloop.delivery.application.commands.mark_merged import (
    MarkMergedCommand,
    MarkMergedCommandHandler,
)
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository


class TestMarkMergedCommandHandler:
    def test_moves_a_pr_open_slice_to_merged(self) -> None:
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.PR_OPEN)
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        handler = MarkMergedCommandHandler(slice_repository=repository)

        handler(MarkMergedCommand(slice_id="12"))

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.status == SliceStatus.MERGED

    def test_moves_a_dispatched_slice_to_merged(self) -> None:
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.DISPATCHED)
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        handler = MarkMergedCommandHandler(slice_repository=repository)

        handler(MarkMergedCommand(slice_id="12"))

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.status == SliceStatus.MERGED

    def test_moves_an_under_review_slice_to_merged(self) -> None:
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.UNDER_REVIEW)
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        handler = MarkMergedCommandHandler(slice_repository=repository)

        handler(MarkMergedCommand(slice_id="12"))

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.status == SliceStatus.MERGED

    def test_moves_a_changes_requested_slice_to_merged(self) -> None:
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.CHANGES_REQUESTED)
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        handler = MarkMergedCommandHandler(slice_repository=repository)

        handler(MarkMergedCommand(slice_id="12"))

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.status == SliceStatus.MERGED

    def test_is_idempotent_when_slice_is_not_pr_open(self) -> None:
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.MERGED, agent_run_id="run-12")
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        handler = MarkMergedCommandHandler(slice_repository=repository)

        handler(MarkMergedCommand(slice_id="12"))

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.status == SliceStatus.MERGED

    def test_does_nothing_when_slice_is_missing(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): []})
        handler = MarkMergedCommandHandler(slice_repository=repository)

        handler(MarkMergedCommand(slice_id="99"))

        assert repository.find(SliceId("99")) is None

    def test_marks_a_blocked_slice_as_merged(self) -> None:
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.BLOCKED)
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        handler = MarkMergedCommandHandler(slice_repository=repository)

        handler(MarkMergedCommand(slice_id="12"))

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.status == SliceStatus.MERGED
