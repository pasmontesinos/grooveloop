from __future__ import annotations

from github import Github
from injector import Binder, Module, provider

from grooveloop.shared.application.queries.pending_verifications import PendingVerificationsQuery
from grooveloop.shared.application.queries.query_bus import QueryBus
from grooveloop.shared.domain.agent_profiles import AgentProfiles
from grooveloop.shared.domain.agent_runner import AgentRunner
from grooveloop.shared.domain.agent_runner_registry import AgentRunnerRegistry
from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.infrastructure.event_handler_binding import bind_event_handlers
from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
from grooveloop.shared.infrastructure.injector_lookup import resolve
from grooveloop.shared.infrastructure.target_repo import TargetRepo
from grooveloop.shared.infrastructure.target_repository import target_repository
from grooveloop.verification.application.commands.conclude_verification import ConcludeVerificationCommandHandler
from grooveloop.verification.application.commands.recover_verification import RecoverVerificationCommandHandler
from grooveloop.verification.application.commands.resume_verification import ResumeVerificationCommandHandler
from grooveloop.verification.application.commands.verify_deployment import VerifyDeploymentCommandHandler
from grooveloop.verification.application.queries.pending_verifications import PendingVerificationsQueryHandler
from grooveloop.verification.application.services.verification_recovery import VerificationRecovery
from grooveloop.verification.application.services.verification_retry import VerificationRetry
from grooveloop.verification.application.tasks.verification_task import VerificationTask
from grooveloop.verification.domain.events import (
    SliceReadyToVerify,
    VerificationConcluded,
    VerificationIncomplete,
    VerificationRunFailed,
)
from grooveloop.verification.domain.merged_slice_signal import MergedSliceSignal
from grooveloop.verification.domain.slice_verification_repository import SliceVerificationRepository
from grooveloop.verification.infrastructure.detectors.slice_ready_to_verify_detector import SliceReadyToVerifyDetector
from grooveloop.verification.infrastructure.detectors.verification_concluded_detector import (
    VerificationConcludedDetector,
)
from grooveloop.verification.infrastructure.detectors.verification_incomplete_detector import (
    VerificationIncompleteDetector,
)
from grooveloop.verification.infrastructure.detectors.verification_run_failed_detector import (
    VerificationRunFailedDetector,
)
from grooveloop.verification.infrastructure.event_handlers.conclude_verification_when_verification_concluded import (
    ConcludeVerificationWhenVerificationConcluded,
)
from grooveloop.verification.infrastructure.event_handlers.recover_verification_when_verification_run_failed import (
    RecoverVerificationWhenVerificationRunFailed,
)
from grooveloop.verification.infrastructure.event_handlers.resume_verification_when_verification_incomplete import (
    ResumeVerificationWhenVerificationIncomplete,
)
from grooveloop.verification.infrastructure.event_handlers.verify_deployment_when_slice_ready_to_verify import (
    VerifyDeploymentWhenSliceReadyToVerify,
)
from grooveloop.verification.infrastructure.github_merged_slice_signal import GithubMergedSliceSignal
from grooveloop.verification.infrastructure.github_slice_verification_repository import (
    GithubSliceVerificationRepository,
)


class VerificationModule(Module):
    def configure(self, binder: Binder) -> None:
        bind_event_handlers(
            binder,
            {
                SliceReadyToVerify: VerifyDeploymentWhenSliceReadyToVerify,
                VerificationConcluded: ConcludeVerificationWhenVerificationConcluded,
                VerificationRunFailed: RecoverVerificationWhenVerificationRunFailed,
                VerificationIncomplete: ResumeVerificationWhenVerificationIncomplete,
            },
        )

        query_bus = resolve(binder.injector, QueryBus)
        query_bus.register(PendingVerificationsQuery, PendingVerificationsQueryHandler)

    @provider
    def slice_verification_repository(
        self, github: Github, target_repo: TargetRepo, cache: GithubReadCache
    ) -> SliceVerificationRepository:
        return GithubSliceVerificationRepository(target_repository(github, target_repo, cache), cache)

    @provider
    def merged_slice_signal(self, github: Github, target_repo: TargetRepo, cache: GithubReadCache) -> MergedSliceSignal:
        return GithubMergedSliceSignal(target_repository(github, target_repo, cache), cache)

    @provider
    def pending_verifications_query_handler(
        self, slice_verification_repository: SliceVerificationRepository
    ) -> PendingVerificationsQueryHandler:
        return PendingVerificationsQueryHandler(slice_verification_repository=slice_verification_repository)

    @provider
    def verify_deployment_command_handler(
        self,
        slice_verification_repository: SliceVerificationRepository,
        agent_runner_registry: AgentRunnerRegistry,
        agent_profiles: AgentProfiles,
        verification_task: VerificationTask,
    ) -> VerifyDeploymentCommandHandler:
        return VerifyDeploymentCommandHandler(
            slice_verification_repository=slice_verification_repository,
            agent_runner_registry=agent_runner_registry,
            agent_profiles=agent_profiles,
            verification_task=verification_task,
        )

    @provider
    def verification_task(self) -> VerificationTask:
        return VerificationTask()

    @provider
    def verification_recovery(
        self,
        agent_runner_registry: AgentRunnerRegistry,
        agent_profiles: AgentProfiles,
        verification_task: VerificationTask,
    ) -> VerificationRecovery:
        return VerificationRecovery(
            agent_runner_registry=agent_runner_registry,
            agent_profiles=agent_profiles,
            verification_task=verification_task,
        )

    @provider
    def verification_retry(
        self, slice_verification_repository: SliceVerificationRepository, clock: Clock
    ) -> VerificationRetry:
        return VerificationRetry(slice_verification_repository=slice_verification_repository, clock=clock)

    @provider
    def recover_verification_command_handler(
        self,
        slice_verification_repository: SliceVerificationRepository,
        agent_runner: AgentRunner,
        verification_recovery: VerificationRecovery,
        verification_retry: VerificationRetry,
    ) -> RecoverVerificationCommandHandler:
        return RecoverVerificationCommandHandler(
            slice_verification_repository=slice_verification_repository,
            agent_runner=agent_runner,
            verification_recovery=verification_recovery,
            verification_retry=verification_retry,
        )

    @provider
    def resume_verification_command_handler(
        self,
        slice_verification_repository: SliceVerificationRepository,
        agent_runner: AgentRunner,
        verification_recovery: VerificationRecovery,
        verification_retry: VerificationRetry,
    ) -> ResumeVerificationCommandHandler:
        return ResumeVerificationCommandHandler(
            slice_verification_repository=slice_verification_repository,
            agent_runner=agent_runner,
            verification_recovery=verification_recovery,
            verification_retry=verification_retry,
        )

    @provider
    def conclude_verification_command_handler(
        self, slice_verification_repository: SliceVerificationRepository
    ) -> ConcludeVerificationCommandHandler:
        return ConcludeVerificationCommandHandler(slice_verification_repository=slice_verification_repository)

    @provider
    def slice_ready_to_verify_detector(
        self,
        merged_slice_signal: MergedSliceSignal,
        slice_verification_repository: SliceVerificationRepository,
    ) -> SliceReadyToVerifyDetector:
        return SliceReadyToVerifyDetector(
            merged_slice_signal=merged_slice_signal,
            slice_verification_repository=slice_verification_repository,
        )

    @provider
    def verification_concluded_detector(
        self,
        merged_slice_signal: MergedSliceSignal,
        slice_verification_repository: SliceVerificationRepository,
    ) -> VerificationConcludedDetector:
        return VerificationConcludedDetector(
            merged_slice_signal=merged_slice_signal,
            slice_verification_repository=slice_verification_repository,
        )

    @provider
    def verification_run_failed_detector(
        self,
        merged_slice_signal: MergedSliceSignal,
        slice_verification_repository: SliceVerificationRepository,
        agent_runner: AgentRunner,
    ) -> VerificationRunFailedDetector:
        return VerificationRunFailedDetector(
            merged_slice_signal=merged_slice_signal,
            slice_verification_repository=slice_verification_repository,
            agent_runner=agent_runner,
        )

    @provider
    def verification_incomplete_detector(
        self,
        merged_slice_signal: MergedSliceSignal,
        slice_verification_repository: SliceVerificationRepository,
        agent_runner: AgentRunner,
    ) -> VerificationIncompleteDetector:
        return VerificationIncompleteDetector(
            merged_slice_signal=merged_slice_signal,
            slice_verification_repository=slice_verification_repository,
            agent_runner=agent_runner,
        )
