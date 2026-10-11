from __future__ import annotations

from grooveloop.delivery.domain.pull_request import PullRequest
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.delivery.infrastructure.detectors.pull_request_closed_detector import (
    PullRequestClosedDetector,
)
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository


def _pull_request(closed: bool, merged: bool = False) -> PullRequest:
    return PullRequest(
        number=PullRequestNumber(99),
        comments=[],
        merged=merged,
        closed=closed,
    )


class TestPullRequestClosedDetector:
    def test_emits_event_for_a_pr_open_slice_whose_pull_request_is_closed_without_merge(self) -> None:
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.PR_OPEN, pull_request=_pull_request(closed=True))
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        detector = PullRequestClosedDetector(slice_repository=repository)

        events = list(detector.detect())

        assert [event.slice_id.value for event in events] == ["12"]

    def test_does_not_emit_when_the_pull_request_is_merged(self) -> None:
        a_slice = SliceMother.create(
            slice_id="12", status=SliceStatus.PR_OPEN, pull_request=_pull_request(closed=True, merged=True)
        )
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        detector = PullRequestClosedDetector(slice_repository=repository)

        assert list(detector.detect()) == []

    def test_does_not_emit_when_the_pull_request_is_still_open(self) -> None:
        a_slice = SliceMother.create(
            slice_id="12", status=SliceStatus.PR_OPEN, pull_request=_pull_request(closed=False)
        )
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        detector = PullRequestClosedDetector(slice_repository=repository)

        assert list(detector.detect()) == []

    def test_does_not_emit_for_a_terminal_slice(self) -> None:
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.FAILED, pull_request=_pull_request(closed=True))
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        detector = PullRequestClosedDetector(slice_repository=repository)

        assert list(detector.detect()) == []

    def test_emits_event_for_a_dispatched_slice_whose_linked_pull_request_is_closed_without_merge(self) -> None:
        a_slice = SliceMother.create(
            slice_id="12", status=SliceStatus.DISPATCHED, pull_request=_pull_request(closed=True)
        )
        repository = FakeSliceRepository({StoryId("10"): [a_slice]}, closed={SliceId("12")})
        detector = PullRequestClosedDetector(slice_repository=repository)

        events = list(detector.detect())

        assert [event.slice_id.value for event in events] == ["12"]

    def test_emits_event_for_a_changes_requested_slice_whose_pull_request_is_closed_without_merge(self) -> None:
        a_slice = SliceMother.create(
            slice_id="12", status=SliceStatus.CHANGES_REQUESTED, pull_request=_pull_request(closed=True)
        )
        repository = FakeSliceRepository({StoryId("10"): [a_slice]}, closed={SliceId("12")})
        detector = PullRequestClosedDetector(slice_repository=repository)

        events = list(detector.detect())

        assert [event.slice_id.value for event in events] == ["12"]

    def test_emits_event_for_an_under_review_slice_whose_pull_request_is_closed_without_merge(self) -> None:
        a_slice = SliceMother.create(
            slice_id="12", status=SliceStatus.UNDER_REVIEW, pull_request=_pull_request(closed=True)
        )
        repository = FakeSliceRepository({StoryId("10"): [a_slice]}, closed={SliceId("12")})
        detector = PullRequestClosedDetector(slice_repository=repository)

        events = list(detector.detect())

        assert [event.slice_id.value for event in events] == ["12"]

    def test_does_not_emit_for_a_dispatched_slice_whose_linked_pull_request_is_still_open(self) -> None:
        a_slice = SliceMother.create(
            slice_id="12", status=SliceStatus.DISPATCHED, pull_request=_pull_request(closed=False)
        )
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        detector = PullRequestClosedDetector(slice_repository=repository)

        assert list(detector.detect()) == []

    def test_emits_event_for_a_blocked_slice_whose_pull_request_is_closed_without_merge(self) -> None:
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.BLOCKED, pull_request=_pull_request(closed=True))
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        detector = PullRequestClosedDetector(slice_repository=repository)

        events = list(detector.detect())

        assert [event.slice_id.value for event in events] == ["12"]
