from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class QueryHandler[Q, QR](ABC):
    @abstractmethod
    def __call__(self, query: Q) -> QR: ...

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)

        if "__call__" not in vars(cls):
            return

        original = cls.__call__

        def logged_call(self: QueryHandler[Q, QR], query: Q) -> QR:
            query_name = type(query).__name__
            logger.info("Executing %s with %s", query_name, vars(query))
            start = time.monotonic()
            result = original(self, query)
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.info("Executed %s in %.1fms", query_name, elapsed_ms)

            return result

        cls.__call__ = logged_call  # type: ignore[method-assign]
