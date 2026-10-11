from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.domain.cost_basis import CostBasis
from grooveloop.shared.domain.cost_split import CostSplit
from grooveloop.shared.domain.token_class import TokenClass
from grooveloop.shared.infrastructure.token_cost_weights import weighted_shares

if TYPE_CHECKING:
    from grooveloop.shared.domain.model_usage import ModelUsage


def parse_cost_split(total_cost_usd: float | None, models: list[ModelUsage]) -> CostSplit:
    tokens_by_class = {
        TokenClass.INPUT: sum(model.input_tokens for model in models),
        TokenClass.CACHE_READ: sum(model.cache_read_tokens for model in models),
        TokenClass.CACHE_WRITE: sum(model.cache_creation_tokens for model in models),
        TokenClass.OUTPUT: sum(model.output_tokens for model in models),
    }
    shares = weighted_shares(tokens_by_class, total_cost_usd)
    basis = CostBasis.DERIVED if all(share.cost_usd is not None for share in shares) else CostBasis.UNAVAILABLE

    return CostSplit(basis=basis, shares=shares)
