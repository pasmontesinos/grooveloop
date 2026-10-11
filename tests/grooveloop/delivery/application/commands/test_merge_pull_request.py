from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grooveloop.delivery.application.commands.merge_pull_request import (
    MergePullRequestCommand,
    MergePullRequestCommandHandler,
)
from grooveloop.delivery.domain.mergeability import Mergeability
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.review_verdict import ReviewVerdict
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_pull_request_merger import FakePullRequestMerger
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository

if TYPE_CHECKING:
    from grooveloop.delivery.domain.slice import Slice


def _handler(a_slice: Slice, merger: FakePullRequestMerger) -> MergePullRequestCommandHandler:
    return MergePullRequestCommandHandler(
        slice_repository=FakeSliceRepository({StoryId("10"): [a_slice]}), pull_request_merger=merger
    )


class TestMergePullRequestCommandHandler:
    def test_merges_the_clean_pull_request_of_an_approved_slice(self) -> None:
        merger = FakePullRequestMerger(Mergeability.CLEAN)

        _handler(
            SliceMother.create(
                slice_id="12", status=SliceStatus.PR_OPEN, pull_request_number=42, review_verdict=ReviewVerdict.APPROVE
            ),
            merger,
        )(MergePullRequestCommand(slice_id="12"))

        assert merger.merged == [PullRequestNumber(42)]

    @pytest.mark.parametrize("mergeability", set(Mergeability) - {Mergeability.CLEAN})
    def test_leaves_the_pull_request_open_when_it_is_not_clean(self, mergeability: Mergeability) -> None:
        merger = FakePullRequestMerger(mergeability)

        _handler(
            SliceMother.create(
                slice_id="12", status=SliceStatus.PR_OPEN, pull_request_number=42, review_verdict=ReviewVerdict.APPROVE
            ),
            merger,
        )(MergePullRequestCommand(slice_id="12"))

        assert merger.merged == []

    @pytest.mark.parametrize("verdict", [ReviewVerdict.BLOCKING, ReviewVerdict.BLOCKED, ReviewVerdict.EMPTY])
    def test_does_not_consult_the_pull_request_without_an_approving_verdict(self, verdict: ReviewVerdict) -> None:
        merger = FakePullRequestMerger(Mergeability.CLEAN)

        _handler(
            SliceMother.create(
                slice_id="12", status=SliceStatus.PR_OPEN, pull_request_number=42, review_verdict=verdict
            ),
            merger,
        )(MergePullRequestCommand(slice_id="12"))

        assert merger.consulted == []
        assert merger.merged == []

    def test_does_not_merge_a_slice_that_already_left_pr_open(self) -> None:
        merger = FakePullRequestMerger(Mergeability.CLEAN)

        _handler(
            SliceMother.create(
                slice_id="12", status=SliceStatus.MERGED, pull_request_number=42, review_verdict=ReviewVerdict.APPROVE
            ),
            merger,
        )(MergePullRequestCommand(slice_id="12"))

        assert merger.merged == []

    def test_does_nothing_when_the_slice_is_missing(self) -> None:
        merger = FakePullRequestMerger(Mergeability.CLEAN)

        _handler(
            SliceMother.create(
                slice_id="12", status=SliceStatus.PR_OPEN, pull_request_number=42, review_verdict=ReviewVerdict.APPROVE
            ),
            merger,
        )(MergePullRequestCommand(slice_id="99"))

        assert merger.consulted == []
