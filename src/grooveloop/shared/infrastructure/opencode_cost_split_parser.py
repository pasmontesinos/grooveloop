from __future__ import annotations

from typing import Any

from grooveloop.shared.domain.cost_basis import CostBasis
from grooveloop.shared.domain.cost_share import CostShare
from grooveloop.shared.domain.cost_split import CostSplit
from grooveloop.shared.domain.token_class import TokenClass
from grooveloop.shared.infrastructure.opencode_json_numbers import parse_float, parse_int
from grooveloop.shared.infrastructure.token_cost_weights import weighted_shares


def parse_cost_split(entries: list[dict[str, Any]]) -> CostSplit:
    totals = dict.fromkeys(TokenClass, 0)
    dollars = dict.fromkeys(TokenClass, 0.0)
    has_cost = False

    for entry in entries:
        entry_cost = parse_float(entry.get("cost"))
        entry_shares = weighted_shares(_tokens_by_class(entry), entry_cost if entry_cost > 0 else None)
        for share in entry_shares:
            totals[share.token_class] += share.tokens
            if share.cost_usd is not None:
                dollars[share.token_class] += share.cost_usd
                has_cost = True

    if not has_cost:
        return CostSplit(
            basis=CostBasis.UNAVAILABLE,
            shares=[CostShare(token_class, totals[token_class], None) for token_class in TokenClass],
        )

    return CostSplit(
        basis=CostBasis.DERIVED,
        shares=[CostShare(token_class, totals[token_class], dollars[token_class]) for token_class in TokenClass],
    )


def _tokens_by_class(entry: dict[str, Any]) -> dict[TokenClass, int]:
    tokens = entry.get("tokens")
    tokens = tokens if isinstance(tokens, dict) else {}
    cache = tokens.get("cache")
    cache = cache if isinstance(cache, dict) else {}

    return {
        TokenClass.INPUT: parse_int(tokens.get("input")),
        TokenClass.CACHE_READ: parse_int(cache.get("read")),
        TokenClass.CACHE_WRITE: parse_int(cache.get("write")),
        TokenClass.OUTPUT: parse_int(tokens.get("output")),
    }
