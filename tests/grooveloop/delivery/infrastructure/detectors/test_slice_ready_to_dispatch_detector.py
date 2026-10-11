from __future__ import annotations

from grooveloop.delivery.application.queries.next_dispatchable_slices import (
    NextDispatchableSlicesQuery,
    NextDispatchableSlicesQueryHandler,
)
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.delivery.infrastructure.detectors.slice_ready_to_dispatch_detector import (
    SliceReadyToDispatchDetector,
)
from grooveloop.shared.application.queries.pending_lessons import (
    PendingLessonDTO,
    PendingLessonsQuery,
    PendingLessonsQueryResult,
)
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_query_bus import FakeQueryBus
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository


def _query_bus(repository: FakeSliceRepository, pending: set[int] | None = None) -> FakeQueryBus:
    pending_numbers = pending or set()

    return FakeQueryBus(
        {
            NextDispatchableSlicesQuery: NextDispatchableSlicesQueryHandler(slice_repository=repository),
            PendingLessonsQuery: lambda query: PendingLessonsQueryResult(
                pending_lessons=[
                    PendingLessonDTO(pull_request_number=number, conventions_pull_request_number=None)
                    for number in query.pull_request_numbers
                    if number in pending_numbers
                ]
            ),
        }
    )


def _detector(repository: FakeSliceRepository, pending: set[int] | None = None) -> SliceReadyToDispatchDetector:
    return SliceReadyToDispatchDetector(
        slice_repository=repository,
        query_bus=_query_bus(repository, pending),
    )


def _slice_ids(detector: SliceReadyToDispatchDetector) -> list[str]:
    return [event.slice_id.value for event in detector.detect()]


class TestSliceReadyToDispatchDetector:
    def test_emits_the_dispatchable_slice_of_a_single_story(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(slice_id="11", status=SliceStatus.MERGED, story_id="10"),
                    SliceMother.create(slice_id="12", status=SliceStatus.DISPATCHED, story_id="10"),
                ],
                StoryId("20"): [
                    SliceMother.create(slice_id="21", status=SliceStatus.MERGED, story_id="20"),
                    SliceMother.create(slice_id="22", status=SliceStatus.PENDING, story_id="20"),
                ],
            }
        )
        detector = _detector(repository)

        assert _slice_ids(detector) == ["22"]

    def test_does_not_emit_when_a_previous_slice_is_not_merged(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(slice_id="11", status=SliceStatus.DISPATCHED, story_id="10"),
                    SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10"),
                ]
            }
        )
        detector = _detector(repository)

        assert list(detector.detect()) == []

    def test_does_not_emit_when_no_story_has_a_pending_slice(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(slice_id="11", status=SliceStatus.MERGED, story_id="10"),
                    SliceMother.create(slice_id="12", status=SliceStatus.DISPATCHED, story_id="10"),
                ]
            }
        )
        detector = _detector(repository)

        assert list(detector.detect()) == []

    def test_emits_one_event_per_dispatchable_slice_across_several_stories(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [SliceMother.create(slice_id="11", status=SliceStatus.PENDING, story_id="10")],
                StoryId("20"): [SliceMother.create(slice_id="21", status=SliceStatus.PENDING, story_id="20")],
            }
        )
        detector = _detector(repository)

        assert sorted(_slice_ids(detector)) == ["11", "21"]

    def test_emits_one_event_per_independent_dispatchable_slice_of_the_same_story(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(slice_id="10", status=SliceStatus.MERGED, story_id="10"),
                    SliceMother.create(
                        slice_id="11", status=SliceStatus.PENDING, story_id="10", depends_on=[SliceId("10")]
                    ),
                    SliceMother.create(
                        slice_id="12", status=SliceStatus.PENDING, story_id="10", depends_on=[SliceId("10")]
                    ),
                ]
            }
        )
        detector = _detector(repository)

        assert sorted(_slice_ids(detector)) == ["11", "12"]

    def test_does_not_emit_when_a_merged_dependency_has_a_pending_lesson(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="11", status=SliceStatus.MERGED, story_id="10", pull_request_number=100
                    ),
                    SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10"),
                ]
            }
        )
        detector = _detector(repository, pending={100})

        assert list(detector.detect()) == []

    def test_emits_when_the_merged_dependency_lesson_is_resolved(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="11", status=SliceStatus.MERGED, story_id="10", pull_request_number=100
                    ),
                    SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10"),
                ]
            }
        )
        detector = _detector(repository)

        assert _slice_ids(detector) == ["12"]

    def test_a_merged_dependency_without_a_pull_request_does_not_block(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(slice_id="11", status=SliceStatus.MERGED, story_id="10"),
                    SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10"),
                ]
            }
        )
        detector = _detector(repository, pending={100})

        assert _slice_ids(detector) == ["12"]

    def test_gated_story_does_not_hide_another_dispatchable_story(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="11", status=SliceStatus.MERGED, story_id="10", pull_request_number=100
                    ),
                    SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10"),
                ],
                StoryId("20"): [SliceMother.create(slice_id="21", status=SliceStatus.PENDING, story_id="20")],
            }
        )
        detector = _detector(repository, pending={100})

        assert _slice_ids(detector) == ["21"]

    def test_emits_a_slice_whose_declared_dependency_is_merged_even_though_a_previous_slice_is_not(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(slice_id="11", status=SliceStatus.MERGED, story_id="10"),
                    SliceMother.create(slice_id="12", status=SliceStatus.PR_OPEN, story_id="10"),
                    SliceMother.create(
                        slice_id="13", status=SliceStatus.PENDING, story_id="10", depends_on=[SliceId("11")]
                    ),
                ]
            }
        )
        detector = _detector(repository)

        assert _slice_ids(detector) == ["13"]

    def test_lesson_gate_follows_declared_dependencies_not_sequential_order(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="11", status=SliceStatus.MERGED, story_id="10", pull_request_number=100
                    ),
                    SliceMother.create(
                        slice_id="12", status=SliceStatus.MERGED, story_id="10", pull_request_number=200
                    ),
                    SliceMother.create(
                        slice_id="13", status=SliceStatus.PENDING, story_id="10", depends_on=[SliceId("11")]
                    ),
                ]
            }
        )
        detector = _detector(repository, pending={200})

        assert _slice_ids(detector) == ["13"]
