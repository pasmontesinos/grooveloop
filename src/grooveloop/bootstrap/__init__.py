from __future__ import annotations

from grooveloop.bootstrap._container import container
from grooveloop.bootstrap.di import modules

container.initialize(modules)

__all__ = ["container"]
