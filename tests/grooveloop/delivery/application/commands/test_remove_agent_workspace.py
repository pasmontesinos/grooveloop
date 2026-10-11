from __future__ import annotations

from unittest.mock import Mock, call, create_autospec

import pytest

from grooveloop.delivery.application.commands.remove_agent_workspace import (
    RemoveAgentWorkspaceCommand,
    RemoveAgentWorkspaceCommandHandler,
)
from grooveloop.shared.domain.workspace_containers import WorkspaceContainers
from grooveloop.shared.domain.workspace_processes import WorkspaceProcesses
from tests.playground.shared.infrastructure.fake_agent_workspaces import FakeAgentWorkspaces
from tests.playground.shared.infrastructure.fake_workspace_containers import FakeWorkspaceContainers
from tests.playground.shared.infrastructure.fake_workspace_processes import FakeWorkspaceProcesses


class TestRemoveAgentWorkspaceCommandHandler:
    def test_removes_the_workspace_of_the_run(self) -> None:
        agent_workspaces = FakeAgentWorkspaces(["run-1"])
        handler = RemoveAgentWorkspaceCommandHandler(
            agent_workspaces=agent_workspaces,
            workspace_processes=FakeWorkspaceProcesses(),
            workspace_containers=FakeWorkspaceContainers(),
        )

        handler(RemoveAgentWorkspaceCommand(run_id="run-1"))

        assert agent_workspaces.removed == ["run-1"]
        assert agent_workspaces.finished_run_ids() == []

    def test_removes_the_containers_of_the_workspace(self) -> None:
        workspace_containers = FakeWorkspaceContainers()
        handler = RemoveAgentWorkspaceCommandHandler(
            agent_workspaces=FakeAgentWorkspaces(["run-1"]),
            workspace_processes=FakeWorkspaceProcesses(),
            workspace_containers=workspace_containers,
        )

        handler(RemoveAgentWorkspaceCommand(run_id="run-1"))

        assert workspace_containers.removed == ["/runs/run-1/workdir"]

    def test_does_not_touch_the_containers_when_the_run_has_no_workspace(self) -> None:
        workspace_containers = FakeWorkspaceContainers()
        handler = RemoveAgentWorkspaceCommandHandler(
            agent_workspaces=FakeAgentWorkspaces(),
            workspace_processes=FakeWorkspaceProcesses(),
            workspace_containers=workspace_containers,
        )

        handler(RemoveAgentWorkspaceCommand(run_id="run-1"))

        assert workspace_containers.removed == []

    def test_removes_the_workspace_and_reports_the_failure_when_the_containers_fail(self) -> None:
        agent_workspaces = FakeAgentWorkspaces(["run-1"])
        handler = RemoveAgentWorkspaceCommandHandler(
            agent_workspaces=agent_workspaces,
            workspace_processes=FakeWorkspaceProcesses(),
            workspace_containers=FakeWorkspaceContainers(failure=RuntimeError("docker compose down failed")),
        )

        with pytest.raises(RuntimeError, match="docker compose down failed"):
            handler(RemoveAgentWorkspaceCommand(run_id="run-1"))

        assert agent_workspaces.removed == ["run-1"]

    def test_terminates_the_processes_of_the_workspace(self) -> None:
        workspace_processes = FakeWorkspaceProcesses()
        handler = RemoveAgentWorkspaceCommandHandler(
            agent_workspaces=FakeAgentWorkspaces(["run-1"]),
            workspace_processes=workspace_processes,
            workspace_containers=FakeWorkspaceContainers(),
        )

        handler(RemoveAgentWorkspaceCommand(run_id="run-1"))

        assert workspace_processes.terminated == ["/runs/run-1/workdir"]

    def test_terminates_the_processes_before_removing_the_containers(self) -> None:
        workspace_processes = create_autospec(WorkspaceProcesses, spec_set=True, instance=True)
        workspace_containers = create_autospec(WorkspaceContainers, spec_set=True, instance=True)
        cleanup = Mock()
        cleanup.attach_mock(workspace_processes, "processes")
        cleanup.attach_mock(workspace_containers, "containers")
        handler = RemoveAgentWorkspaceCommandHandler(
            agent_workspaces=FakeAgentWorkspaces(["run-1"]),
            workspace_processes=workspace_processes,
            workspace_containers=workspace_containers,
        )

        handler(RemoveAgentWorkspaceCommand(run_id="run-1"))

        assert cleanup.mock_calls == [
            call.processes.terminate("/runs/run-1/workdir"),
            call.containers.remove("/runs/run-1/workdir"),
        ]

    def test_removes_the_containers_and_the_workspace_and_reports_the_failure_when_the_processes_fail(self) -> None:
        agent_workspaces = FakeAgentWorkspaces(["run-1"])
        workspace_containers = FakeWorkspaceContainers()
        handler = RemoveAgentWorkspaceCommandHandler(
            agent_workspaces=agent_workspaces,
            workspace_processes=FakeWorkspaceProcesses(failure=RuntimeError("lsof failed")),
            workspace_containers=workspace_containers,
        )

        with pytest.raises(RuntimeError, match="lsof failed"):
            handler(RemoveAgentWorkspaceCommand(run_id="run-1"))

        assert workspace_containers.removed == ["/runs/run-1/workdir"]
        assert agent_workspaces.removed == ["run-1"]
