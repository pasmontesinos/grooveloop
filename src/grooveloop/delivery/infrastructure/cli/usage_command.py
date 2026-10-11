from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from grooveloop.bootstrap import container
from grooveloop.delivery.application.queries.list_slice_sessions import (
    ListSliceSessionsQuery,
    ListSliceSessionsQueryHandler,
)
from grooveloop.shared.domain.token_class import TokenClass
from grooveloop.shared.infrastructure.cli.exit_code import ExitCode

if TYPE_CHECKING:
    from grooveloop.shared.application.queries.list_repo_sessions import (
        AgentSessionDTO,
        ModelUsageDTO,
        TurnGrowthDTO,
    )

_TOKEN_CLASS_LABELS = {
    TokenClass.INPUT.value: "input",
    TokenClass.CACHE_READ.value: "cache read",
    TokenClass.CACHE_WRITE.value: "cache write",
    TokenClass.OUTPUT.value: "output",
}


def run(repo: str, slice_number: int) -> int:
    handler = container.get(ListSliceSessionsQueryHandler)
    result = handler(ListSliceSessionsQuery(repo=repo, slice_id=str(slice_number)))

    if len(result.sessions) == 0:
        print(f"no sessions for the sub-issue {slice_number} in {repo}", file=sys.stderr)

        return ExitCode.FAILURE

    for session in result.sessions:
        _print_session(session)

    return ExitCode.OK


def _print_session(session: AgentSessionDTO) -> None:
    cost = f"${session.total_cost_usd:.4f}" if session.total_cost_usd is not None else "no cost"
    print(f"[{session.task_type}] {session.engine} — {cost}")

    cost_split = session.cost_split
    if cost_split is None:
        print("split: unavailable")
    else:
        print("split:")
        total_tokens = sum(share.tokens for share in cost_split.shares)
        for share in cost_split.shares:
            label = _TOKEN_CLASS_LABELS[share.token_class]
            if share.cost_usd is not None and session.total_cost_usd:
                percentage = share.cost_usd / session.total_cost_usd * 100
                print(f"  {label} {share.tokens} tokens ${share.cost_usd:.4f} {percentage:.1f}%")
            else:
                percentage = share.tokens / total_tokens * 100 if total_tokens > 0 else 0.0
                print(f"  {label} {share.tokens} tokens {percentage:.1f}%")

        print(f"basis: {cost_split.basis}")

    _print_models(list(session.models))
    _print_turn_growth(session.turn_growth)


def _print_models(models: list[ModelUsageDTO]) -> None:
    if len(models) == 0:
        return

    print("models:")
    for model in models:
        input_tokens = model.input_tokens + model.cache_read_tokens + model.cache_creation_tokens
        cache_share = model.cache_read_tokens / input_tokens * 100 if input_tokens > 0 else 0.0
        print(
            f"  {model.model} ${model.cost_usd:.4f} input {input_tokens} tokens"
            f" · {cache_share:.1f}% cache · output {model.output_tokens} tokens"
        )


def _print_turn_growth(turns: list[TurnGrowthDTO]) -> None:
    if len(turns) == 0:
        return

    print("turns that added the most context:")
    for growth in turns:
        print(f"  {_describe_turn(growth)} — {growth.added_tokens} tokens")


def _describe_turn(growth: TurnGrowthDTO) -> str:
    if growth.turn == 1:
        return "#1 startup"

    if growth.after_action is not None:
        return f"#{growth.turn} after {growth.after_action}"

    return f"#{growth.turn}"
