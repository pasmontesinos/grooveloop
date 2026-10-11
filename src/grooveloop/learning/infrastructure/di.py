from __future__ import annotations

from github import Github
from injector import Binder, Module, provider

from grooveloop.learning.application.commands.close_lesson import CloseLessonCommandHandler
from grooveloop.learning.application.commands.discard_lesson import DiscardLessonCommandHandler
from grooveloop.learning.application.commands.learn_lesson import LearnLessonCommandHandler
from grooveloop.learning.application.commands.refine_conventions import RefineConventionsCommandHandler
from grooveloop.learning.application.queries.pending_lessons import PendingLessonsQueryHandler
from grooveloop.learning.application.queries.story_lessons import StoryLessonsQueryHandler
from grooveloop.learning.application.queries.uncaptured_lessons import UncapturedLessonsQueryHandler
from grooveloop.learning.application.tasks.refinement_task import RefinementTask
from grooveloop.learning.domain.conventions_pull_request_status import ConventionsPullRequestStatus
from grooveloop.learning.domain.events import LessonCaptured, LessonDiscarded, LessonLearned, LessonResolved
from grooveloop.learning.domain.learn_signal import LearnSignal
from grooveloop.learning.domain.lesson_repository import LessonRepository
from grooveloop.learning.domain.refinement_result import RefinementResult
from grooveloop.learning.infrastructure.detectors.lesson_captured_detector import LessonCapturedDetector
from grooveloop.learning.infrastructure.detectors.lesson_resolved_detector import LessonResolvedDetector
from grooveloop.learning.infrastructure.detectors.refinement_outcome_detector import RefinementOutcomeDetector
from grooveloop.learning.infrastructure.event_handlers.close_lesson_when_lesson_resolved import (
    CloseLessonWhenLessonResolved,
)
from grooveloop.learning.infrastructure.event_handlers.discard_lesson_when_lesson_discarded import (
    DiscardLessonWhenLessonDiscarded,
)
from grooveloop.learning.infrastructure.event_handlers.learn_lesson_when_lesson_learned import (
    LearnLessonWhenLessonLearned,
)
from grooveloop.learning.infrastructure.event_handlers.refine_conventions_when_lesson_captured import (
    RefineConventionsWhenLessonCaptured,
)
from grooveloop.learning.infrastructure.github_conventions_pull_request_status import (
    GithubConventionsPullRequestStatus,
)
from grooveloop.learning.infrastructure.github_learn_signal import GithubLearnSignal
from grooveloop.learning.infrastructure.github_lesson_repository import GithubLessonRepository
from grooveloop.learning.infrastructure.github_refinement_result import GithubRefinementResult
from grooveloop.shared.application.queries.pending_lessons import PendingLessonsQuery
from grooveloop.shared.application.queries.query_bus import QueryBus
from grooveloop.shared.application.queries.uncaptured_lessons import UncapturedLessonsQuery
from grooveloop.shared.domain.agent_profiles import AgentProfiles
from grooveloop.shared.domain.agent_runner_registry import AgentRunnerRegistry
from grooveloop.shared.infrastructure.event_handler_binding import bind_event_handlers
from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
from grooveloop.shared.infrastructure.injector_lookup import resolve
from grooveloop.shared.infrastructure.target_repo import TargetRepo
from grooveloop.shared.infrastructure.target_repository import target_repository


class LearningModule(Module):
    def configure(self, binder: Binder) -> None:
        bind_event_handlers(
            binder,
            {
                LessonCaptured: RefineConventionsWhenLessonCaptured,
                LessonLearned: LearnLessonWhenLessonLearned,
                LessonDiscarded: DiscardLessonWhenLessonDiscarded,
                LessonResolved: CloseLessonWhenLessonResolved,
            },
        )

        query_bus = resolve(binder.injector, QueryBus)
        query_bus.register(PendingLessonsQuery, PendingLessonsQueryHandler)
        query_bus.register(UncapturedLessonsQuery, UncapturedLessonsQueryHandler)

    @provider
    def lesson_repository(self, github: Github, target_repo: TargetRepo, cache: GithubReadCache) -> LessonRepository:
        return GithubLessonRepository(target_repository(github, target_repo, cache), cache)

    @provider
    def conventions_pull_request_status(
        self, github: Github, target_repo: TargetRepo, cache: GithubReadCache
    ) -> ConventionsPullRequestStatus:
        return GithubConventionsPullRequestStatus(target_repository(github, target_repo, cache), cache)

    @provider
    def learn_signal(self, github: Github, target_repo: TargetRepo, cache: GithubReadCache) -> LearnSignal:
        return GithubLearnSignal(target_repository(github, target_repo, cache), cache)

    @provider
    def refinement_result(self, github: Github, target_repo: TargetRepo, cache: GithubReadCache) -> RefinementResult:
        return GithubRefinementResult(target_repository(github, target_repo, cache), cache)

    @provider
    def refine_conventions_command_handler(
        self,
        agent_runner_registry: AgentRunnerRegistry,
        agent_profiles: AgentProfiles,
        lesson_repository: LessonRepository,
        refinement_task: RefinementTask,
    ) -> RefineConventionsCommandHandler:
        return RefineConventionsCommandHandler(
            agent_runner_registry=agent_runner_registry,
            agent_profiles=agent_profiles,
            lesson_repository=lesson_repository,
            refinement_task=refinement_task,
        )

    @provider
    def refinement_task(self) -> RefinementTask:
        return RefinementTask()

    @provider
    def learn_lesson_command_handler(self, lesson_repository: LessonRepository) -> LearnLessonCommandHandler:
        return LearnLessonCommandHandler(lesson_repository=lesson_repository)

    @provider
    def discard_lesson_command_handler(self, lesson_repository: LessonRepository) -> DiscardLessonCommandHandler:
        return DiscardLessonCommandHandler(lesson_repository=lesson_repository)

    @provider
    def close_lesson_command_handler(self, lesson_repository: LessonRepository) -> CloseLessonCommandHandler:
        return CloseLessonCommandHandler(lesson_repository=lesson_repository)

    @provider
    def lesson_captured_detector(
        self, learn_signal: LearnSignal, lesson_repository: LessonRepository
    ) -> LessonCapturedDetector:
        return LessonCapturedDetector(learn_signal=learn_signal, lesson_repository=lesson_repository)

    @provider
    def refinement_outcome_detector(
        self, refinement_result: RefinementResult, lesson_repository: LessonRepository
    ) -> RefinementOutcomeDetector:
        return RefinementOutcomeDetector(refinement_result=refinement_result, lesson_repository=lesson_repository)

    @provider
    def lesson_resolved_detector(
        self,
        lesson_repository: LessonRepository,
        conventions_pull_request_status: ConventionsPullRequestStatus,
    ) -> LessonResolvedDetector:
        return LessonResolvedDetector(
            lesson_repository=lesson_repository,
            conventions_pull_request_status=conventions_pull_request_status,
        )

    @provider
    def pending_lessons_query_handler(
        self,
        lesson_repository: LessonRepository,
        conventions_pull_request_status: ConventionsPullRequestStatus,
    ) -> PendingLessonsQueryHandler:
        return PendingLessonsQueryHandler(
            lesson_repository=lesson_repository,
            conventions_pull_request_status=conventions_pull_request_status,
        )

    @provider
    def story_lessons_query_handler(
        self,
        lesson_repository: LessonRepository,
        conventions_pull_request_status: ConventionsPullRequestStatus,
    ) -> StoryLessonsQueryHandler:
        return StoryLessonsQueryHandler(
            lesson_repository=lesson_repository,
            conventions_pull_request_status=conventions_pull_request_status,
        )

    @provider
    def uncaptured_lessons_query_handler(
        self, learn_signal: LearnSignal, lesson_repository: LessonRepository
    ) -> UncapturedLessonsQueryHandler:
        return UncapturedLessonsQueryHandler(learn_signal=learn_signal, lesson_repository=lesson_repository)
