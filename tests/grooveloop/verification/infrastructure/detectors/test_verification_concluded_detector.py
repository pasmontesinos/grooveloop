from __future__ import annotations

from grooveloop.verification.domain.events import VerificationConcluded
from grooveloop.verification.domain.merged_slice import MergedSlice
from grooveloop.verification.domain.pull_request_number import PullRequestNumber
from grooveloop.verification.domain.slice_id import SliceId
from grooveloop.verification.domain.slice_verification import SliceVerification
from grooveloop.verification.domain.story_id import StoryId
from grooveloop.verification.domain.verification_status import VerificationStatus
from grooveloop.verification.infrastructure.detectors.verification_concluded_detector import (
    VerificationConcludedDetector,
)
from tests.playground.shared.infrastructure.fake_merged_slice_signal import FakeMergedSliceSignal
from tests.playground.shared.infrastructure.fake_slice_verification_repository import (
    FakeSliceVerificationRepository,
)


def _detector(status: VerificationStatus, has_report: bool) -> VerificationConcludedDetector:
    merged_slice = MergedSlice(
        slice_id=SliceId("11"),
        pull_request_number=PullRequestNumber(42),
        title="Mark verify-deploy when creating the sub-issues",
        description="- **Observable verification:**\n\n  1. `gh pr view 42`.\n",
        has_report=has_report,
    )

    return VerificationConcludedDetector(
        merged_slice_signal=FakeMergedSliceSignal([merged_slice]),
        slice_verification_repository=FakeSliceVerificationRepository(
            [SliceVerification(SliceId("11"), StoryId("10"), status)]
        ),
    )


class TestVerificationConcludedDetector:
    def test_emits_when_the_pull_request_carries_the_report_marker(self) -> None:
        detector = _detector(VerificationStatus.RUNNING, has_report=True)

        assert list(detector.detect()) == [VerificationConcluded(slice_id=SliceId("11"))]

    def test_does_not_emit_while_the_report_marker_is_missing(self) -> None:
        assert list(_detector(VerificationStatus.RUNNING, has_report=False).detect()) == []

    def test_does_not_emit_for_a_verification_that_never_started(self) -> None:
        assert list(_detector(VerificationStatus.EMPTY, has_report=True).detect()) == []

    def test_does_not_emit_for_an_already_concluded_verification(self) -> None:
        assert list(_detector(VerificationStatus.CONCLUDED, has_report=True).detect()) == []
