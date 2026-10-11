from __future__ import annotations

from github import Github
from injector import Binder, Module, provider

from grooveloop.shared.application.queries.get_story_spec import GetStorySpecQuery
from grooveloop.shared.application.queries.query_bus import QueryBus
from grooveloop.shared.infrastructure.event_handler_binding import bind_event_handlers
from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
from grooveloop.shared.infrastructure.injector_lookup import resolve
from grooveloop.shared.infrastructure.target_repo import TargetRepo
from grooveloop.shared.infrastructure.target_repository import target_repository
from grooveloop.slicing.application.commands.complete_story import CompleteStoryCommandHandler
from grooveloop.slicing.application.commands.create_slices_from_spec import CreateSlicesFromSpecCommandHandler
from grooveloop.slicing.application.queries.get_story_spec import GetStorySpecQueryHandler
from grooveloop.slicing.domain.events import StoryCompleted, StoryReadyToSlice
from grooveloop.slicing.domain.story_repository import StoryRepository
from grooveloop.slicing.infrastructure.detectors.story_completed_detector import StoryCompletedDetector
from grooveloop.slicing.infrastructure.detectors.story_ready_to_slice_detector import StoryReadyToSliceDetector
from grooveloop.slicing.infrastructure.event_handlers.complete_story_when_story_completed import (
    CompleteStoryWhenStoryCompleted,
)
from grooveloop.slicing.infrastructure.event_handlers.create_slices_from_spec_when_story_ready_to_slice import (
    CreateSlicesFromSpecWhenStoryReadyToSlice,
)
from grooveloop.slicing.infrastructure.github_story_repository import GithubStoryRepository


class SlicingModule(Module):
    def configure(self, binder: Binder) -> None:
        query_bus = resolve(binder.injector, QueryBus)
        query_bus.register(GetStorySpecQuery, GetStorySpecQueryHandler)

        bind_event_handlers(
            binder,
            {
                StoryReadyToSlice: CreateSlicesFromSpecWhenStoryReadyToSlice,
                StoryCompleted: CompleteStoryWhenStoryCompleted,
            },
        )

    @provider
    def story_repository(self, github: Github, target_repo: TargetRepo, cache: GithubReadCache) -> StoryRepository:
        return GithubStoryRepository(target_repository(github, target_repo, cache), cache)

    @provider
    def create_slices_from_spec_command_handler(
        self, story_repository: StoryRepository
    ) -> CreateSlicesFromSpecCommandHandler:
        return CreateSlicesFromSpecCommandHandler(story_repository=story_repository)

    @provider
    def complete_story_command_handler(self, story_repository: StoryRepository) -> CompleteStoryCommandHandler:
        return CompleteStoryCommandHandler(story_repository=story_repository)

    @provider
    def get_story_spec_query_handler(self, story_repository: StoryRepository) -> GetStorySpecQueryHandler:
        return GetStorySpecQueryHandler(story_repository=story_repository)

    @provider
    def story_ready_to_slice_detector(self, story_repository: StoryRepository) -> StoryReadyToSliceDetector:
        return StoryReadyToSliceDetector(story_repository=story_repository)

    @provider
    def story_completed_detector(
        self, story_repository: StoryRepository, query_bus: QueryBus
    ) -> StoryCompletedDetector:
        return StoryCompletedDetector(story_repository=story_repository, query_bus=query_bus)
