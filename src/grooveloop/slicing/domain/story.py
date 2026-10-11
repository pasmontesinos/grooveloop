from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.slicing.domain.exceptions import StoryNotReadyError, StoryNotSlicedError
from grooveloop.slicing.domain.slice import Slice
from grooveloop.slicing.domain.slice_order import SliceOrder
from grooveloop.slicing.domain.story_status import StoryStatus

if TYPE_CHECKING:
    from grooveloop.slicing.domain.spec import Spec
    from grooveloop.slicing.domain.story_id import StoryId


class Story:
    def __init__(self, id: StoryId, spec: Spec, status: StoryStatus, slices: list[Slice], title: str = "") -> None:
        self._id = id
        self._spec = spec
        self._status = status
        self._slices = slices
        self._title = title

    @property
    def id(self) -> StoryId:
        return self._id

    @property
    def title(self) -> str:
        return self._title

    @property
    def status(self) -> StoryStatus:
        return self._status

    @property
    def spec(self) -> Spec:
        return self._spec

    @property
    def slices(self) -> list[Slice]:
        return list(self._slices)

    def materialize_slices(self, verify_deploy: bool) -> None:
        if self._status != StoryStatus.READY_FOR_IMPLEMENTATION:
            raise StoryNotReadyError(f"Story {self._id} is not ready for implementation")

        self._slices = [
            Slice.create(
                title=item.title,
                order=SliceOrder(item.order),
                description=item.body,
                verify_deploy=verify_deploy,
                depends_on=(
                    [SliceOrder(position) for position in item.depends_on] if item.depends_on is not None else None
                ),
            )
            for item in self._spec.items
        ]
        self._status = StoryStatus.SLICED

    def complete(self) -> None:
        if self._status != StoryStatus.SLICED:
            raise StoryNotSlicedError(f"Story {self._id} is not sliced")

        self._status = StoryStatus.DONE
