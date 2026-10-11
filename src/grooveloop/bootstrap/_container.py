from __future__ import annotations

import contextlib
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, TypeVar, overload

from injector import Injector, Module

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    from injector import Binder

T = TypeVar("T")

_NOT_INITIALIZED = "Container is not initialized. Call 'initialize' first."


class OverrideModule(Module):
    def __init__(self, interface: Any, implementation: Any) -> None:
        super().__init__()
        self._interface = interface
        self._implementation = implementation

    def configure(self, binder: Binder) -> None:
        binder.bind(self._interface, to=self._implementation)


class Container:
    _root_injector: Injector | None = None
    _injector_ctx: ContextVar[Injector] = ContextVar("_injector_ctx")

    def initialize(self, modules: Sequence[Module]) -> None:
        if self._root_injector is not None:
            raise RuntimeError("Container is already initialized.")

        self._root_injector = Injector(modules, auto_bind=False)

    def bind(self, interface: type[T] | Any, implementation: T | Any) -> None:
        if self._root_injector is None:
            raise RuntimeError(_NOT_INITIALIZED)

        self._root_injector.binder.bind(interface, to=implementation)

    @overload
    def get(self, interface: type[T]) -> T: ...

    @overload
    def get(self, interface: Any) -> Any: ...

    def get(self, interface: type[T] | Any) -> T | Any:
        return self._injector.get(interface)

    @contextlib.contextmanager
    def override(self, interface: type[T] | Any, implementation: T | Any) -> Generator[None]:
        override_module = OverrideModule(interface, implementation)
        child_injector = self._injector.create_child_injector([override_module])

        token = self._injector_ctx.set(child_injector)
        try:
            yield
        finally:
            self._injector_ctx.reset(token)

    @contextlib.contextmanager
    def restoring_bindings(self) -> Generator[None]:
        if self._root_injector is None:
            raise RuntimeError(_NOT_INITIALIZED)

        bindings = self._root_injector.binder._bindings
        snapshot = dict(bindings)
        try:
            yield
        finally:
            bindings.clear()
            bindings.update(snapshot)

    @property
    def _injector(self) -> Injector:
        if self._root_injector is None:
            raise RuntimeError(_NOT_INITIALIZED)

        try:
            return self._injector_ctx.get()
        except LookupError:
            self._injector_ctx.set(self._root_injector)

            return self._root_injector


container = Container()
