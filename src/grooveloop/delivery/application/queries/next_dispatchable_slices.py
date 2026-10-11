from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.shared.application.queries.query import Query
from grooveloop.shared.application.queries.query_handler import QueryHandler
from grooveloop.shared.application.queries.query_result import QueryResult

if TYPE_CHECKING:
    from grooveloop.delivery.domain.slice import Slice
    from grooveloop.delivery.domain.slice_repository import SliceRepository


@dataclass(frozen=True)
class DispatchableSliceDTO:
    id: str

    @classmethod
    def from_domain(cls, a_slice: Slice) -> Self:
        return cls(id=a_slice.id.value)


@dataclass(frozen=True)
class NextDispatchableSlicesQueryResult(QueryResult):
    slices: list[DispatchableSliceDTO]


@dataclass(frozen=True)
class NextDispatchableSlicesQuery(Query[NextDispatchableSlicesQueryResult]):
    story_id: str


class NextDispatchableSlicesQueryHandler(QueryHandler[NextDispatchableSlicesQuery, NextDispatchableSlicesQueryResult]):
    def __init__(self, slice_repository: SliceRepository) -> None:
        self._slice_repository = slice_repository

    def __call__(self, query: NextDispatchableSlicesQuery) -> NextDispatchableSlicesQueryResult:
        slices = self._slice_repository.search(story_id=StoryId(query.story_id))
        dispatchable = [a_slice for a_slice in slices if a_slice.is_dispatchable(slices)]

        return NextDispatchableSlicesQueryResult(
            slices=[DispatchableSliceDTO.from_domain(a_slice) for a_slice in dispatchable]
        )
