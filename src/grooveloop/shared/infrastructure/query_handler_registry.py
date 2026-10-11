from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from grooveloop.shared.application.queries.query import Query
    from grooveloop.shared.application.queries.query_handler import QueryHandler


class QueryHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[type[Query[Any]], type[QueryHandler[Any, Any]]] = {}

    def register(self, query_type: type[Query[Any]], handler_type: type[QueryHandler[Any, Any]]) -> None:
        self._handlers[query_type] = handler_type

    def handler_for(self, query_type: type[Query[Any]]) -> type[QueryHandler[Any, Any]] | None:
        return self._handlers.get(query_type)
