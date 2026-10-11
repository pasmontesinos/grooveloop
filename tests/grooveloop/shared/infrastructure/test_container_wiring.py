from __future__ import annotations

from pathlib import Path

from github import Github
from injector import Injector

from grooveloop.bootstrap import container
from grooveloop.bootstrap.di import modules
from grooveloop.cli.invocation_inputs import bind_invocation_inputs
from grooveloop.cli.tick import DETECTORS
from grooveloop.delivery.application.commands.close_agent_run import CloseAgentRunCommandHandler
from grooveloop.delivery.application.commands.remove_agent_workspace import RemoveAgentWorkspaceCommandHandler
from grooveloop.delivery.infrastructure.detectors.agent_run_abandoned_detector import AgentRunAbandonedDetector
from grooveloop.delivery.infrastructure.github_delivery_labels import GithubDeliveryLabels
from grooveloop.shared.application.events.event_dispatcher import EventDispatcher
from grooveloop.shared.application.queries.list_loops import ListLoopsQueryHandler
from grooveloop.shared.application.queries.query_bus import QueryBus
from grooveloop.shared.domain.abandoned_agent_runs import AbandonedAgentRuns
from grooveloop.shared.domain.agent_run_logs import AgentRunLogs
from grooveloop.shared.domain.agent_runner_registry import AgentRunnerRegistry
from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.domain.loop_presence import LoopPresence
from grooveloop.shared.domain.loop_snapshots import LoopSnapshots
from grooveloop.shared.domain.process_liveness import ProcessLiveness
from grooveloop.shared.domain.workspace_containers import WorkspaceContainers
from grooveloop.shared.domain.workspace_processes import WorkspaceProcesses
from grooveloop.shared.infrastructure.agent_log_readers import AgentLogReaders
from grooveloop.shared.infrastructure.docker_workspace_containers import DockerWorkspaceContainers
from grooveloop.shared.infrastructure.event_handler_registry import EventHandlerRegistry
from grooveloop.shared.infrastructure.filesystem_agent_run_logs import FilesystemAgentRunLogs
from grooveloop.shared.infrastructure.filesystem_loop_presence import FilesystemLoopPresence
from grooveloop.shared.infrastructure.filesystem_loop_snapshots import FilesystemLoopSnapshots
from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
from grooveloop.shared.infrastructure.injector_event_dispatcher import InjectorEventDispatcher
from grooveloop.shared.infrastructure.injector_lookup import resolve
from grooveloop.shared.infrastructure.injector_query_bus import InjectorQueryBus
from grooveloop.shared.infrastructure.local_abandoned_agent_runs import LocalAbandonedAgentRuns
from grooveloop.shared.infrastructure.repos_dir import ReposDir
from grooveloop.shared.infrastructure.runs_dir import RunsDir
from grooveloop.shared.infrastructure.signal_process_liveness import SignalProcessLiveness
from grooveloop.shared.infrastructure.signal_workspace_processes import SignalWorkspaceProcesses
from grooveloop.shared.infrastructure.subprocess_agent_runner import SubprocessAgentRunner
from grooveloop.shared.infrastructure.system_clock import SystemClock
from grooveloop.shared.infrastructure.target_repo import TargetRepo
from tests.playground.shared.infrastructure.github_client import github_client_for_any_repo


class TestContainerWiring:
    def test_should_resolve_clock(self) -> None:
        assert isinstance(container.get(Clock), SystemClock)

    def test_should_resolve_github_read_cache_as_a_singleton(self) -> None:
        first = container.get(GithubReadCache)
        second = container.get(GithubReadCache)

        assert isinstance(first, GithubReadCache)
        assert first is second

    def test_should_resolve_loop_presence(self) -> None:
        assert isinstance(container.get(LoopPresence), FilesystemLoopPresence)

    def test_should_resolve_loop_snapshots(self) -> None:
        assert isinstance(container.get(LoopSnapshots), FilesystemLoopSnapshots)

    def test_should_resolve_agent_run_logs(self) -> None:
        assert isinstance(container.get(AgentRunLogs), FilesystemAgentRunLogs)

    def test_should_resolve_process_liveness(self) -> None:
        assert isinstance(container.get(ProcessLiveness), SignalProcessLiveness)

    def test_should_resolve_list_loops_query_handler(self) -> None:
        assert isinstance(container.get(ListLoopsQueryHandler), ListLoopsQueryHandler)

    def test_should_resolve_the_runs_and_repos_directories_under_the_home(self) -> None:
        assert container.get(RunsDir) == RunsDir(Path.home() / ".grooveloop" / "runs")
        assert container.get(ReposDir) == ReposDir(Path.home() / ".grooveloop" / "repos")

    def test_should_resolve_one_log_reader_per_supported_engine_as_a_singleton(self) -> None:
        log_readers = container.get(AgentLogReaders)

        assert sorted(log_readers.value) == ["claude", "opencode"]
        assert container.get(AgentLogReaders) is log_readers

    def test_should_resolve_query_bus(self) -> None:
        assert isinstance(container.get(QueryBus), InjectorQueryBus)

    def test_should_resolve_event_dispatcher(self) -> None:
        assert isinstance(container.get(EventDispatcher), InjectorEventDispatcher)

    def test_should_resolve_a_runner_for_every_supported_engine(self) -> None:
        registry = container.get(AgentRunnerRegistry)

        assert isinstance(registry.runner_for("claude"), SubprocessAgentRunner)
        assert isinstance(registry.runner_for("opencode"), SubprocessAgentRunner)

    def test_should_resolve_every_registered_event_handler_without_an_open_override(self) -> None:
        injector = Injector(modules, auto_bind=False)
        registered = injector.get(EventHandlerRegistry).registered_handlers()

        assert registered
        assert all(isinstance(injector.get(handler_type), handler_type) for handler_type in registered)

    def test_should_resolve_every_tick_detector_from_the_invocation_inputs(self) -> None:
        bind_invocation_inputs("owner/repo", ".")

        with container.override(Github, github_client_for_any_repo()):
            detectors = [container.get(detector_type) for detector_type in DETECTORS]

        assert [type(detector) for detector in detectors] == DETECTORS

    def test_should_resolve_the_delivery_labels_from_the_invocation_inputs(self) -> None:
        bind_invocation_inputs("owner/repo", ".")

        with container.override(Github, github_client_for_any_repo()):
            delivery_labels = container.get(GithubDeliveryLabels)

        assert isinstance(delivery_labels, GithubDeliveryLabels)

    def test_should_resolve_the_closing_of_abandoned_runs_without_an_open_override(self) -> None:
        injector = Injector(modules, auto_bind=False)
        injector.binder.bind(TargetRepo, TargetRepo("owner/repo"))

        assert isinstance(resolve(injector, AbandonedAgentRuns), LocalAbandonedAgentRuns)
        assert isinstance(injector.get(AgentRunAbandonedDetector), AgentRunAbandonedDetector)
        assert isinstance(injector.get(CloseAgentRunCommandHandler), CloseAgentRunCommandHandler)

    def test_should_resolve_the_workspace_sweep_with_processes_and_docker_without_an_open_override(self) -> None:
        injector = Injector(modules, auto_bind=False)

        assert isinstance(resolve(injector, WorkspaceProcesses), SignalWorkspaceProcesses)
        assert isinstance(resolve(injector, WorkspaceContainers), DockerWorkspaceContainers)
        assert isinstance(injector.get(RemoveAgentWorkspaceCommandHandler), RemoveAgentWorkspaceCommandHandler)
