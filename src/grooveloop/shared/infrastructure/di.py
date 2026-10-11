from __future__ import annotations

from pathlib import Path

from github import Auth, Github
from injector import Injector, Module, provider, singleton

from grooveloop.shared.application.events.event_dispatcher import EventDispatcher
from grooveloop.shared.application.queries.list_loops import ListLoopsQueryHandler
from grooveloop.shared.application.queries.query_bus import QueryBus
from grooveloop.shared.domain.abandoned_agent_runs import AbandonedAgentRuns
from grooveloop.shared.domain.agent_command import AgentCommand
from grooveloop.shared.domain.agent_profiles import AgentProfiles
from grooveloop.shared.domain.agent_run_logs import AgentRunLogs
from grooveloop.shared.domain.agent_runner import AgentRunner
from grooveloop.shared.domain.agent_runner_registry import AgentRunnerRegistry
from grooveloop.shared.domain.agent_workspaces import AgentWorkspaces
from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.domain.loop_presence import LoopPresence
from grooveloop.shared.domain.loop_snapshots import LoopSnapshots
from grooveloop.shared.domain.process_liveness import ProcessLiveness
from grooveloop.shared.domain.pull_request_details import PullRequestDetails
from grooveloop.shared.domain.story_specs import StorySpecs
from grooveloop.shared.domain.workspace_containers import WorkspaceContainers
from grooveloop.shared.domain.workspace_processes import WorkspaceProcesses
from grooveloop.shared.infrastructure.agent_log_readers import AgentLogReaders
from grooveloop.shared.infrastructure.agent_profiles_probe import AgentProfilesProbe
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.claude_command import ClaudeCommand
from grooveloop.shared.infrastructure.claude_log_reader import ClaudeLogReader
from grooveloop.shared.infrastructure.claude_probe import ClaudeProbe
from grooveloop.shared.infrastructure.docker_compose_probe import DockerComposeProbe
from grooveloop.shared.infrastructure.docker_workspace_containers import DockerWorkspaceContainers
from grooveloop.shared.infrastructure.event_handler_registry import EventHandlerRegistry
from grooveloop.shared.infrastructure.filesystem_agent_profiles import FilesystemAgentProfiles
from grooveloop.shared.infrastructure.filesystem_agent_run_logs import FilesystemAgentRunLogs
from grooveloop.shared.infrastructure.filesystem_loop_presence import FilesystemLoopPresence
from grooveloop.shared.infrastructure.filesystem_loop_snapshots import FilesystemLoopSnapshots
from grooveloop.shared.infrastructure.filesystem_pull_request_details import FilesystemPullRequestDetails
from grooveloop.shared.infrastructure.filesystem_story_specs import FilesystemStorySpecs
from grooveloop.shared.infrastructure.github_auth_probe import GithubAuthProbe
from grooveloop.shared.infrastructure.github_graphql_probe import GithubGraphQLProbe
from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
from grooveloop.shared.infrastructure.github_token import github_token
from grooveloop.shared.infrastructure.grooveloop_cli_probe import GrooveloopCliProbe
from grooveloop.shared.infrastructure.injector_event_dispatcher import InjectorEventDispatcher
from grooveloop.shared.infrastructure.injector_query_bus import InjectorQueryBus
from grooveloop.shared.infrastructure.local_abandoned_agent_runs import LocalAbandonedAgentRuns
from grooveloop.shared.infrastructure.local_agent_workspaces import LocalAgentWorkspaces
from grooveloop.shared.infrastructure.mapped_agent_runner_registry import MappedAgentRunnerRegistry
from grooveloop.shared.infrastructure.opencode_command import OpencodeCommand
from grooveloop.shared.infrastructure.opencode_log_reader import OpencodeLogReader
from grooveloop.shared.infrastructure.opencode_probe import OpencodeProbe
from grooveloop.shared.infrastructure.query_handler_registry import QueryHandlerRegistry
from grooveloop.shared.infrastructure.repos_dir import ReposDir
from grooveloop.shared.infrastructure.runs_dir import RunsDir
from grooveloop.shared.infrastructure.signal_process_liveness import SignalProcessLiveness
from grooveloop.shared.infrastructure.signal_workspace_processes import SignalWorkspaceProcesses
from grooveloop.shared.infrastructure.subprocess_agent_runner import SubprocessAgentRunner
from grooveloop.shared.infrastructure.system_clock import SystemClock

_AGENT_COMMANDS: list[AgentCommand] = [ClaudeCommand(), OpencodeCommand()]


class SharedModule(Module):
    @singleton
    @provider
    def clock(self) -> Clock:
        return SystemClock()

    @singleton
    @provider
    def runs_dir(self) -> RunsDir:
        return RunsDir(Path.home() / ".grooveloop" / "runs")

    @singleton
    @provider
    def repos_dir(self) -> ReposDir:
        return ReposDir(Path.home() / ".grooveloop" / "repos")

    @singleton
    @provider
    def agent_log_readers(self) -> AgentLogReaders:
        return AgentLogReaders({reader.engine: reader for reader in [ClaudeLogReader(), OpencodeLogReader()]})

    @singleton
    @provider
    def github_read_cache(self, clock: Clock) -> GithubReadCache:
        return GithubReadCache(clock)

    @singleton
    @provider
    def query_handler_registry(self) -> QueryHandlerRegistry:
        return QueryHandlerRegistry()

    @provider
    def query_bus(self, injector: Injector, registry: QueryHandlerRegistry) -> QueryBus:
        return InjectorQueryBus(injector, registry)

    @singleton
    @provider
    def event_handler_registry(self) -> EventHandlerRegistry:
        return EventHandlerRegistry()

    @provider
    def event_dispatcher(self, injector: Injector, registry: EventHandlerRegistry) -> EventDispatcher:
        return InjectorEventDispatcher(injector, registry)

    @singleton
    @provider
    def github(self) -> Github:
        return Github(auth=Auth.Token(github_token()))

    @provider
    def github_auth_probe(self, github: Github) -> GithubAuthProbe:
        return GithubAuthProbe(github)

    @provider
    def github_graphql_probe(self, github: Github) -> GithubGraphQLProbe:
        return GithubGraphQLProbe(github)

    @provider
    def agent_command(self) -> AgentCommand:
        return ClaudeCommand()

    @provider
    def agent_runner(
        self, clock: Clock, command: AgentCommand, runs_dir: RunsDir, log_readers: AgentLogReaders
    ) -> AgentRunner:
        return SubprocessAgentRunner(
            runs_dir=runs_dir.value, clock=clock, command=command, log_readers=log_readers.value
        )

    @provider
    def agent_runner_registry(
        self, clock: Clock, runs_dir: RunsDir, log_readers: AgentLogReaders
    ) -> AgentRunnerRegistry:
        return MappedAgentRunnerRegistry(
            {
                command.engine: SubprocessAgentRunner(
                    runs_dir=runs_dir.value, clock=clock, command=command, log_readers=log_readers.value
                )
                for command in _AGENT_COMMANDS
            }
        )

    @provider
    def loop_presence(self, clock: Clock, repos_dir: ReposDir) -> LoopPresence:
        return FilesystemLoopPresence(repos_dir=repos_dir.value, clock=clock)

    @provider
    def loop_snapshots(self, repos_dir: ReposDir) -> LoopSnapshots:
        return FilesystemLoopSnapshots(repos_dir=repos_dir.value)

    @provider
    def pull_request_details(self, repos_dir: ReposDir) -> PullRequestDetails:
        return FilesystemPullRequestDetails(repos_dir=repos_dir.value)

    @provider
    def story_specs(self, repos_dir: ReposDir) -> StorySpecs:
        return FilesystemStorySpecs(repos_dir=repos_dir.value)

    @provider
    def agent_run_logs(self, runs_dir: RunsDir, log_readers: AgentLogReaders) -> AgentRunLogs:
        return FilesystemAgentRunLogs(runs_dir=runs_dir.value, log_readers=log_readers.value)

    @provider
    def process_liveness(self) -> ProcessLiveness:
        return SignalProcessLiveness()

    @provider
    def agent_workspaces(self, clock: Clock, runs_dir: RunsDir) -> AgentWorkspaces:
        return LocalAgentWorkspaces(runs_dir=runs_dir.value, clock=clock)

    @provider
    def abandoned_agent_runs(self, clock: Clock, runs_dir: RunsDir) -> AbandonedAgentRuns:
        return LocalAbandonedAgentRuns(runs_dir=runs_dir.value, clock=clock)

    @provider
    def workspace_processes(self) -> WorkspaceProcesses:
        return SignalWorkspaceProcesses()

    @provider
    def workspace_containers(self) -> WorkspaceContainers:
        return DockerWorkspaceContainers()

    @provider
    def claude_probe(self) -> ClaudeProbe:
        return ClaudeProbe()

    @provider
    def opencode_probe(self) -> OpencodeProbe:
        return OpencodeProbe()

    @provider
    def docker_compose_probe(self) -> DockerComposeProbe:
        return DockerComposeProbe()

    @provider
    def grooveloop_cli_probe(self) -> GrooveloopCliProbe:
        return GrooveloopCliProbe()

    @provider
    def agent_profiles(self, agent_workdir: AgentWorkdir) -> AgentProfiles:
        return FilesystemAgentProfiles(workdir=agent_workdir.value)

    @provider
    def agent_profiles_probe(self, agent_profiles: AgentProfiles, agent_workdir: AgentWorkdir) -> AgentProfilesProbe:
        return AgentProfilesProbe(agent_profiles=agent_profiles, workdir=agent_workdir.value)

    @provider
    def list_loops_query_handler(
        self,
        loop_presence: LoopPresence,
        process_liveness: ProcessLiveness,
        loop_snapshots: LoopSnapshots,
        clock: Clock,
        query_bus: QueryBus,
    ) -> ListLoopsQueryHandler:
        return ListLoopsQueryHandler(
            loop_presence=loop_presence,
            process_liveness=process_liveness,
            loop_snapshots=loop_snapshots,
            clock=clock,
            query_bus=query_bus,
        )
