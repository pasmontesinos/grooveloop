from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from grooveloop.shared.application.events.event_handler import EventHandler
    from grooveloop.shared.domain.event import Event


class EventHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[type[EventHandler[Any]]]] = {}

    def register(self, event_type: type[Event], handler_type: type[EventHandler[Any]]) -> None:
        self._handlers.setdefault(event_type, []).append(handler_type)

    def registered_handlers(self) -> list[type[EventHandler[Any]]]:
        return [handler for handlers in self._handlers.values() for handler in handlers]

    def handlers_for(self, event_type: type[Event]) -> list[type[EventHandler[Any]]]:
        return self._handlers.get(event_type, [])
