from __future__ import annotations

from typing import TYPE_CHECKING, Any

from grooveloop.shared.application.events.event_dispatcher import EventDispatcher

if TYPE_CHECKING:
    from injector import Injector

    from grooveloop.shared.application.events.event_handler import EventHandler
    from grooveloop.shared.domain.event import Event
    from grooveloop.shared.infrastructure.event_handler_registry import EventHandlerRegistry


class InjectorEventDispatcher(EventDispatcher):
    def __init__(self, injector: Injector, registry: EventHandlerRegistry) -> None:
        self._injector = injector
        self._registry = registry

    def register(self, event_type: type[Event], handler_type: type[EventHandler[Any]]) -> None:
        self._registry.register(event_type, handler_type)

    def dispatch(self, event: Event) -> None:
        for handler_type in self._registry.handlers_for(type(event)):
            self._injector.get(handler_type).handle(event)
