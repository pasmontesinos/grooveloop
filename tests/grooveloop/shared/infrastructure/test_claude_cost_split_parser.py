from __future__ import annotations

import pytest

from grooveloop.shared.domain.cost_basis import CostBasis
from grooveloop.shared.domain.model_usage import ModelUsage
from grooveloop.shared.domain.token_class import TokenClass
from grooveloop.shared.infrastructure.claude_cost_split_parser import parse_cost_split

_OPUS = ModelUsage(
    model="claude-opus-4",
    input_tokens=78,
    output_tokens=24_743,
    cache_read_tokens=3_946_729,
    cache_creation_tokens=116_343,
    cost_usd=3.7557595,
)


class TestParseCostSplit:
    def test_should_derive_the_split_across_every_model(self) -> None:
        split = parse_cost_split(3.7557595, [_OPUS])

        assert split.basis == CostBasis.DERIVED
        by_class = {share.token_class: share for share in split.shares}
        assert by_class[TokenClass.CACHE_READ].tokens == 3_946_729
        assert sum(share.cost_usd for share in split.shares if share.cost_usd is not None) == pytest.approx(
            3.7557595, abs=1e-6
        )

    def test_should_be_unavailable_when_there_is_no_total_cost(self) -> None:
        split = parse_cost_split(None, [_OPUS])

        assert split.basis == CostBasis.UNAVAILABLE
        assert all(share.cost_usd is None for share in split.shares)

    def test_should_be_unavailable_when_there_are_no_models(self) -> None:
        split = parse_cost_split(0.5, [])

        assert split.basis == CostBasis.UNAVAILABLE
