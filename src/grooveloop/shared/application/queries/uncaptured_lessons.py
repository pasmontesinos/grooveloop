from __future__ import annotations

from dataclasses import dataclass

from grooveloop.shared.application.queries.query import Query
from grooveloop.shared.application.queries.query_result import QueryResult


@dataclass(frozen=True)
class UncapturedLessonsQueryResult(QueryResult):
    pull_request_numbers: list[int]


@dataclass(frozen=True)
class UncapturedLessonsQuery(Query[UncapturedLessonsQueryResult]):
    pull_request_numbers: list[int]
