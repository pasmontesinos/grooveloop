from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grooveloop.slicing.application.commands.create_slices_from_spec import (
    CreateSlicesFromSpecCommand,
    CreateSlicesFromSpecCommandHandler,
)
from grooveloop.slicing.domain.exceptions import StoryNotFoundError
from grooveloop.slicing.domain.slice_spec_item import SliceSpecItem
from grooveloop.slicing.domain.spec import Spec
from grooveloop.slicing.domain.story import Story
from grooveloop.slicing.domain.story_id import StoryId
from grooveloop.slicing.domain.story_status import StoryStatus
from tests.grooveloop.slicing.mothers.story_mother import StoryMother
from tests.playground.shared.infrastructure.fake_story_repository import FakeStoryRepository

if TYPE_CHECKING:
    from grooveloop.slicing.domain.slice_order import SliceOrder


def _positions(depends_on: list[SliceOrder] | None) -> list[int] | None:
    if depends_on is None:
        return None

    return [position.value for position in depends_on]


class TestCreateSlicesFromSpecCommandHandler:
    def test_should_materialize_one_slice_per_spec_item(self) -> None:
        repository = FakeStoryRepository()
        repository.save(StoryMother.create(story_id="story-1", slice_count=3))
        handler = CreateSlicesFromSpecCommandHandler(story_repository=repository)

        handler(CreateSlicesFromSpecCommand(story_id="story-1"))

        stored = repository.find(StoryId("story-1"))
        assert stored is not None
        assert len(stored.slices) == 3

    def test_should_leave_the_story_sliced(self) -> None:
        repository = FakeStoryRepository()
        repository.save(StoryMother.create(story_id="story-1", slice_count=2))
        handler = CreateSlicesFromSpecCommandHandler(story_repository=repository)

        handler(CreateSlicesFromSpecCommand(story_id="story-1"))

        stored = repository.find(StoryId("story-1"))
        assert stored is not None
        assert stored.status == StoryStatus.SLICED

    def test_should_raise_when_story_not_found(self) -> None:
        handler = CreateSlicesFromSpecCommandHandler(story_repository=FakeStoryRepository())

        with pytest.raises(StoryNotFoundError):
            handler(CreateSlicesFromSpecCommand(story_id="missing"))

    def test_should_mark_every_slice_for_deploy_verification_when_requested(self) -> None:
        repository = FakeStoryRepository()
        repository.save(StoryMother.create(story_id="story-1", slice_count=2))
        handler = CreateSlicesFromSpecCommandHandler(story_repository=repository)

        handler(CreateSlicesFromSpecCommand(story_id="story-1", verify_deploy=True))

        stored = repository.find(StoryId("story-1"))
        assert stored is not None
        assert [a_slice.verify_deploy for a_slice in stored.slices] == [True, True]

    def test_should_leave_slices_unmarked_by_default(self) -> None:
        repository = FakeStoryRepository()
        repository.save(StoryMother.create(story_id="story-1", slice_count=2))
        handler = CreateSlicesFromSpecCommandHandler(story_repository=repository)

        handler(CreateSlicesFromSpecCommand(story_id="story-1"))

        stored = repository.find(StoryId("story-1"))
        assert stored is not None
        assert [a_slice.verify_deploy for a_slice in stored.slices] == [False, False]

    def test_should_propagate_declared_dependencies_to_each_slice(self) -> None:
        repository = FakeStoryRepository()
        story = Story(
            id=StoryId("story-1"),
            spec=Spec(
                items=[
                    SliceSpecItem(title="slice 1", order=1),
                    SliceSpecItem(title="slice 2", order=2, depends_on=[]),
                    SliceSpecItem(title="slice 3", order=3, depends_on=[1]),
                ]
            ),
            status=StoryStatus.READY_FOR_IMPLEMENTATION,
            slices=[],
        )
        repository.save(story)
        handler = CreateSlicesFromSpecCommandHandler(story_repository=repository)

        handler(CreateSlicesFromSpecCommand(story_id="story-1"))

        stored = repository.find(StoryId("story-1"))
        assert stored is not None
        assert [_positions(a_slice.depends_on) for a_slice in stored.slices] == [None, [], [1]]
