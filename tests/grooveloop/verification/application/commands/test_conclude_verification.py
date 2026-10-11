from __future__ import annotations

from grooveloop.verification.application.commands.conclude_verification import (
    ConcludeVerificationCommand,
    ConcludeVerificationCommandHandler,
)
from grooveloop.verification.domain.slice_id import SliceId
from grooveloop.verification.domain.slice_verification import SliceVerification
from grooveloop.verification.domain.story_id import StoryId
from grooveloop.verification.domain.verification_status import VerificationStatus
from tests.playground.shared.infrastructure.fake_slice_verification_repository import (
    FakeSliceVerificationRepository,
)


def _repository(status: VerificationStatus) -> FakeSliceVerificationRepository:
    return FakeSliceVerificationRepository([SliceVerification(SliceId("11"), StoryId("10"), status)])


class TestConcludeVerificationCommandHandler:
    def test_concludes_a_running_verification(self) -> None:
        repository = _repository(VerificationStatus.RUNNING)

        ConcludeVerificationCommandHandler(slice_verification_repository=repository)(
            ConcludeVerificationCommand(slice_id="11")
        )

        verification = repository.find(SliceId("11"))
        assert verification is not None
        assert verification.status == VerificationStatus.CONCLUDED

    def test_leaves_a_verification_that_never_started_untouched(self) -> None:
        repository = _repository(VerificationStatus.EMPTY)

        ConcludeVerificationCommandHandler(slice_verification_repository=repository)(
            ConcludeVerificationCommand(slice_id="11")
        )

        verification = repository.find(SliceId("11"))
        assert verification is not None
        assert verification.status == VerificationStatus.EMPTY

    def test_does_nothing_for_an_unknown_slice(self) -> None:
        repository = FakeSliceVerificationRepository([])

        ConcludeVerificationCommandHandler(slice_verification_repository=repository)(
            ConcludeVerificationCommand(slice_id="11")
        )

        assert repository.find(SliceId("11")) is None
