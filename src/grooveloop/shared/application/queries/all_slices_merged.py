from __future__ import annotations

from dataclasses import dataclass

from grooveloop.shared.application.queries.query import Query
from grooveloop.shared.application.queries.query_result import QueryResult


@dataclass(frozen=True)
class AllSlicesMergedQueryResult(QueryResult):
    all_merged: bool


@dataclass(frozen=True)
class AllSlicesMergedQuery(Query[AllSlicesMergedQueryResult]):
    story_id: str
