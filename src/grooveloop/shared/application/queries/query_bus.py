from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from grooveloop.shared.application.queries.query import Query
    from grooveloop.shared.application.queries.query_handler import QueryHandler


class QueryBus(ABC):
    @abstractmethod
    def register(self, query_type: type[Query[Any]], handler_type: type[QueryHandler[Any, Any]]) -> None: ...

    @abstractmethod
    def ask[R](self, query: Query[R]) -> R: ...
