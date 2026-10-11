from __future__ import annotations

from dataclasses import dataclass

from grooveloop.shared.application.queries.query import Query
from grooveloop.shared.application.queries.query_result import QueryResult


@dataclass(frozen=True)
class PendingLessonDTO:
    pull_request_number: int
    conventions_pull_request_number: int | None


@dataclass(frozen=True)
class PendingLessonsQueryResult(QueryResult):
    pending_lessons: list[PendingLessonDTO]


@dataclass(frozen=True)
class PendingLessonsQuery(Query[PendingLessonsQueryResult]):
    pull_request_numbers: list[int]
