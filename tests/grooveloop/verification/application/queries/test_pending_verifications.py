from __future__ import annotations

from grooveloop.shared.application.queries.pending_verifications import PendingVerificationsQuery
from grooveloop.verification.application.queries.pending_verifications import PendingVerificationsQueryHandler
from grooveloop.verification.domain.slice_id import SliceId
from grooveloop.verification.domain.slice_verification import SliceVerification
from grooveloop.verification.domain.story_id import StoryId
from grooveloop.verification.domain.verification_status import VerificationStatus
from tests.playground.shared.infrastructure.fake_slice_verification_repository import (
    FakeSliceVerificationRepository,
)


def _verification(number: str, story: str, status: VerificationStatus) -> SliceVerification:
    return SliceVerification(slice_id=SliceId(number), story_id=StoryId(story), status=status)


class TestPendingVerificationsQueryHandler:
    def test_should_return_the_slices_whose_verification_has_not_concluded(self) -> None:
        repository = FakeSliceVerificationRepository(
            [
                _verification("11", "10", VerificationStatus.EMPTY),
                _verification("12", "10", VerificationStatus.RUNNING),
                _verification("13", "10", VerificationStatus.CONCLUDED),
            ]
        )
        handler = PendingVerificationsQueryHandler(slice_verification_repository=repository)

        result = handler(PendingVerificationsQuery(story_id="10"))

        assert result.slice_ids == ["11", "12"]

    def test_should_ignore_the_verifications_of_other_stories(self) -> None:
        repository = FakeSliceVerificationRepository(
            [
                _verification("11", "10", VerificationStatus.RUNNING),
                _verification("21", "20", VerificationStatus.RUNNING),
            ]
        )
        handler = PendingVerificationsQueryHandler(slice_verification_repository=repository)

        result = handler(PendingVerificationsQuery(story_id="10"))

        assert result.slice_ids == ["11"]

    def test_should_return_nothing_when_every_verification_concluded(self) -> None:
        repository = FakeSliceVerificationRepository([_verification("11", "10", VerificationStatus.CONCLUDED)])
        handler = PendingVerificationsQueryHandler(slice_verification_repository=repository)

        result = handler(PendingVerificationsQuery(story_id="10"))

        assert result.slice_ids == []
