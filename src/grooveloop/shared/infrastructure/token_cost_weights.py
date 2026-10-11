from __future__ import annotations

from grooveloop.shared.domain.cost_share import CostShare
from grooveloop.shared.domain.token_class import TokenClass

_WEIGHTS: dict[TokenClass, float] = {
    TokenClass.INPUT: 1.0,
    TokenClass.CACHE_READ: 0.1,
    TokenClass.CACHE_WRITE: 2.0,
    TokenClass.OUTPUT: 5.0,
}


def weighted_shares(tokens_by_class: dict[TokenClass, int], total_cost_usd: float | None) -> list[CostShare]:
    weighted = {token_class: tokens_by_class.get(token_class, 0) * weight for token_class, weight in _WEIGHTS.items()}
    total_weighted = sum(weighted.values())

    if total_cost_usd is None or total_weighted <= 0:
        return [CostShare(token_class, tokens_by_class.get(token_class, 0), None) for token_class in TokenClass]

    unit_price = total_cost_usd / total_weighted

    return [
        CostShare(token_class, tokens_by_class.get(token_class, 0), weighted[token_class] * unit_price)
        for token_class in TokenClass
    ]
