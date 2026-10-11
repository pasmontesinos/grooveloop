from __future__ import annotations

import pytest

from grooveloop.shared.domain.agent_run import AgentRun
from grooveloop.shared.domain.agent_run_cause import AgentRunCause
from grooveloop.verification.domain.exceptions import IllegalVerificationTransitionError
from grooveloop.verification.domain.slice_id import SliceId
from grooveloop.verification.domain.slice_verification import SliceVerification
from grooveloop.verification.domain.verification_status import VerificationStatus

TRANSITIONS = [
    ("start", {VerificationStatus.EMPTY}, VerificationStatus.RUNNING),
    ("conclude", {VerificationStatus.RUNNING}, VerificationStatus.CONCLUDED),
    ("fail", {VerificationStatus.RUNNING}, VerificationStatus.FAILED),
]


def _verification_in(status: VerificationStatus) -> SliceVerification:
    return SliceVerification(slice_id=SliceId("11"), story_id=None, status=status)


class TestSliceVerificationLifecycle:
    @pytest.mark.parametrize(("method", "allowed", "target"), TRANSITIONS)
    def test_should_transition_from_allowed_status(
        self, method: str, allowed: set[VerificationStatus], target: VerificationStatus
    ) -> None:
        for status in allowed:
            verification = _verification_in(status)

            getattr(verification, method)()

            assert verification.status == target

    @pytest.mark.parametrize(("method", "allowed", "target"), TRANSITIONS)
    def test_should_reject_transition_from_disallowed_status(
        self, method: str, allowed: set[VerificationStatus], target: VerificationStatus
    ) -> None:
        for status in set(VerificationStatus) - allowed:
            verification = _verification_in(status)

            with pytest.raises(IllegalVerificationTransitionError):
                getattr(verification, method)()

    @pytest.mark.parametrize(
        ("predicate", "allowed"),
        [
            ("can_start", {VerificationStatus.EMPTY}),
            ("can_conclude", {VerificationStatus.RUNNING}),
            ("is_running", {VerificationStatus.RUNNING}),
        ],
    )
    def test_should_answer_each_predicate_only_from_its_statuses(
        self, predicate: str, allowed: set[VerificationStatus]
    ) -> None:
        for status in VerificationStatus:
            assert getattr(_verification_in(status), predicate)() is (status in allowed)

    @pytest.mark.parametrize(
        ("status", "pending"),
        [
            (VerificationStatus.EMPTY, True),
            (VerificationStatus.RUNNING, True),
            (VerificationStatus.CONCLUDED, False),
            (VerificationStatus.FAILED, True),
        ],
    )
    def test_should_stay_pending_until_it_concludes(self, status: VerificationStatus, pending: bool) -> None:
        assert _verification_in(status).is_pending() is pending

    def test_should_record_the_cause_of_the_failure(self) -> None:
        verification = _verification_in(VerificationStatus.RUNNING)

        verification.fail(AgentRunCause.OVERLOADED)

        assert verification.failure_cause == AgentRunCause.OVERLOADED

    def test_should_count_the_attempt_when_it_retries_the_agent_run(self) -> None:
        verification = SliceVerification(
            slice_id=SliceId("11"), story_id=None, status=VerificationStatus.RUNNING, agent_run_id="run-1", retries=1
        )

        verification.retry_agent_run(AgentRun(run_id="run-2", pid=0))

        assert verification.agent_run_id == "run-2"
        assert verification.retries == 2
        assert verification.status == VerificationStatus.RUNNING
