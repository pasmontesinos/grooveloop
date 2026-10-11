from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.verification.domain.events import VerificationIncomplete
from grooveloop.verification.domain.verification_status import VerificationStatus

if TYPE_CHECKING:
    from collections.abc import Iterator

    from grooveloop.shared.domain.agent_runner import AgentRunner
    from grooveloop.verification.domain.merged_slice_signal import MergedSliceSignal
    from grooveloop.verification.domain.slice_verification_repository import SliceVerificationRepository


class VerificationIncompleteDetector:
    def __init__(
        self,
        merged_slice_signal: MergedSliceSignal,
        slice_verification_repository: SliceVerificationRepository,
        agent_runner: AgentRunner,
    ) -> None:
        self._merged_slice_signal = merged_slice_signal
        self._slice_verification_repository = slice_verification_repository
        self._agent_runner = agent_runner

    def detect(self) -> Iterator[VerificationIncomplete]:
        runs = {
            verification.slice_id: verification.agent_run_id
            for verification in self._slice_verification_repository.search(status=VerificationStatus.RUNNING)
        }

        for merged_slice in self._merged_slice_signal.merged_slices():
            run_id = runs.get(merged_slice.slice_id)
            if (
                run_id is not None
                and not merged_slice.has_report
                and self._agent_runner.outcome_of(run_id) is AgentOutcome.SUCCEEDED
            ):
                yield VerificationIncomplete(
                    slice_id=merged_slice.slice_id,
                    run_id=run_id,
                    pull_request_number=merged_slice.pull_request_number,
                    title=merged_slice.title,
                    description=merged_slice.description,
                )
