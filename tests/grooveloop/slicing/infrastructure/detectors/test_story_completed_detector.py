from __future__ import annotations

from grooveloop.shared.application.queries.all_slices_merged import AllSlicesMergedQuery, AllSlicesMergedQueryResult
from grooveloop.shared.application.queries.pending_lessons import (
    PendingLessonDTO,
    PendingLessonsQuery,
    PendingLessonsQueryResult,
)
from grooveloop.shared.application.queries.pending_verifications import (
    PendingVerificationsQuery,
    PendingVerificationsQueryResult,
)
from grooveloop.shared.application.queries.story_pull_request_numbers import (
    StoryPullRequestNumbersQuery,
    StoryPullRequestNumbersQueryResult,
)
from grooveloop.shared.application.queries.uncaptured_lessons import (
    UncapturedLessonsQuery,
    UncapturedLessonsQueryResult,
)
from grooveloop.slicing.domain.story_status import StoryStatus
from grooveloop.slicing.infrastructure.detectors.story_completed_detector import StoryCompletedDetector
from tests.grooveloop.slicing.mothers.story_mother import StoryMother
from tests.playground.shared.infrastructure.fake_query_bus import FakeQueryBus
from tests.playground.shared.infrastructure.fake_story_repository import FakeStoryRepository


def _query_bus(
    merged_story_ids: set[str],
    pull_request_numbers: dict[str, list[int]] | None = None,
    pending: set[int] | None = None,
    uncaptured: set[int] | None = None,
    pending_verifications: dict[str, list[str]] | None = None,
) -> FakeQueryBus:
    numbers = pull_request_numbers or {}
    pending_numbers = pending or set()
    uncaptured_numbers = uncaptured or set()
    verifications = pending_verifications or {}

    return FakeQueryBus(
        {
            AllSlicesMergedQuery: lambda query: AllSlicesMergedQueryResult(
                all_merged=query.story_id in merged_story_ids
            ),
            StoryPullRequestNumbersQuery: lambda query: StoryPullRequestNumbersQueryResult(
                pull_request_numbers=numbers.get(query.story_id, [])
            ),
            PendingLessonsQuery: lambda query: PendingLessonsQueryResult(
                pending_lessons=[
                    PendingLessonDTO(pull_request_number=number, conventions_pull_request_number=None)
                    for number in query.pull_request_numbers
                    if number in pending_numbers
                ]
            ),
            UncapturedLessonsQuery: lambda query: UncapturedLessonsQueryResult(
                pull_request_numbers=[number for number in query.pull_request_numbers if number in uncaptured_numbers]
            ),
            PendingVerificationsQuery: lambda query: PendingVerificationsQueryResult(
                slice_ids=verifications.get(query.story_id, [])
            ),
        }
    )


class TestStoryCompletedDetector:
    def test_emits_for_sliced_stories_whose_slices_are_all_merged(self) -> None:
        repository = FakeStoryRepository()
        repository.save(StoryMother.create(story_id="7", status=StoryStatus.SLICED))
        detector = StoryCompletedDetector(story_repository=repository, query_bus=_query_bus({"7"}))

        assert {event.story_id.value for event in detector.detect()} == {"7"}

    def test_does_not_emit_when_some_slice_is_not_merged(self) -> None:
        repository = FakeStoryRepository()
        repository.save(StoryMother.create(story_id="7", status=StoryStatus.SLICED))
        detector = StoryCompletedDetector(story_repository=repository, query_bus=_query_bus(set()))

        assert list(detector.detect()) == []

    def test_does_not_emit_for_stories_not_yet_sliced(self) -> None:
        repository = FakeStoryRepository()
        repository.save(StoryMother.create(story_id="7", status=StoryStatus.READY_FOR_IMPLEMENTATION))
        detector = StoryCompletedDetector(story_repository=repository, query_bus=_query_bus({"7"}))

        assert list(detector.detect()) == []

    def test_does_not_emit_when_a_slice_has_an_unresolved_lesson(self) -> None:
        repository = FakeStoryRepository()
        repository.save(StoryMother.create(story_id="7", status=StoryStatus.SLICED))
        detector = StoryCompletedDetector(
            story_repository=repository,
            query_bus=_query_bus({"7"}, pull_request_numbers={"7": [100]}, pending={100}),
        )

        assert list(detector.detect()) == []

    def test_emits_when_the_slice_lesson_is_resolved(self) -> None:
        repository = FakeStoryRepository()
        repository.save(StoryMother.create(story_id="7", status=StoryStatus.SLICED))
        detector = StoryCompletedDetector(
            story_repository=repository,
            query_bus=_query_bus({"7"}, pull_request_numbers={"7": [100]}, pending=set()),
        )

        assert {event.story_id.value for event in detector.detect()} == {"7"}

    def test_does_not_emit_when_a_merged_pull_request_carries_an_uncaptured_lesson(self) -> None:
        repository = FakeStoryRepository()
        repository.save(StoryMother.create(story_id="7", status=StoryStatus.SLICED))
        detector = StoryCompletedDetector(
            story_repository=repository,
            query_bus=_query_bus({"7"}, pull_request_numbers={"7": [100]}, uncaptured={100}),
        )

        assert list(detector.detect()) == []

    def test_asks_the_story_pull_request_numbers_only_once(self) -> None:
        repository = FakeStoryRepository()
        repository.save(StoryMother.create(story_id="7", status=StoryStatus.SLICED))
        query_bus = _query_bus({"7"}, pull_request_numbers={"7": [100]})
        detector = StoryCompletedDetector(story_repository=repository, query_bus=query_bus)

        list(detector.detect())

        assert len([query for query in query_bus.asked if isinstance(query, StoryPullRequestNumbersQuery)]) == 1

    def test_does_not_emit_when_a_slice_verification_has_not_concluded(self) -> None:
        repository = FakeStoryRepository()
        repository.save(StoryMother.create(story_id="7", status=StoryStatus.SLICED))
        detector = StoryCompletedDetector(
            story_repository=repository,
            query_bus=_query_bus({"7"}, pending_verifications={"7": ["100"]}),
        )

        assert list(detector.detect()) == []

    def test_emits_when_every_slice_verification_has_concluded(self) -> None:
        repository = FakeStoryRepository()
        repository.save(StoryMother.create(story_id="7", status=StoryStatus.SLICED))
        detector = StoryCompletedDetector(
            story_repository=repository,
            query_bus=_query_bus({"7"}, pending_verifications={"7": []}),
        )

        assert {event.story_id.value for event in detector.detect()} == {"7"}
