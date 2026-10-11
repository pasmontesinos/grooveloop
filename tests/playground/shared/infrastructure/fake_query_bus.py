from __future__ import annotations

from typing import TYPE_CHECKING, Any

from grooveloop.shared.application.queries.query_bus import QueryBus

if TYPE_CHECKING:
    from collections.abc import Callable

    from grooveloop.shared.application.queries.query import Query
    from grooveloop.shared.application.queries.query_handler import QueryHandler


class FakeQueryBus(QueryBus):
    def __init__(self, answers: dict[type[Query[Any]], Callable[[Any], Any]] | None = None) -> None:
        self._answers = answers or {}
        self.asked: list[Query[Any]] = []

    def register(self, query_type: type[Query[Any]], handler_type: type[QueryHandler[Any, Any]]) -> None:
        return None

    def ask[R](self, query: Query[R]) -> R:
        self.asked.append(query)
        answer = self._answers.get(type(query))
        if answer is None:
            raise AssertionError(f"Unexpected query {query!r}")

        result: R = answer(query)

        return result
