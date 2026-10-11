from __future__ import annotations

from dataclasses import dataclass

from grooveloop.shared.application.queries.query import Query
from grooveloop.shared.application.queries.query_result import QueryResult


@dataclass(frozen=True)
class GetStorySpecQueryResult(QueryResult):
    spec_text: str


@dataclass(frozen=True)
class GetStorySpecQuery(Query[GetStorySpecQueryResult | None]):
    story_id: str
