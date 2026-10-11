from __future__ import annotations

from grooveloop.delivery.domain.events import PullRequestApproved
from grooveloop.delivery.domain.review_verdict import ReviewVerdict
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.delivery.infrastructure.auto_merge import AutoMerge
from grooveloop.delivery.infrastructure.detectors.pull_request_approved_detector import (
    PullRequestApprovedDetector,
)
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository


def _repository_with_an_approved_and_a_blocking_slice() -> FakeSliceRepository:
    return FakeSliceRepository(
        {
            StoryId("10"): [
                SliceMother.create(
                    slice_id="12",
                    status=SliceStatus.PR_OPEN,
                    pull_request_number=42,
                    review_verdict=ReviewVerdict.APPROVE,
                ),
                SliceMother.create(
                    slice_id="13",
                    status=SliceStatus.PR_OPEN,
                    pull_request_number=42,
                    review_verdict=ReviewVerdict.BLOCKING,
                ),
            ]
        }
    )


class TestPullRequestApprovedDetector:
    def test_emits_event_for_every_auto_mergeable_slice_when_auto_merge_is_on(self) -> None:
        detector = PullRequestApprovedDetector(
            slice_repository=_repository_with_an_approved_and_a_blocking_slice(), auto_merge=AutoMerge(True)
        )

        events = list(detector.detect())

        assert events == [PullRequestApproved(slice_id=SliceId("12"))]

    def test_emits_nothing_when_auto_merge_is_off(self) -> None:
        detector = PullRequestApprovedDetector(
            slice_repository=_repository_with_an_approved_and_a_blocking_slice(), auto_merge=AutoMerge(False)
        )

        assert list(detector.detect()) == []
