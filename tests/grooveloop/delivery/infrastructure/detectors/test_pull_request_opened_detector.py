from __future__ import annotations

from grooveloop.delivery.domain.pull_request import PullRequest
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.delivery.infrastructure.detectors.pull_request_opened_detector import (
    PullRequestOpenedDetector,
)
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository


def _pull_request(merged: bool = False, closed: bool = False) -> PullRequest:
    return PullRequest(number=PullRequestNumber(99), comments=[], merged=merged, closed=closed)


class TestPullRequestOpenedDetector:
    def test_emits_event_for_dispatched_slice_with_an_open_pull_request(self) -> None:
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.DISPATCHED, pull_request=_pull_request())
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        detector = PullRequestOpenedDetector(slice_repository=repository)

        events = list(detector.detect())

        assert [(event.slice_id.value, event.pull_request_number.value) for event in events] == [("12", 99)]

    def test_does_not_emit_when_there_is_no_pull_request(self) -> None:
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.DISPATCHED)
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        detector = PullRequestOpenedDetector(slice_repository=repository)

        assert list(detector.detect()) == []

    def test_does_not_emit_for_non_dispatched_slice(self) -> None:
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.PR_OPEN, pull_request=_pull_request())
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        detector = PullRequestOpenedDetector(slice_repository=repository)

        assert list(detector.detect()) == []

    def test_does_not_emit_when_the_linked_pull_request_is_already_resolved(self) -> None:
        a_slice = SliceMother.create(
            slice_id="12", status=SliceStatus.DISPATCHED, pull_request=_pull_request(merged=True)
        )
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        detector = PullRequestOpenedDetector(slice_repository=repository)

        assert list(detector.detect()) == []
