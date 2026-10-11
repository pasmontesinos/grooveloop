from __future__ import annotations

from dataclasses import dataclass

from grooveloop.shared.application.queries.query import Query
from grooveloop.shared.application.queries.query_result import QueryResult


@dataclass(frozen=True)
class PendingVerificationsQueryResult(QueryResult):
    slice_ids: list[str]


@dataclass(frozen=True)
class PendingVerificationsQuery(Query[PendingVerificationsQueryResult]):
    story_id: str
