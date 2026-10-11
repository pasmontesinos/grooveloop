from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable

    from injector import Injector


def resolve[T](injector: Injector, interface: Callable[..., T]) -> T:
    return injector.get(cast("type[T]", interface))
