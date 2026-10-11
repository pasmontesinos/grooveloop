from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True)
class Identifier:
    value: str

    @classmethod
    def generate(cls) -> Self:
        return cls(value=str(uuid.uuid4()))

    def __str__(self) -> str:
        return self.value
