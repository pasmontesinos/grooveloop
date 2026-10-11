from __future__ import annotations

from typing import TYPE_CHECKING, Any

from grooveloop.shared.application.queries.query_bus import QueryBus

if TYPE_CHECKING:
    from injector import Injector

    from grooveloop.shared.application.queries.query import Query
    from grooveloop.shared.application.queries.query_handler import QueryHandler
    from grooveloop.shared.infrastructure.query_handler_registry import QueryHandlerRegistry


class InjectorQueryBus(QueryBus):
    def __init__(self, injector: Injector, registry: QueryHandlerRegistry) -> None:
        self._injector = injector
        self._registry = registry

    def register(self, query_type: type[Query[Any]], handler_type: type[QueryHandler[Any, Any]]) -> None:
        self._registry.register(query_type, handler_type)

    def ask[R](self, query: Query[R]) -> R:
        handler_type = self._registry.handler_for(type(query))
        if handler_type is None:
            raise KeyError(f"No handler registered for query type {type(query)!r}")

        result: R = self._injector.get(handler_type)(query)

        return result
