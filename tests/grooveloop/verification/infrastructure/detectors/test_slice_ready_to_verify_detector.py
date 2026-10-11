from __future__ import annotations

from grooveloop.verification.domain.events import SliceReadyToVerify
from grooveloop.verification.domain.merged_slice import MergedSlice
from grooveloop.verification.domain.pull_request_number import PullRequestNumber
from grooveloop.verification.domain.slice_id import SliceId
from grooveloop.verification.domain.slice_verification import SliceVerification
from grooveloop.verification.domain.story_id import StoryId
from grooveloop.verification.domain.verification_status import VerificationStatus
from grooveloop.verification.infrastructure.detectors.slice_ready_to_verify_detector import SliceReadyToVerifyDetector
from tests.playground.shared.infrastructure.fake_merged_slice_signal import FakeMergedSliceSignal
from tests.playground.shared.infrastructure.fake_slice_verification_repository import (
    FakeSliceVerificationRepository,
)

_TITLE = "Mark verify-deploy when creating the sub-issues"
_DESCRIPTION = "- **Observable verification:**\n\n  1. `gh pr view 42`.\n"


def _detector(status: VerificationStatus | None) -> SliceReadyToVerifyDetector:
    merged_slice = MergedSlice(
        slice_id=SliceId("11"),
        pull_request_number=PullRequestNumber(42),
        title=_TITLE,
        description=_DESCRIPTION,
        has_report=False,
    )
    verifications = [SliceVerification(SliceId("11"), StoryId("10"), status)] if status is not None else []

    return SliceReadyToVerifyDetector(
        merged_slice_signal=FakeMergedSliceSignal([merged_slice]),
        slice_verification_repository=FakeSliceVerificationRepository(verifications),
    )


class TestSliceReadyToVerifyDetector:
    def test_emits_for_a_merged_marked_slice_whose_verification_has_not_started(self) -> None:
        detector = _detector(VerificationStatus.EMPTY)

        assert list(detector.detect()) == [
            SliceReadyToVerify(
                slice_id=SliceId("11"),
                pull_request_number=PullRequestNumber(42),
                title=_TITLE,
                description=_DESCRIPTION,
            )
        ]

    def test_does_not_emit_for_a_running_verification(self) -> None:
        assert list(_detector(VerificationStatus.RUNNING).detect()) == []

    def test_does_not_emit_for_a_concluded_verification(self) -> None:
        assert list(_detector(VerificationStatus.CONCLUDED).detect()) == []

    def test_does_not_emit_for_a_slice_without_verification(self) -> None:
        assert list(_detector(None).detect()) == []


class TestVerifiableSliceDetectorRepositoryReads:
    def test_resolves_the_pending_verifications_with_a_single_repository_read(self) -> None:
        merged_slices = [
            MergedSlice(
                slice_id=SliceId(str(number)),
                pull_request_number=PullRequestNumber(number + 30),
                title=_TITLE,
                description=_DESCRIPTION,
                has_report=False,
            )
            for number in (11, 12)
        ]
        repository = FakeSliceVerificationRepository(
            [
                SliceVerification(SliceId("11"), StoryId("10"), VerificationStatus.EMPTY),
                SliceVerification(SliceId("12"), StoryId("10"), VerificationStatus.EMPTY),
            ]
        )
        detector = SliceReadyToVerifyDetector(
            merged_slice_signal=FakeMergedSliceSignal(merged_slices),
            slice_verification_repository=repository,
        )

        events = list(detector.detect())

        assert len(events) == 2
        assert repository.search_calls == 1
        assert repository.find_calls == 0
