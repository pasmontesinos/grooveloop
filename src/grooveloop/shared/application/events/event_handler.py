from __future__ import annotations

from abc import ABC, abstractmethod


class EventHandler[E](ABC):
    event_class: type[E]

    @abstractmethod
    def handle(self, event: E) -> None: ...
