from __future__ import annotations

from typing import TYPE_CHECKING, Any

from grooveloop.shared.application.events.event_dispatcher import EventDispatcher
from grooveloop.shared.infrastructure.injector_lookup import resolve

if TYPE_CHECKING:
    from injector import Binder

    from grooveloop.shared.application.events.event_handler import EventHandler
    from grooveloop.shared.domain.event import Event


def bind_event_handlers(binder: Binder, handlers: dict[type[Event], type[EventHandler[Any]]]) -> None:
    dispatcher = resolve(binder.injector, EventDispatcher)

    for event_type, handler_type in handlers.items():
        dispatcher.register(event_type, handler_type)
        binder.bind(handler_type, to=handler_type)
