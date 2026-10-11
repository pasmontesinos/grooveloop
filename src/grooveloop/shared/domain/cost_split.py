from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.shared.domain.cost_basis import CostBasis
    from grooveloop.shared.domain.cost_share import CostShare


@dataclass(frozen=True)
class CostSplit:
    basis: CostBasis
    shares: list[CostShare] = field(default_factory=list)
