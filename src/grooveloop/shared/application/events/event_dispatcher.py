from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from grooveloop.shared.application.events.event_handler import EventHandler
    from grooveloop.shared.domain.event import Event


class EventDispatcher(ABC):
    @abstractmethod
    def register(self, event_type: type[Event], handler_type: type[EventHandler[Any]]) -> None: ...

    @abstractmethod
    def dispatch(self, event: Event) -> None: ...
