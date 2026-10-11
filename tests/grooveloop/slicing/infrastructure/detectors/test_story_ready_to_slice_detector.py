from __future__ import annotations

from grooveloop.slicing.domain.slice_spec_item import SliceSpecItem
from grooveloop.slicing.domain.spec import Spec
from grooveloop.slicing.domain.story import Story
from grooveloop.slicing.domain.story_id import StoryId
from grooveloop.slicing.domain.story_status import StoryStatus
from grooveloop.slicing.infrastructure.detectors.story_ready_to_slice_detector import StoryReadyToSliceDetector
from tests.playground.shared.infrastructure.fake_story_repository import FakeStoryRepository


def _story(number: str, status: StoryStatus, item_count: int = 1) -> Story:
    items = [SliceSpecItem(title=f"Slice {index}", order=index) for index in range(1, item_count + 1)]

    return Story(id=StoryId(number), spec=Spec(items=items), status=status, slices=[])


class TestStoryReadyToSliceDetector:
    def test_emits_one_event_per_ready_story_with_a_spec(self) -> None:
        repository = FakeStoryRepository()
        repository.save(_story("7", StoryStatus.READY_FOR_IMPLEMENTATION))
        repository.save(_story("9", StoryStatus.READY_FOR_IMPLEMENTATION))
        detector = StoryReadyToSliceDetector(story_repository=repository)

        assert {event.story_id.value for event in detector.detect()} == {"7", "9"}

    def test_does_not_emit_for_already_sliced_stories(self) -> None:
        repository = FakeStoryRepository()
        repository.save(_story("7", StoryStatus.SLICED))
        detector = StoryReadyToSliceDetector(story_repository=repository)

        assert list(detector.detect()) == []

    def test_does_not_emit_for_draft_stories(self) -> None:
        repository = FakeStoryRepository()
        repository.save(_story("7", StoryStatus.DRAFT))
        detector = StoryReadyToSliceDetector(story_repository=repository)

        assert list(detector.detect()) == []

    def test_does_not_emit_for_ready_issues_without_a_spec(self) -> None:
        repository = FakeStoryRepository()
        repository.save(_story("7", StoryStatus.READY_FOR_IMPLEMENTATION, item_count=0))
        detector = StoryReadyToSliceDetector(story_repository=repository)

        assert list(detector.detect()) == []
