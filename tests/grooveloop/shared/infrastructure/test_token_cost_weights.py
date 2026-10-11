from __future__ import annotations

import pytest

from grooveloop.shared.domain.token_class import TokenClass
from grooveloop.shared.infrastructure.token_cost_weights import weighted_shares


class TestWeightedShares:
    def test_should_split_the_total_cost_proportionally_to_the_weighted_tokens(self) -> None:
        tokens_by_class = {
            TokenClass.CACHE_READ: 3_946_729,
            TokenClass.CACHE_WRITE: 116_343,
            TokenClass.OUTPUT: 24_743,
            TokenClass.INPUT: 78,
        }

        shares = weighted_shares(tokens_by_class, 3.7557595)

        by_class = {share.token_class: share for share in shares}
        assert by_class[TokenClass.CACHE_READ].cost_usd == pytest.approx(1.9734, abs=1e-3)
        assert by_class[TokenClass.CACHE_WRITE].cost_usd == pytest.approx(1.1634, abs=1e-3)
        assert by_class[TokenClass.OUTPUT].cost_usd == pytest.approx(0.6186, abs=1e-3)
        assert by_class[TokenClass.INPUT].cost_usd == pytest.approx(0.0004, abs=1e-3)
        assert sum(share.cost_usd for share in shares if share.cost_usd is not None) == pytest.approx(
            3.7557595, abs=1e-6
        )

    def test_should_return_every_token_class_in_enum_order(self) -> None:
        shares = weighted_shares({}, 1.0)

        assert [share.token_class for share in shares] == list(TokenClass)

    def test_should_report_tokens_without_cost_when_there_is_no_total_cost(self) -> None:
        shares = weighted_shares({TokenClass.INPUT: 100}, None)

        by_class = {share.token_class: share for share in shares}
        assert by_class[TokenClass.INPUT].tokens == 100
        assert all(share.cost_usd is None for share in shares)

    def test_should_report_tokens_without_cost_when_every_class_has_zero_tokens(self) -> None:
        shares = weighted_shares({TokenClass.INPUT: 0, TokenClass.OUTPUT: 0}, 5.0)

        assert all(share.cost_usd is None for share in shares)
