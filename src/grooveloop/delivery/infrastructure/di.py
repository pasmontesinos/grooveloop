from __future__ import annotations

from github import Github
from injector import Binder, Module, provider

from grooveloop.delivery.application.commands.address_review_changes import (
    AddressReviewChangesCommandHandler,
)
from grooveloop.delivery.application.commands.block_slice import BlockSliceCommandHandler
from grooveloop.delivery.application.commands.close_agent_run import CloseAgentRunCommandHandler
from grooveloop.delivery.application.commands.close_without_merge import (
    CloseWithoutMergeCommandHandler,
)
from grooveloop.delivery.application.commands.complete_review import (
    CompleteReviewCommandHandler,
)
from grooveloop.delivery.application.commands.dispatch_slice import DispatchSliceCommandHandler
from grooveloop.delivery.application.commands.fail_addressing_changes import (
    FailAddressingChangesCommandHandler,
)
from grooveloop.delivery.application.commands.fail_dispatched_slice import (
    FailDispatchedSliceCommandHandler,
)
from grooveloop.delivery.application.commands.mark_merged import (
    MarkMergedCommandHandler,
)
from grooveloop.delivery.application.commands.merge_pull_request import MergePullRequestCommandHandler
from grooveloop.delivery.application.commands.relaunch_implementation import (
    RelaunchImplementationCommandHandler,
)
from grooveloop.delivery.application.commands.relaunch_review_phase import (
    RelaunchReviewPhaseCommandHandler,
)
from grooveloop.delivery.application.commands.remove_agent_workspace import (
    RemoveAgentWorkspaceCommandHandler,
)
from grooveloop.delivery.application.commands.resume_implementation import ResumeImplementationCommandHandler
from grooveloop.delivery.application.commands.resume_review_phase import ResumeReviewPhaseCommandHandler
from grooveloop.delivery.application.commands.review_pull_request import (
    ReviewPullRequestCommandHandler,
)
from grooveloop.delivery.application.queries.all_slices_merged import AllSlicesMergedQueryHandler
from grooveloop.delivery.application.queries.list_repo_sessions import ListRepoSessionsQueryHandler
from grooveloop.delivery.application.queries.list_slice_sessions import ListSliceSessionsQueryHandler
from grooveloop.delivery.application.queries.next_dispatchable_slices import (
    NextDispatchableSlicesQuery,
    NextDispatchableSlicesQueryHandler,
)
from grooveloop.delivery.application.queries.story_pull_request_numbers import (
    StoryPullRequestNumbersQueryHandler,
)
from grooveloop.delivery.application.services.agent_run_failure_cause import AgentRunFailureCause
from grooveloop.delivery.application.services.implementation_recovery import ImplementationRecovery
from grooveloop.delivery.application.services.review_phase_recovery import ReviewPhaseRecovery
from grooveloop.delivery.application.services.slice_retry import SliceRetry
from grooveloop.delivery.application.tasks.addressing_task import AddressingTask
from grooveloop.delivery.application.tasks.implementation_task import ImplementationTask
from grooveloop.delivery.application.tasks.review_task import ReviewTask
from grooveloop.delivery.application.tasks.story_journal_section import StoryJournalSection
from grooveloop.delivery.domain.agent_session_repository import AgentSessionRepository
from grooveloop.delivery.domain.events import (
    AgentRunAbandoned,
    AgentRunFailed,
    AgentWorkspaceAbandoned,
    BlockingReviewDetected,
    HumanDecisionRequired,
    ImplementationIncomplete,
    ImplementationInterrupted,
    PullRequestApproved,
    PullRequestClosed,
    PullRequestMerged,
    PullRequestOpened,
    ReReviewRequired,
    ReviewChangesRequested,
    ReviewChangesUnaddressed,
    ReviewCompleted,
    ReviewPhaseIncomplete,
    ReviewPhaseInterrupted,
    SliceReadyToDispatch,
)
from grooveloop.delivery.domain.pull_request_merger import PullRequestMerger
from grooveloop.delivery.domain.slice_labels import SliceLabels
from grooveloop.delivery.domain.slice_repository import SliceRepository
from grooveloop.delivery.infrastructure.auto_merge import AutoMerge
from grooveloop.delivery.infrastructure.detectors.agent_run_abandoned_detector import AgentRunAbandonedDetector
from grooveloop.delivery.infrastructure.detectors.agent_run_failed_detector import (
    AgentRunFailedDetector,
)
from grooveloop.delivery.infrastructure.detectors.agent_workspace_abandoned_detector import (
    AgentWorkspaceAbandonedDetector,
)
from grooveloop.delivery.infrastructure.detectors.implementation_incomplete_detector import (
    ImplementationIncompleteDetector,
)
from grooveloop.delivery.infrastructure.detectors.implementation_interrupted_detector import (
    ImplementationInterruptedDetector,
)
from grooveloop.delivery.infrastructure.detectors.pull_request_approved_detector import (
    PullRequestApprovedDetector,
)
from grooveloop.delivery.infrastructure.detectors.pull_request_closed_detector import (
    PullRequestClosedDetector,
)
from grooveloop.delivery.infrastructure.detectors.pull_request_merged_detector import (
    PullRequestMergedDetector,
)
from grooveloop.delivery.infrastructure.detectors.pull_request_opened_detector import (
    PullRequestOpenedDetector,
)
from grooveloop.delivery.infrastructure.detectors.re_review_required_detector import (
    ReReviewRequiredDetector,
)
from grooveloop.delivery.infrastructure.detectors.review_changes_requested_detector import (
    ReviewChangesRequestedDetector,
)
from grooveloop.delivery.infrastructure.detectors.review_changes_unaddressed_detector import (
    ReviewChangesUnaddressedDetector,
)
from grooveloop.delivery.infrastructure.detectors.review_outcome_detector import (
    ReviewOutcomeDetector,
)
from grooveloop.delivery.infrastructure.detectors.review_phase_incomplete_detector import (
    ReviewPhaseIncompleteDetector,
)
from grooveloop.delivery.infrastructure.detectors.review_phase_interrupted_detector import (
    ReviewPhaseInterruptedDetector,
)
from grooveloop.delivery.infrastructure.detectors.slice_ready_to_dispatch_detector import (
    SliceReadyToDispatchDetector,
)
from grooveloop.delivery.infrastructure.event_handlers.address_review_changes_when_blocking_review_detected import (
    AddressReviewChangesWhenBlockingReviewDetected,
)
from grooveloop.delivery.infrastructure.event_handlers.address_review_changes_when_review_changes_requested import (
    AddressReviewChangesWhenReviewChangesRequested,
)
from grooveloop.delivery.infrastructure.event_handlers.block_slice_when_human_decision_required import (
    BlockSliceWhenHumanDecisionRequired,
)
from grooveloop.delivery.infrastructure.event_handlers.close_agent_run_when_agent_run_abandoned import (
    CloseAgentRunWhenAgentRunAbandoned,
)
from grooveloop.delivery.infrastructure.event_handlers.close_without_merge_when_pull_request_closed import (
    CloseWithoutMergeWhenPullRequestClosed,
)
from grooveloop.delivery.infrastructure.event_handlers.complete_review_when_review_completed import (
    CompleteReviewWhenReviewCompleted,
)
from grooveloop.delivery.infrastructure.event_handlers.dispatch_slice_when_slice_ready_to_dispatch import (
    DispatchSliceWhenSliceReadyToDispatch,
)
from grooveloop.delivery.infrastructure.event_handlers.fail_addressing_changes_when_review_changes_unaddressed import (
    FailAddressingChangesWhenReviewChangesUnaddressed,
)
from grooveloop.delivery.infrastructure.event_handlers.fail_dispatched_slice_when_agent_run_failed import (
    FailDispatchedSliceWhenAgentRunFailed,
)
from grooveloop.delivery.infrastructure.event_handlers.mark_merged_when_pull_request_merged import (
    MarkMergedWhenPullRequestMerged,
)
from grooveloop.delivery.infrastructure.event_handlers.merge_pull_request_when_pull_request_approved import (
    MergePullRequestWhenPullRequestApproved,
)
from grooveloop.delivery.infrastructure.event_handlers.relaunch_implementation_when_implementation_interrupted import (
    RelaunchImplementationWhenImplementationInterrupted,
)
from grooveloop.delivery.infrastructure.event_handlers.relaunch_review_phase_when_review_phase_interrupted import (
    RelaunchReviewPhaseWhenReviewPhaseInterrupted,
)
from grooveloop.delivery.infrastructure.event_handlers.remove_agent_workspace_when_agent_workspace_abandoned import (
    RemoveAgentWorkspaceWhenAgentWorkspaceAbandoned,
)
from grooveloop.delivery.infrastructure.event_handlers.resume_implementation_when_implementation_incomplete import (
    ResumeImplementationWhenImplementationIncomplete,
)
from grooveloop.delivery.infrastructure.event_handlers.resume_review_phase_when_review_phase_incomplete import (
    ResumeReviewPhaseWhenReviewPhaseIncomplete,
)
from grooveloop.delivery.infrastructure.event_handlers.review_pull_request_when_pull_request_opened import (
    ReviewPullRequestWhenPullRequestOpened,
)
from grooveloop.delivery.infrastructure.event_handlers.review_pull_request_when_re_review_required import (
    ReviewPullRequestWhenReReviewRequired,
)
from grooveloop.delivery.infrastructure.github_delivery_labels import GithubDeliveryLabels
from grooveloop.delivery.infrastructure.github_pull_request_merger import GithubPullRequestMerger
from grooveloop.delivery.infrastructure.github_pull_request_merger_probe import GithubPullRequestMergerProbe
from grooveloop.delivery.infrastructure.github_slice_labels import GithubSliceLabels
from grooveloop.delivery.infrastructure.github_slice_repository import GithubSliceRepository
from grooveloop.delivery.infrastructure.local_agent_session_repository import LocalAgentSessionRepository
from grooveloop.delivery.infrastructure.max_review_rounds import MaxReviewRounds
from grooveloop.shared.application.queries.all_slices_merged import AllSlicesMergedQuery
from grooveloop.shared.application.queries.list_repo_sessions import ListRepoSessionsQuery
from grooveloop.shared.application.queries.query_bus import QueryBus
from grooveloop.shared.application.queries.story_pull_request_numbers import StoryPullRequestNumbersQuery
from grooveloop.shared.domain.abandoned_agent_runs import AbandonedAgentRuns
from grooveloop.shared.domain.agent_profiles import AgentProfiles
from grooveloop.shared.domain.agent_runner import AgentRunner
from grooveloop.shared.domain.agent_runner_registry import AgentRunnerRegistry
from grooveloop.shared.domain.agent_workspaces import AgentWorkspaces
from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.domain.workspace_containers import WorkspaceContainers
from grooveloop.shared.domain.workspace_processes import WorkspaceProcesses
from grooveloop.shared.infrastructure.agent_log_readers import AgentLogReaders
from grooveloop.shared.infrastructure.event_handler_binding import bind_event_handlers
from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
from grooveloop.shared.infrastructure.injector_lookup import resolve
from grooveloop.shared.infrastructure.runs_dir import RunsDir
from grooveloop.shared.infrastructure.target_repo import TargetRepo
from grooveloop.shared.infrastructure.target_repository import target_repository


class DeliveryModule(Module):
    def configure(self, binder: Binder) -> None:
        query_bus = resolve(binder.injector, QueryBus)
        query_bus.register(AllSlicesMergedQuery, AllSlicesMergedQueryHandler)
        query_bus.register(StoryPullRequestNumbersQuery, StoryPullRequestNumbersQueryHandler)
        query_bus.register(ListRepoSessionsQuery, ListRepoSessionsQueryHandler)
        query_bus.register(NextDispatchableSlicesQuery, NextDispatchableSlicesQueryHandler)

        bind_event_handlers(
            binder,
            {
                PullRequestOpened: ReviewPullRequestWhenPullRequestOpened,
                ReviewCompleted: CompleteReviewWhenReviewCompleted,
                HumanDecisionRequired: BlockSliceWhenHumanDecisionRequired,
                PullRequestApproved: MergePullRequestWhenPullRequestApproved,
                PullRequestMerged: MarkMergedWhenPullRequestMerged,
                PullRequestClosed: CloseWithoutMergeWhenPullRequestClosed,
                ReviewChangesRequested: AddressReviewChangesWhenReviewChangesRequested,
                BlockingReviewDetected: AddressReviewChangesWhenBlockingReviewDetected,
                ReReviewRequired: ReviewPullRequestWhenReReviewRequired,
                ReviewChangesUnaddressed: FailAddressingChangesWhenReviewChangesUnaddressed,
                AgentRunFailed: FailDispatchedSliceWhenAgentRunFailed,
                ImplementationInterrupted: RelaunchImplementationWhenImplementationInterrupted,
                ImplementationIncomplete: ResumeImplementationWhenImplementationIncomplete,
                ReviewPhaseInterrupted: RelaunchReviewPhaseWhenReviewPhaseInterrupted,
                ReviewPhaseIncomplete: ResumeReviewPhaseWhenReviewPhaseIncomplete,
                SliceReadyToDispatch: DispatchSliceWhenSliceReadyToDispatch,
                AgentWorkspaceAbandoned: RemoveAgentWorkspaceWhenAgentWorkspaceAbandoned,
                AgentRunAbandoned: CloseAgentRunWhenAgentRunAbandoned,
            },
        )

    @provider
    def slice_repository(self, github: Github, target_repo: TargetRepo, cache: GithubReadCache) -> SliceRepository:
        return GithubSliceRepository(target_repository(github, target_repo, cache), cache)

    @provider
    def delivery_labels(self, github: Github, target_repo: TargetRepo, cache: GithubReadCache) -> GithubDeliveryLabels:
        return GithubDeliveryLabels(target_repository(github, target_repo, cache))

    @provider
    def slice_labels(self, github: Github, target_repo: TargetRepo, cache: GithubReadCache) -> SliceLabels:
        return GithubSliceLabels(target_repository(github, target_repo, cache))

    @provider
    def agent_session_repository(
        self, clock: Clock, runs_dir: RunsDir, log_readers: AgentLogReaders
    ) -> AgentSessionRepository:
        return LocalAgentSessionRepository(runs_dir=runs_dir.value, clock=clock, log_readers=log_readers.value)

    @provider
    def dispatch_slice_command_handler(
        self,
        slice_repository: SliceRepository,
        agent_runner_registry: AgentRunnerRegistry,
        agent_profiles: AgentProfiles,
        slice_labels: SliceLabels,
        implementation_task: ImplementationTask,
    ) -> DispatchSliceCommandHandler:
        return DispatchSliceCommandHandler(
            slice_repository=slice_repository,
            agent_runner_registry=agent_runner_registry,
            agent_profiles=agent_profiles,
            slice_labels=slice_labels,
            implementation_task=implementation_task,
        )

    @provider
    def story_journal_section(self, query_bus: QueryBus) -> StoryJournalSection:
        return StoryJournalSection(query_bus=query_bus)

    @provider
    def implementation_task(
        self, query_bus: QueryBus, story_journal_section: StoryJournalSection
    ) -> ImplementationTask:
        return ImplementationTask(query_bus=query_bus, story_journal_section=story_journal_section)

    @provider
    def review_task(self, story_journal_section: StoryJournalSection) -> ReviewTask:
        return ReviewTask(story_journal_section=story_journal_section)

    @provider
    def addressing_task(self) -> AddressingTask:
        return AddressingTask()

    @provider
    def implementation_recovery(
        self,
        agent_runner: AgentRunner,
        agent_runner_registry: AgentRunnerRegistry,
        agent_profiles: AgentProfiles,
        implementation_task: ImplementationTask,
    ) -> ImplementationRecovery:
        return ImplementationRecovery(
            agent_runner=agent_runner,
            agent_runner_registry=agent_runner_registry,
            agent_profiles=agent_profiles,
            implementation_task=implementation_task,
        )

    @provider
    def review_phase_recovery(
        self,
        agent_runner_registry: AgentRunnerRegistry,
        agent_profiles: AgentProfiles,
        review_task: ReviewTask,
        addressing_task: AddressingTask,
    ) -> ReviewPhaseRecovery:
        return ReviewPhaseRecovery(
            agent_runner_registry=agent_runner_registry,
            agent_profiles=agent_profiles,
            review_task=review_task,
            addressing_task=addressing_task,
        )

    @provider
    def slice_retry(self, slice_repository: SliceRepository, clock: Clock) -> SliceRetry:
        return SliceRetry(slice_repository=slice_repository, clock=clock)

    @provider
    def agent_run_failure_cause(self, agent_runner: AgentRunner) -> AgentRunFailureCause:
        return AgentRunFailureCause(agent_runner=agent_runner)

    @provider
    def review_pull_request_command_handler(
        self,
        slice_repository: SliceRepository,
        agent_runner_registry: AgentRunnerRegistry,
        agent_profiles: AgentProfiles,
        review_task: ReviewTask,
    ) -> ReviewPullRequestCommandHandler:
        return ReviewPullRequestCommandHandler(
            slice_repository=slice_repository,
            agent_runner_registry=agent_runner_registry,
            agent_profiles=agent_profiles,
            review_task=review_task,
        )

    @provider
    def pull_request_opened_detector(self, slice_repository: SliceRepository) -> PullRequestOpenedDetector:
        return PullRequestOpenedDetector(slice_repository=slice_repository)

    @provider
    def complete_review_command_handler(self, slice_repository: SliceRepository) -> CompleteReviewCommandHandler:
        return CompleteReviewCommandHandler(slice_repository=slice_repository)

    @provider
    def block_slice_command_handler(self, slice_repository: SliceRepository) -> BlockSliceCommandHandler:
        return BlockSliceCommandHandler(slice_repository=slice_repository)

    @provider
    def review_outcome_detector(
        self, slice_repository: SliceRepository, agent_runner: AgentRunner, max_review_rounds: MaxReviewRounds
    ) -> ReviewOutcomeDetector:
        return ReviewOutcomeDetector(
            slice_repository=slice_repository, agent_runner=agent_runner, max_review_rounds=max_review_rounds
        )

    @provider
    def mark_merged_command_handler(self, slice_repository: SliceRepository) -> MarkMergedCommandHandler:
        return MarkMergedCommandHandler(slice_repository=slice_repository)

    @provider
    def pull_request_merged_detector(self, slice_repository: SliceRepository) -> PullRequestMergedDetector:
        return PullRequestMergedDetector(slice_repository=slice_repository)

    @provider
    def pull_request_merger(self, github: Github, target_repo: TargetRepo, cache: GithubReadCache) -> PullRequestMerger:
        return GithubPullRequestMerger(target_repository(github, target_repo, cache))

    @provider
    def pull_request_merger_probe(
        self, github: Github, target_repo: TargetRepo, cache: GithubReadCache
    ) -> GithubPullRequestMergerProbe:
        return GithubPullRequestMergerProbe(target_repository(github, target_repo, cache))

    @provider
    def merge_pull_request_command_handler(
        self, slice_repository: SliceRepository, pull_request_merger: PullRequestMerger
    ) -> MergePullRequestCommandHandler:
        return MergePullRequestCommandHandler(
            slice_repository=slice_repository, pull_request_merger=pull_request_merger
        )

    @provider
    def pull_request_approved_detector(
        self, slice_repository: SliceRepository, auto_merge: AutoMerge
    ) -> PullRequestApprovedDetector:
        return PullRequestApprovedDetector(slice_repository=slice_repository, auto_merge=auto_merge)

    @provider
    def close_without_merge_command_handler(self, slice_repository: SliceRepository) -> CloseWithoutMergeCommandHandler:
        return CloseWithoutMergeCommandHandler(slice_repository=slice_repository)

    @provider
    def pull_request_closed_detector(self, slice_repository: SliceRepository) -> PullRequestClosedDetector:
        return PullRequestClosedDetector(slice_repository=slice_repository)

    @provider
    def address_review_changes_command_handler(
        self,
        slice_repository: SliceRepository,
        agent_runner_registry: AgentRunnerRegistry,
        agent_profiles: AgentProfiles,
        addressing_task: AddressingTask,
    ) -> AddressReviewChangesCommandHandler:
        return AddressReviewChangesCommandHandler(
            slice_repository=slice_repository,
            agent_runner_registry=agent_runner_registry,
            agent_profiles=agent_profiles,
            addressing_task=addressing_task,
        )

    @provider
    def review_changes_requested_detector(self, slice_repository: SliceRepository) -> ReviewChangesRequestedDetector:
        return ReviewChangesRequestedDetector(slice_repository=slice_repository)

    @provider
    def re_review_required_detector(self, slice_repository: SliceRepository) -> ReReviewRequiredDetector:
        return ReReviewRequiredDetector(slice_repository=slice_repository)

    @provider
    def fail_addressing_changes_command_handler(
        self, slice_repository: SliceRepository, agent_run_failure_cause: AgentRunFailureCause
    ) -> FailAddressingChangesCommandHandler:
        return FailAddressingChangesCommandHandler(
            slice_repository=slice_repository, agent_run_failure_cause=agent_run_failure_cause
        )

    @provider
    def review_changes_unaddressed_detector(
        self, slice_repository: SliceRepository, agent_runner: AgentRunner
    ) -> ReviewChangesUnaddressedDetector:
        return ReviewChangesUnaddressedDetector(slice_repository=slice_repository, agent_runner=agent_runner)

    @provider
    def fail_dispatched_slice_command_handler(
        self, slice_repository: SliceRepository, agent_run_failure_cause: AgentRunFailureCause
    ) -> FailDispatchedSliceCommandHandler:
        return FailDispatchedSliceCommandHandler(
            slice_repository=slice_repository, agent_run_failure_cause=agent_run_failure_cause
        )

    @provider
    def agent_run_failed_detector(
        self, slice_repository: SliceRepository, agent_runner: AgentRunner
    ) -> AgentRunFailedDetector:
        return AgentRunFailedDetector(slice_repository=slice_repository, agent_runner=agent_runner)

    @provider
    def relaunch_implementation_command_handler(
        self,
        slice_repository: SliceRepository,
        agent_runner: AgentRunner,
        implementation_recovery: ImplementationRecovery,
        slice_retry: SliceRetry,
    ) -> RelaunchImplementationCommandHandler:
        return RelaunchImplementationCommandHandler(
            slice_repository=slice_repository,
            agent_runner=agent_runner,
            implementation_recovery=implementation_recovery,
            slice_retry=slice_retry,
        )

    @provider
    def resume_implementation_command_handler(
        self,
        slice_repository: SliceRepository,
        agent_runner: AgentRunner,
        implementation_recovery: ImplementationRecovery,
        slice_retry: SliceRetry,
    ) -> ResumeImplementationCommandHandler:
        return ResumeImplementationCommandHandler(
            slice_repository=slice_repository,
            agent_runner=agent_runner,
            implementation_recovery=implementation_recovery,
            slice_retry=slice_retry,
        )

    @provider
    def implementation_incomplete_detector(
        self, slice_repository: SliceRepository, agent_runner: AgentRunner
    ) -> ImplementationIncompleteDetector:
        return ImplementationIncompleteDetector(slice_repository=slice_repository, agent_runner=agent_runner)

    @provider
    def implementation_interrupted_detector(
        self, slice_repository: SliceRepository, agent_runner: AgentRunner
    ) -> ImplementationInterruptedDetector:
        return ImplementationInterruptedDetector(slice_repository=slice_repository, agent_runner=agent_runner)

    @provider
    def resume_review_phase_command_handler(
        self,
        slice_repository: SliceRepository,
        agent_runner: AgentRunner,
        review_phase_recovery: ReviewPhaseRecovery,
        slice_retry: SliceRetry,
    ) -> ResumeReviewPhaseCommandHandler:
        return ResumeReviewPhaseCommandHandler(
            slice_repository=slice_repository,
            agent_runner=agent_runner,
            review_phase_recovery=review_phase_recovery,
            slice_retry=slice_retry,
        )

    @provider
    def review_phase_incomplete_detector(
        self, slice_repository: SliceRepository, agent_runner: AgentRunner
    ) -> ReviewPhaseIncompleteDetector:
        return ReviewPhaseIncompleteDetector(slice_repository=slice_repository, agent_runner=agent_runner)

    @provider
    def relaunch_review_phase_command_handler(
        self,
        slice_repository: SliceRepository,
        agent_runner: AgentRunner,
        review_phase_recovery: ReviewPhaseRecovery,
        slice_retry: SliceRetry,
    ) -> RelaunchReviewPhaseCommandHandler:
        return RelaunchReviewPhaseCommandHandler(
            slice_repository=slice_repository,
            agent_runner=agent_runner,
            review_phase_recovery=review_phase_recovery,
            slice_retry=slice_retry,
        )

    @provider
    def review_phase_interrupted_detector(
        self, slice_repository: SliceRepository, agent_runner: AgentRunner
    ) -> ReviewPhaseInterruptedDetector:
        return ReviewPhaseInterruptedDetector(slice_repository=slice_repository, agent_runner=agent_runner)

    @provider
    def remove_agent_workspace_command_handler(
        self,
        agent_workspaces: AgentWorkspaces,
        workspace_processes: WorkspaceProcesses,
        workspace_containers: WorkspaceContainers,
    ) -> RemoveAgentWorkspaceCommandHandler:
        return RemoveAgentWorkspaceCommandHandler(
            agent_workspaces=agent_workspaces,
            workspace_processes=workspace_processes,
            workspace_containers=workspace_containers,
        )

    @provider
    def slice_ready_to_dispatch_detector(
        self, slice_repository: SliceRepository, query_bus: QueryBus
    ) -> SliceReadyToDispatchDetector:
        return SliceReadyToDispatchDetector(slice_repository=slice_repository, query_bus=query_bus)

    @provider
    def agent_workspace_abandoned_detector(self, agent_workspaces: AgentWorkspaces) -> AgentWorkspaceAbandonedDetector:
        return AgentWorkspaceAbandonedDetector(agent_workspaces=agent_workspaces)

    @provider
    def close_agent_run_command_handler(self, abandoned_agent_runs: AbandonedAgentRuns) -> CloseAgentRunCommandHandler:
        return CloseAgentRunCommandHandler(abandoned_agent_runs=abandoned_agent_runs)

    @provider
    def agent_run_abandoned_detector(
        self, abandoned_agent_runs: AbandonedAgentRuns, target_repo: TargetRepo
    ) -> AgentRunAbandonedDetector:
        return AgentRunAbandonedDetector(abandoned_agent_runs=abandoned_agent_runs, target_repo=target_repo)

    @provider
    def list_slice_sessions_query_handler(
        self, agent_session_repository: AgentSessionRepository
    ) -> ListSliceSessionsQueryHandler:
        return ListSliceSessionsQueryHandler(agent_session_repository=agent_session_repository)

    @provider
    def list_repo_sessions_query_handler(
        self, agent_session_repository: AgentSessionRepository
    ) -> ListRepoSessionsQueryHandler:
        return ListRepoSessionsQueryHandler(agent_session_repository=agent_session_repository)

    @provider
    def all_slices_merged_query_handler(self, slice_repository: SliceRepository) -> AllSlicesMergedQueryHandler:
        return AllSlicesMergedQueryHandler(slice_repository=slice_repository)

    @provider
    def next_dispatchable_slices_query_handler(
        self, slice_repository: SliceRepository
    ) -> NextDispatchableSlicesQueryHandler:
        return NextDispatchableSlicesQueryHandler(slice_repository=slice_repository)

    @provider
    def story_pull_request_numbers_query_handler(
        self, slice_repository: SliceRepository
    ) -> StoryPullRequestNumbersQueryHandler:
        return StoryPullRequestNumbersQueryHandler(slice_repository=slice_repository)
