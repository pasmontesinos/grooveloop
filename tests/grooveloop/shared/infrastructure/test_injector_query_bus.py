from __future__ import annotations

from dataclasses import dataclass
from typing import assert_type

import pytest
from injector import Injector

from grooveloop.shared.application.queries.query import Query
from grooveloop.shared.application.queries.query_handler import QueryHandler
from grooveloop.shared.application.queries.query_result import QueryResult
from grooveloop.shared.infrastructure.injector_query_bus import InjectorQueryBus
from grooveloop.shared.infrastructure.query_handler_registry import QueryHandlerRegistry


@dataclass(frozen=True)
class GreetQueryResult(QueryResult):
    greeting: str


@dataclass(frozen=True)
class GreetQuery(Query[GreetQueryResult]):
    name: str


class GreetQueryHandler(QueryHandler[GreetQuery, GreetQueryResult]):
    def __call__(self, query: GreetQuery) -> GreetQueryResult:
        return GreetQueryResult(greeting=f"hello {query.name}")


class TestInjectorQueryBus:
    def test_should_resolve_handler_and_return_its_result(self) -> None:
        bus = InjectorQueryBus(Injector(), QueryHandlerRegistry())
        bus.register(GreetQuery, GreetQueryHandler)

        result = bus.ask(GreetQuery(name="ada"))

        assert_type(result, GreetQueryResult)
        assert result == GreetQueryResult(greeting="hello ada")

    def test_should_raise_when_no_handler_registered(self) -> None:
        bus = InjectorQueryBus(Injector(), QueryHandlerRegistry())

        with pytest.raises(KeyError):
            bus.ask(GreetQuery(name="ada"))
