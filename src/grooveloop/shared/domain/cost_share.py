from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.shared.domain.token_class import TokenClass


@dataclass(frozen=True)
class CostShare:
    token_class: TokenClass
    tokens: int
    cost_usd: float | None
