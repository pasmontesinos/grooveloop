from __future__ import annotations

import pytest

from grooveloop.shared.domain.cost_basis import CostBasis
from grooveloop.shared.domain.token_class import TokenClass
from grooveloop.shared.infrastructure.opencode_cost_split_parser import parse_cost_split

_ENTRY = {
    "providerID": "anthropic",
    "modelID": "claude-opus-4",
    "tokens": {"input": 10, "output": 20, "cache": {"read": 100, "write": 5}},
    "cost": 0.5,
}


class TestParseCostSplit:
    def test_should_sum_the_derived_cost_of_every_entry(self) -> None:
        split = parse_cost_split([_ENTRY, _ENTRY])

        assert split.basis == CostBasis.DERIVED
        by_class = {share.token_class: share for share in split.shares}
        assert by_class[TokenClass.CACHE_READ].tokens == 200
        assert sum(share.cost_usd for share in split.shares if share.cost_usd is not None) == pytest.approx(
            1.0, abs=1e-6
        )

    def test_should_be_unavailable_when_there_are_no_entries(self) -> None:
        split = parse_cost_split([])

        assert split.basis == CostBasis.UNAVAILABLE

    def test_should_be_unavailable_when_every_entry_has_zero_cost(self) -> None:
        free_entry = {**_ENTRY, "cost": 0}

        split = parse_cost_split([free_entry])

        assert split.basis == CostBasis.UNAVAILABLE
        by_class = {share.token_class: share for share in split.shares}
        assert by_class[TokenClass.CACHE_READ].tokens == 100
