from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.verification.domain.slice_verification_repository import SliceVerificationRepository

if TYPE_CHECKING:
    from grooveloop.verification.domain.slice_id import SliceId
    from grooveloop.verification.domain.slice_verification import SliceVerification
    from grooveloop.verification.domain.story_id import StoryId
    from grooveloop.verification.domain.verification_status import VerificationStatus


class FakeSliceVerificationRepository(SliceVerificationRepository):
    def __init__(self, verifications: list[SliceVerification]) -> None:
        self._verifications = {verification.slice_id: verification for verification in verifications}
        self.find_calls = 0
        self.search_calls = 0

    def find(self, id: SliceId) -> SliceVerification | None:
        self.find_calls += 1

        return self._verifications.get(id)

    def save(self, verification: SliceVerification) -> None:
        self._verifications[verification.slice_id] = verification

    def search(
        self, story_id: StoryId | None = None, status: VerificationStatus | None = None
    ) -> list[SliceVerification]:
        self.search_calls += 1
        verifications = list(self._verifications.values())

        if story_id is not None:
            verifications = [verification for verification in verifications if verification.story_id == story_id]

        if status is not None:
            verifications = [verification for verification in verifications if verification.status == status]

        return verifications
