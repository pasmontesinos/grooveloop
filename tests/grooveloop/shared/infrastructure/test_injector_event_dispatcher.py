from __future__ import annotations

from dataclasses import dataclass

from injector import Injector, Module, provider, singleton

from grooveloop.shared.application.events.event_handler import EventHandler
from grooveloop.shared.domain.event import Event
from grooveloop.shared.infrastructure.event_handler_registry import EventHandlerRegistry
from grooveloop.shared.infrastructure.injector_event_dispatcher import InjectorEventDispatcher


@dataclass(frozen=True)
class SomethingHappened(Event):
    subject: str


class RecordingHandler(EventHandler[SomethingHappened]):
    event_class = SomethingHappened

    def __init__(self) -> None:
        self.handled: list[SomethingHappened] = []

    def handle(self, event: SomethingHappened) -> None:
        self.handled.append(event)


class RecordingHandlerModule(Module):
    @singleton
    @provider
    def recording_handler(self) -> RecordingHandler:
        return RecordingHandler()


class TestInjectorEventDispatcher:
    def test_should_invoke_registered_handler_with_the_event(self) -> None:
        injector = Injector([RecordingHandlerModule()])
        dispatcher = InjectorEventDispatcher(injector, EventHandlerRegistry())
        dispatcher.register(SomethingHappened, RecordingHandler)
        event = SomethingHappened(subject="slice-1")

        dispatcher.dispatch(event)

        assert injector.get(RecordingHandler).handled == [event]

    def test_should_do_nothing_when_no_handler_registered(self) -> None:
        dispatcher = InjectorEventDispatcher(Injector(), EventHandlerRegistry())

        dispatcher.dispatch(SomethingHappened(subject="slice-1"))
