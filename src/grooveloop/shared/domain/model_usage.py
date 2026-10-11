from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelUsage:
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    cost_usd: float
