from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.shared.application.events.event_handler import EventHandler
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.target_repo import TargetRepo
from grooveloop.verification.application.commands.verify_deployment import (
    VerifyDeploymentCommand,
    VerifyDeploymentCommandHandler,
)
from grooveloop.verification.domain.events import SliceReadyToVerify


class VerifyDeploymentWhenSliceReadyToVerify(EventHandler[SliceReadyToVerify]):
    event_class = SliceReadyToVerify

    def handle(self, event: SliceReadyToVerify) -> None:
        handler = container.get(VerifyDeploymentCommandHandler)
        workdir = container.get(AgentWorkdir)
        repo = container.get(TargetRepo)

        handler(
            VerifyDeploymentCommand(
                slice_id=event.slice_id.value,
                pull_request_number=event.pull_request_number.value,
                title=event.title,
                description=event.description,
                workdir=workdir.value,
                repo=repo.value,
            )
        )
