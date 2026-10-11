from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.dispatch_slice import (
    DispatchSliceCommand,
    DispatchSliceCommandHandler,
)
from grooveloop.delivery.domain.events import SliceReadyToDispatch
from grooveloop.delivery.infrastructure.journal_enabled import JournalEnabled
from grooveloop.delivery.infrastructure.max_parallel_slices import MaxParallelSlices
from grooveloop.shared.application.events.event_handler import EventHandler
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.target_repo import TargetRepo


class DispatchSliceWhenSliceReadyToDispatch(EventHandler[SliceReadyToDispatch]):
    event_class = SliceReadyToDispatch

    def handle(self, event: SliceReadyToDispatch) -> None:
        handler = container.get(DispatchSliceCommandHandler)
        workdir = container.get(AgentWorkdir)
        repo = container.get(TargetRepo)
        max_parallel_slices = container.get(MaxParallelSlices)
        journal_enabled = container.get(JournalEnabled)

        handler(
            DispatchSliceCommand(
                slice_id=event.slice_id.value,
                workdir=workdir.value,
                repo=repo.value,
                max_parallel_slices=max_parallel_slices.value,
                journal_enabled=journal_enabled.value,
            )
        )
