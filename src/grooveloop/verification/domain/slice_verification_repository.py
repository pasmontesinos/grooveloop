from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.verification.domain.slice_id import SliceId
    from grooveloop.verification.domain.slice_verification import SliceVerification
    from grooveloop.verification.domain.story_id import StoryId
    from grooveloop.verification.domain.verification_status import VerificationStatus


class SliceVerificationRepository(ABC):
    @abstractmethod
    def find(self, id: SliceId) -> SliceVerification | None: ...

    @abstractmethod
    def save(self, verification: SliceVerification) -> None: ...

    @abstractmethod
    def search(
        self, story_id: StoryId | None = None, status: VerificationStatus | None = None
    ) -> list[SliceVerification]: ...
