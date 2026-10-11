from __future__ import annotations

import pytest

from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.verification.domain.events import VerificationIncomplete
from grooveloop.verification.domain.merged_slice import MergedSlice
from grooveloop.verification.domain.pull_request_number import PullRequestNumber
from grooveloop.verification.domain.slice_id import SliceId
from grooveloop.verification.domain.slice_verification import SliceVerification
from grooveloop.verification.domain.story_id import StoryId
from grooveloop.verification.domain.verification_status import VerificationStatus
from grooveloop.verification.infrastructure.detectors.verification_incomplete_detector import (
    VerificationIncompleteDetector,
)
from tests.playground.shared.infrastructure.fake_agent_runner import FakeAgentRunner
from tests.playground.shared.infrastructure.fake_merged_slice_signal import FakeMergedSliceSignal
from tests.playground.shared.infrastructure.fake_slice_verification_repository import (
    FakeSliceVerificationRepository,
)

_TITLE = "Mark verify-deploy when creating the sub-issues"
_DESCRIPTION = "- **Observable verification:**\n\n  1. `gh pr view 42`.\n"


def _detector(
    status: VerificationStatus = VerificationStatus.RUNNING,
    outcome: AgentOutcome = AgentOutcome.SUCCEEDED,
    has_report: bool = False,
) -> VerificationIncompleteDetector:
    merged_slice = MergedSlice(
        slice_id=SliceId("11"),
        pull_request_number=PullRequestNumber(42),
        title=_TITLE,
        description=_DESCRIPTION,
        has_report=has_report,
    )

    return VerificationIncompleteDetector(
        merged_slice_signal=FakeMergedSliceSignal([merged_slice]),
        slice_verification_repository=FakeSliceVerificationRepository(
            [SliceVerification(SliceId("11"), StoryId("10"), status, agent_run_id="run-1")]
        ),
        agent_runner=FakeAgentRunner(outcome),
    )


class TestVerificationIncompleteDetector:
    def test_emits_when_the_verifier_finished_without_its_report(self) -> None:
        assert list(_detector().detect()) == [
            VerificationIncomplete(
                slice_id=SliceId("11"),
                run_id="run-1",
                pull_request_number=PullRequestNumber(42),
                title=_TITLE,
                description=_DESCRIPTION,
            )
        ]

    @pytest.mark.parametrize("outcome", [AgentOutcome.RUNNING, AgentOutcome.INTERRUPTED, AgentOutcome.FAILED])
    def test_does_not_emit_while_the_run_has_not_succeeded(self, outcome: AgentOutcome) -> None:
        assert list(_detector(outcome=outcome).detect()) == []

    def test_does_not_emit_when_the_report_was_published(self) -> None:
        assert list(_detector(has_report=True).detect()) == []

    def test_does_not_emit_for_a_verification_that_is_not_running(self) -> None:
        assert list(_detector(status=VerificationStatus.CONCLUDED).detect()) == []
