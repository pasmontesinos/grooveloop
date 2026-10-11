from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock, create_autospec

import pytest

from grooveloop.bootstrap import container
from grooveloop.delivery.application.queries.list_slice_sessions import (
    ListSliceSessionsQueryHandler,
    ListSliceSessionsQueryResult,
)
from grooveloop.delivery.infrastructure.cli import usage_command
from grooveloop.shared.application.queries.list_repo_sessions import (
    AgentSessionDTO,
    CostShareDTO,
    CostSplitDTO,
    ModelUsageDTO,
    TurnGrowthDTO,
)
from grooveloop.shared.infrastructure.cli.exit_code import ExitCode

_STARTED_AT = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def list_slice_sessions_handler() -> Any:
    mock = create_autospec(ListSliceSessionsQueryHandler, spec_set=True, instance=True)
    with container.override(ListSliceSessionsQueryHandler, mock):
        yield mock


@pytest.mark.entrypoint
class TestUsageCommand:
    def test_should_print_the_derived_cost_split_and_exit_zero(
        self, list_slice_sessions_handler: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        session = AgentSessionDTO(
            slice_number="363",
            outcome="succeeded",
            task_type="implement_slice",
            engine="claude",
            run_id="run-1",
            started_at=_STARTED_AT,
            has_log=True,
            elapsed_seconds=12.0,
            total_cost_usd=3.7558,
            models=[],
            cost_split=CostSplitDTO(
                basis="derived",
                shares=[
                    CostShareDTO("input", 78, 0.0004),
                    CostShareDTO("cache_read", 3_946_729, 1.9734),
                    CostShareDTO("cache_write", 116_343, 1.1634),
                    CostShareDTO("output", 24_743, 0.6186),
                ],
            ),
        )
        list_slice_sessions_handler.return_value = ListSliceSessionsQueryResult(sessions=[session])

        exit_code = usage_command.run(repo="owner/repo", slice_number=363)

        out = capsys.readouterr().out
        assert exit_code == 0
        assert "split:" in out
        assert "basis: derived" in out
        query = list_slice_sessions_handler.call_args.args[0]
        assert query.repo == "owner/repo"
        assert query.slice_id == "363"

    def test_should_print_tokens_without_dollars_when_the_split_is_unavailable(
        self, list_slice_sessions_handler: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        session = AgentSessionDTO(
            slice_number="363",
            outcome="succeeded",
            task_type="implement_slice",
            engine="opencode",
            run_id="run-1",
            started_at=_STARTED_AT,
            has_log=True,
            elapsed_seconds=12.0,
            total_cost_usd=None,
            models=[],
            cost_split=CostSplitDTO(
                basis="unavailable",
                shares=[CostShareDTO("input", 78, None)],
            ),
        )
        list_slice_sessions_handler.return_value = ListSliceSessionsQueryResult(sessions=[session])

        exit_code = usage_command.run(repo="owner/repo", slice_number=363)

        out = capsys.readouterr().out
        assert exit_code == 0
        assert "basis: unavailable" in out
        assert "$" not in out.split("basis:")[0].split("split:")[1]

    def test_should_exit_with_failure_on_stderr_when_the_slice_has_no_sessions(
        self, list_slice_sessions_handler: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        list_slice_sessions_handler.return_value = ListSliceSessionsQueryResult(sessions=[])

        exit_code = usage_command.run(repo="owner/repo", slice_number=999999)

        captured = capsys.readouterr()
        assert exit_code == ExitCode.FAILURE
        assert captured.out == ""
        assert "no sessions for the sub-issue 999999 in owner/repo" in captured.err

    def test_should_report_the_split_as_not_available_yet_when_the_session_has_no_reading(
        self, list_slice_sessions_handler: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        session = AgentSessionDTO(
            slice_number="363",
            outcome="running",
            task_type="review_slice",
            engine="claude",
            run_id="run-1",
            started_at=_STARTED_AT,
            has_log=True,
            elapsed_seconds=12.0,
            total_cost_usd=None,
            models=[],
            cost_split=None,
        )
        list_slice_sessions_handler.return_value = ListSliceSessionsQueryResult(sessions=[session])

        exit_code = usage_command.run(repo="owner/repo", slice_number=363)

        out = capsys.readouterr().out
        assert exit_code == 0
        assert "split: unavailable" in out
        assert "basis:" not in out

    def test_should_print_the_turn_growth_ordered_by_added_tokens(
        self, list_slice_sessions_handler: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        session = AgentSessionDTO(
            slice_number="363",
            outcome="succeeded",
            task_type="implement_slice",
            engine="claude",
            run_id="run-1",
            started_at=_STARTED_AT,
            has_log=True,
            elapsed_seconds=12.0,
            total_cost_usd=None,
            models=[],
            cost_split=None,
            turn_growth=[
                TurnGrowthDTO(turn=7, added_tokens=6200, after_action="Bash · run migration"),
                TurnGrowthDTO(turn=1, added_tokens=64500, after_action=None),
            ],
        )
        list_slice_sessions_handler.return_value = ListSliceSessionsQueryResult(sessions=[session])

        exit_code = usage_command.run(repo="owner/repo", slice_number=363)

        out = capsys.readouterr().out
        assert exit_code == 0
        assert "#7 after Bash · run migration" in out
        assert "6200 tokens" in out
        assert "#1 startup" in out
        assert "64500 tokens" in out
        assert out.index("#7") < out.index("#1")

    def test_should_print_no_turn_growth_block_when_the_session_has_none(
        self, list_slice_sessions_handler: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        session = AgentSessionDTO(
            slice_number="363",
            outcome="succeeded",
            task_type="implement_slice",
            engine="claude",
            run_id="run-1",
            started_at=_STARTED_AT,
            has_log=True,
            elapsed_seconds=12.0,
            total_cost_usd=None,
            models=[],
            cost_split=None,
        )
        list_slice_sessions_handler.return_value = ListSliceSessionsQueryResult(sessions=[session])

        exit_code = usage_command.run(repo="owner/repo", slice_number=363)

        out = capsys.readouterr().out
        assert exit_code == 0
        assert "tokens" not in out

    def test_should_print_one_row_per_model_with_its_cost_input_cache_share_and_output(
        self, list_slice_sessions_handler: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        session = AgentSessionDTO(
            slice_number="417",
            outcome="succeeded",
            task_type="implement_slice",
            engine="claude",
            run_id="run-1",
            started_at=_STARTED_AT,
            has_log=True,
            elapsed_seconds=12.0,
            total_cost_usd=3.5,
            models=[
                ModelUsageDTO(
                    model="claude-opus-5-5",
                    input_tokens=100,
                    output_tokens=2000,
                    cache_read_tokens=800,
                    cache_creation_tokens=100,
                    cost_usd=3.25,
                ),
                ModelUsageDTO(
                    model="claude-haiku-4-5-20251001",
                    input_tokens=50,
                    output_tokens=300,
                    cache_read_tokens=0,
                    cache_creation_tokens=150,
                    cost_usd=0.25,
                ),
            ],
            cost_split=None,
        )
        list_slice_sessions_handler.return_value = ListSliceSessionsQueryResult(sessions=[session])

        exit_code = usage_command.run(repo="owner/repo", slice_number=417)

        out = capsys.readouterr().out
        assert exit_code == 0
        assert "models:" in out
        assert "  claude-opus-5-5 $3.2500 input 1000 tokens · 80.0% cache · output 2000 tokens" in out
        assert "  claude-haiku-4-5-20251001 $0.2500 input 200 tokens · 0.0% cache · output 300 tokens" in out
