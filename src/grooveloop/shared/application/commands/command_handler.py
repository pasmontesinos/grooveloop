from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class CommandHandler[C, CR](ABC):
    @abstractmethod
    def __call__(self, command: C) -> CR: ...

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)

        if "__call__" not in vars(cls):
            return

        original = cls.__call__

        def logged_call(self: CommandHandler[C, CR], command: C) -> CR:
            command_name = type(command).__name__
            logger.info("Executing %s with %s", command_name, vars(command))
            start = time.monotonic()
            result = original(self, command)
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.info("Executed %s in %.1fms", command_name, elapsed_ms)

            return result

        cls.__call__ = logged_call  # type: ignore[method-assign]
