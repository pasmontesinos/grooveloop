from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.infrastructure.local_agent_session_repository import LocalAgentSessionRepository
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.agent_run_cause import AgentRunCause
from grooveloop.shared.domain.agent_run_reading import AgentRunReading
from grooveloop.shared.domain.agent_task_type import AgentTaskType
from grooveloop.shared.domain.cost_basis import CostBasis
from grooveloop.shared.domain.cost_share import CostShare
from grooveloop.shared.domain.cost_split import CostSplit
from grooveloop.shared.domain.model_usage import ModelUsage
from grooveloop.shared.domain.token_class import TokenClass
from grooveloop.shared.domain.tool_tally import ToolTally
from grooveloop.shared.domain.turn_growth import TurnGrowth
from grooveloop.shared.infrastructure.claude_log_reader import ClaudeLogReader
from tests.playground.shared.infrastructure.clock import clock_at
from tests.playground.shared.infrastructure.fake_agent_log_reader import FakeAgentLogReader

if TYPE_CHECKING:
    from pathlib import Path

    from grooveloop.shared.domain.agent_log_reader import AgentLogReader


_NOW = datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC)
_LING_USAGE = ModelUsage(
    model="openrouter/inclusionai/ling-3.0-flash:free",
    input_tokens=120,
    output_tokens=45,
    cache_read_tokens=30,
    cache_creation_tokens=12,
    cost_usd=0.0,
)
_OPUS_USAGE = ModelUsage(
    model="claude-opus-4",
    input_tokens=10,
    output_tokens=20,
    cache_read_tokens=0,
    cache_creation_tokens=0,
    cost_usd=0.42,
)
_BASH_TALLY = ToolTally(name="Bash", count=3)


def _repository(runs_dir: Path, *readers: AgentLogReader) -> LocalAgentSessionRepository:
    return LocalAgentSessionRepository(
        runs_dir=runs_dir, clock=clock_at(_NOW), log_readers={reader.engine: reader for reader in readers}
    )


def _seed_run(
    runs_dir: Path,
    run_id: str,
    *,
    repo: str,
    slice_id: str,
    task_type: str,
    started_at: datetime,
    log: str,
    launch_model: str | None = None,
    engine: str | None = None,
    profile: str | None = None,
    log_written_at: datetime | None = None,
) -> None:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
    metadata: dict[str, object] = {
        "task_type": task_type,
        "started_at": started_at.isoformat(),
        "slice_id": slice_id,
        "repo": repo,
    }
    if launch_model is not None:
        metadata["launch_model"] = launch_model
    if engine is not None:
        metadata["engine"] = engine
    if profile is not None:
        metadata["profile"] = profile
    (run_dir / "run.json").write_text(json.dumps(metadata))
    agent_log = run_dir / "agent.log"
    agent_log.write_text(log)
    if log_written_at is not None:
        written_at = log_written_at.timestamp()
        os.utime(agent_log, (written_at, written_at))


@pytest.mark.integration
class TestLocalAgentSessionRepository:
    def test_search_returns_only_sessions_of_the_repo_and_slice_in_chronological_order(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "later",
            repo="owner/repo",
            slice_id="12",
            task_type="address_review",
            started_at=_NOW.replace(minute=10),
            log="done\n[AGENT_EXIT] 0\n",
        )
        _seed_run(
            runs_dir,
            "earlier",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW.replace(minute=0),
            log="done\n[AGENT_EXIT] 0\n",
        )
        _seed_run(
            runs_dir,
            "other-slice",
            repo="owner/repo",
            slice_id="99",
            task_type="implement_slice",
            started_at=_NOW,
            log="done\n[AGENT_EXIT] 0\n",
        )
        _seed_run(
            runs_dir,
            "other-repo",
            repo="other/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="done\n[AGENT_EXIT] 0\n",
        )
        repository = _repository(runs_dir, ClaudeLogReader())

        sessions = repository.search(repo="owner/repo", slice_id=SliceId("12"))

        assert [session.task_type for session in sessions] == [
            AgentTaskType.IMPLEMENT_SLICE,
            AgentTaskType.ADDRESS_REVIEW,
        ]

    def test_search_returns_every_slice_of_the_repo_when_it_is_given_no_slice(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "mine-early",
            repo="owner/repo",
            slice_id="11",
            task_type="implement_slice",
            started_at=_NOW.replace(minute=0),
            log="done\n[AGENT_EXIT] 0\n",
        )
        _seed_run(
            runs_dir,
            "mine-late",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW.replace(minute=10),
            log="done\n[AGENT_EXIT] 0\n",
        )
        _seed_run(
            runs_dir,
            "other-repo",
            repo="other/repo",
            slice_id="13",
            task_type="implement_slice",
            started_at=_NOW,
            log="done\n[AGENT_EXIT] 0\n",
        )
        repository = _repository(runs_dir, ClaudeLogReader())

        sessions = repository.search(repo="owner/repo")

        assert [session.slice_id for session in sessions] == [SliceId("11"), SliceId("12")]

    def test_search_ignores_runs_without_repo_or_slice_id(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        legacy = runs_dir / "legacy"
        legacy.mkdir(parents=True)
        (legacy / "run.json").write_text(json.dumps({"task_type": "implement_slice", "started_at": _NOW.isoformat()}))
        (legacy / "agent.log").write_text("done\n[AGENT_EXIT] 0\n")
        repository = _repository(runs_dir, ClaudeLogReader())

        assert repository.search(repo="owner/repo", slice_id=SliceId("12")) == []

    def test_search_returns_empty_when_runs_dir_is_missing(self, tmp_path: Path) -> None:
        repository = _repository(tmp_path / "missing", ClaudeLogReader())

        assert repository.search(repo="owner/repo", slice_id=SliceId("12")) == []

    def test_search_reports_outcome_cost_and_models_for_a_terminal_run(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        payload = json.dumps(
            {
                "type": "result",
                "total_cost_usd": 0.42,
                "modelUsage": {"claude-opus-4": {"inputTokens": 10, "outputTokens": 20, "costUSD": 0.42}},
            }
        )
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log=f"{payload}\n[AGENT_EXIT] 0\n",
        )
        repository = _repository(runs_dir, ClaudeLogReader())

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.outcome == AgentOutcome.SUCCEEDED
        assert session.total_cost_usd == 0.42
        assert [model.model for model in session.models] == ["claude-opus-4"]

    def test_search_reports_the_outcome_and_cause_declared_by_the_log_of_a_terminal_run(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        payload = json.dumps({"type": "result", "is_error": True, "api_error_status": 529, "result": "Overloaded"})
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log=f"{payload}\n[AGENT_EXIT] 1\n",
        )
        repository = _repository(runs_dir, ClaudeLogReader())

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert (session.outcome, session.cause) == (AgentOutcome.INTERRUPTED, AgentRunCause.OVERLOADED)

    def test_search_reports_the_outcome_of_a_long_opencode_log_from_its_tail(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        events = "".join(
            json.dumps({"type": "step", "index": index, "padding": "x" * 500}) + "\n" for index in range(400)
        )
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log=f"{events}[AGENT_EXIT] 1\n",
            engine="opencode",
        )
        repository = _repository(runs_dir, FakeAgentLogReader("opencode", AgentRunReading()))

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.outcome == AgentOutcome.FAILED

    def test_search_reads_the_usage_from_the_full_log_of_a_terminal_run(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        events = "".join(
            json.dumps({"type": "assistant", "index": index, "padding": "x" * 500}) + "\n" for index in range(2_000)
        )
        result = json.dumps(
            {
                "type": "result",
                "total_cost_usd": 0.42,
                "modelUsage": {"claude-opus-4": {"inputTokens": 10, "outputTokens": 20, "costUSD": 0.42}},
            }
        )
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log=f"{events}{result}\n[AGENT_EXIT] 0\n",
        )
        reader = FakeAgentLogReader("claude", AgentRunReading(total_cost_usd=0.42, models=[_OPUS_USAGE]))
        repository = _repository(runs_dir, reader)

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.total_cost_usd == 0.42
        assert len(reader.log_text) > len(events)

    def test_search_tolerates_an_invalid_utf8_byte_in_the_log_of_a_terminal_run(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="",
        )
        (runs_dir / "run-1" / "agent.log").write_bytes(b"done\n\xffinvalid\n[AGENT_EXIT] 0\n")
        reader = FakeAgentLogReader("claude", AgentRunReading(total_cost_usd=0.42, models=[_OPUS_USAGE]))
        repository = _repository(runs_dir, reader)

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.total_cost_usd == 0.42

    def test_search_reports_the_launch_model_of_the_run(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="done\n[AGENT_EXIT] 0\n",
            launch_model="opus",
        )
        repository = _repository(runs_dir, ClaudeLogReader())

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.launch_model == "opus"

    def test_search_reports_no_launch_model_for_a_legacy_run(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="done\n[AGENT_EXIT] 0\n",
        )
        repository = _repository(runs_dir, ClaudeLogReader())

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.launch_model is None

    def test_search_reports_the_run_id_profile_and_start_of_the_run(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "5cf547af",
            repo="owner/repo",
            slice_id="12",
            task_type="review_slice",
            started_at=_NOW.replace(minute=5),
            log="done\n[AGENT_EXIT] 0\n",
            profile="reviewer",
        )
        repository = _repository(runs_dir, ClaudeLogReader())

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.run_id == "5cf547af"
        assert session.profile == "reviewer"
        assert session.started_at == _NOW.replace(minute=5)

    def test_search_reports_no_profile_for_a_legacy_run(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="done\n[AGENT_EXIT] 0\n",
        )
        repository = _repository(runs_dir, ClaudeLogReader())

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.profile is None

    def test_search_reports_that_a_run_with_its_log_has_a_log(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="working\n",
        )
        repository = _repository(runs_dir, ClaudeLogReader())

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.has_log is True

    def test_search_reports_the_engine_recorded_in_the_run_metadata(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="done\n[AGENT_EXIT] 0\n",
            engine="opencode",
        )
        repository = _repository(runs_dir, ClaudeLogReader())

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.engine == "opencode"

    def test_search_reports_claude_as_the_engine_of_a_legacy_run(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="done\n[AGENT_EXIT] 0\n",
        )
        repository = _repository(runs_dir, ClaudeLogReader())

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.engine == "claude"

    def test_search_reports_running_when_there_is_no_exit_marker(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="working\n",
        )
        repository = _repository(runs_dir, ClaudeLogReader())

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.outcome == AgentOutcome.RUNNING
        assert session.total_cost_usd is None
        assert session.models == []

    def test_search_reads_the_usage_with_the_reader_of_the_engine_of_the_run(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="done\n[AGENT_EXIT] 0\n",
            engine="opencode",
        )
        repository = _repository(
            runs_dir,
            FakeAgentLogReader("claude", AgentRunReading(total_cost_usd=9.9)),
            FakeAgentLogReader("opencode", AgentRunReading(total_cost_usd=0.0, models=[_LING_USAGE])),
        )

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.total_cost_usd == 0.0
        assert [(model.input_tokens, model.output_tokens) for model in session.models] == [(120, 45)]

    def test_search_caches_the_usage_of_a_terminal_run_and_reuses_it(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="done\n[AGENT_EXIT] 0\n",
            engine="opencode",
        )
        opencode = FakeAgentLogReader("opencode", AgentRunReading(total_cost_usd=0.0, models=[_LING_USAGE]))
        repository = _repository(runs_dir, opencode)

        repository.search(repo="owner/repo", slice_id=SliceId("12"))
        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert opencode.calls == 1
        assert json.loads((runs_dir / "run-1" / "usage.json").read_text())["models"][0]["model"] == _LING_USAGE.model
        assert session.models == [_LING_USAGE]
        assert session.total_cost_usd == 0.0

    def test_search_stores_the_usage_of_a_terminal_run_even_when_it_has_no_metrics(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="done\n[AGENT_EXIT] 0\n",
            engine="opencode",
        )
        repository = _repository(runs_dir, FakeAgentLogReader("opencode", AgentRunReading()))

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.total_cost_usd is None
        assert session.models == []
        assert (runs_dir / "run-1" / "usage.json").exists()

    def test_search_reports_the_run_stats_of_a_terminal_run(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="done\n[AGENT_EXIT] 0\n",
            engine="opencode",
        )
        reading = AgentRunReading(
            total_cost_usd=0.0,
            models=[_LING_USAGE],
            turns=5,
            subagents=1,
            skills=["brainstorming"],
            tools=[_BASH_TALLY],
        )
        repository = _repository(runs_dir, FakeAgentLogReader("opencode", reading))

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.turns == 5
        assert session.subagents == 1
        assert session.skills == ["brainstorming"]
        assert session.tools == [_BASH_TALLY]
        stored = json.loads((runs_dir / "run-1" / "usage.json").read_text())
        assert stored["version"] == 3
        assert stored["turns"] == 5
        assert stored["tools"] == [{"name": "Bash", "count": 3}]

    def test_search_stores_and_reloads_the_cost_split(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="done\n[AGENT_EXIT] 0\n",
            engine="claude",
        )
        split = CostSplit(
            basis=CostBasis.DERIVED,
            shares=[
                CostShare(TokenClass.INPUT, 10, 0.01),
                CostShare(TokenClass.CACHE_READ, 0, None),
                CostShare(TokenClass.CACHE_WRITE, 0, None),
                CostShare(TokenClass.OUTPUT, 5, 0.02),
            ],
        )
        reading = AgentRunReading(total_cost_usd=0.03, models=[_OPUS_USAGE], cost_split=split)
        repository = _repository(runs_dir, FakeAgentLogReader("claude", reading))

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.cost_split == split
        stored = json.loads((runs_dir / "run-1" / "usage.json").read_text())
        assert stored["version"] == 3
        assert stored["cost_split"]["basis"] == "derived"
        assert stored["cost_split"]["shares"][0] == {"token_class": "input", "tokens": 10, "cost_usd": 0.01}

        reloaded_repository = _repository(runs_dir, FakeAgentLogReader("claude", AgentRunReading()))
        reloaded_session = reloaded_repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert reloaded_session.cost_split == split

    def test_search_reports_no_cost_split_when_the_cached_v3_usage_file_lacks_it(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="done\n[AGENT_EXIT] 0\n",
            engine="claude",
        )
        (runs_dir / "run-1" / "usage.json").write_text(
            json.dumps({"version": 3, "total_cost_usd": 0.1, "models": [asdict(_OPUS_USAGE)]})
        )
        repository = _repository(runs_dir, FakeAgentLogReader("claude", AgentRunReading(turns=1)))

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.cost_split is None

    def test_search_reloads_and_migrates_a_v1_usage_file_to_v3(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="done\n[AGENT_EXIT] 0\n",
            engine="opencode",
        )
        (runs_dir / "run-1" / "usage.json").write_text(
            json.dumps({"total_cost_usd": 0.1, "models": [asdict(_LING_USAGE)]})
        )
        reader = FakeAgentLogReader("opencode", AgentRunReading(total_cost_usd=0.0, models=[_OPUS_USAGE], turns=5))
        repository = _repository(runs_dir, reader)

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert reader.calls == 1
        assert session.total_cost_usd == 0.0
        stored = json.loads((runs_dir / "run-1" / "usage.json").read_text())
        assert stored["version"] == 3
        assert stored["turns"] == 5

    def test_search_reports_no_metrics_when_the_engine_has_no_reader(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="done\n[AGENT_EXIT] 0\n",
            engine="unknown",
        )
        repository = _repository(runs_dir, FakeAgentLogReader("claude", AgentRunReading(total_cost_usd=1.0)))

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.total_cost_usd is None
        assert session.models == []

    def test_search_reports_the_last_event_of_a_running_run_from_the_write_time_of_its_log(
        self, tmp_path: Path
    ) -> None:
        runs_dir = tmp_path / "runs"
        written_at = _NOW.replace(minute=45)
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW.replace(minute=40),
            log="working\n",
            log_written_at=written_at,
        )
        repository = _repository(runs_dir, ClaudeLogReader())

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.last_event_at == written_at

    def test_search_reports_no_last_event_when_the_run_has_no_log(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        run_dir = runs_dir / "run-1"
        run_dir.mkdir(parents=True)
        metadata = {
            "task_type": "implement_slice",
            "started_at": _NOW.isoformat(),
            "slice_id": "12",
            "repo": "owner/repo",
        }
        (run_dir / "run.json").write_text(json.dumps(metadata))
        repository = _repository(runs_dir, ClaudeLogReader())

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.last_event_at is None
        assert session.has_log is False

    def test_search_reports_the_last_action_of_a_running_run_with_the_reader_of_its_engine(
        self, tmp_path: Path
    ) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="working\n",
            engine="opencode",
        )
        reader = FakeAgentLogReader("opencode", AgentRunReading(), action="bash · Run the tests")
        repository = _repository(runs_dir, reader)

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.last_action == "bash · Run the tests"
        assert reader.action_log_tail == "working"

    def test_search_reports_the_last_action_when_later_events_are_not_tool_calls(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        tool_use = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [{"type": "tool_use", "name": "Bash", "input": {"description": "Run the tests"}}]
                },
            }
        )
        noise = "".join(json.dumps({"type": "user", "index": index}) + "\n" for index in range(30))
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log=f"{tool_use}\n{noise}",
        )
        repository = _repository(runs_dir, ClaudeLogReader())

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.last_action == "Bash · Run the tests"

    def test_search_reports_no_last_action_for_a_terminal_run(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="working\n[AGENT_EXIT] 0\n",
            engine="opencode",
        )
        reader = FakeAgentLogReader("opencode", AgentRunReading(), action="bash · Run the tests")
        repository = _repository(runs_dir, reader)

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.last_action is None

    def test_search_reports_no_last_action_when_the_engine_has_no_reader(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="working\n",
            engine="unknown",
        )
        repository = _repository(runs_dir, ClaudeLogReader())

        session = repository.search(repo="owner/repo", slice_id=SliceId("12"))[0]

        assert session.last_action is None


@pytest.mark.integration
class TestLocalAgentSessionRepositorySearchTranscripts:
    def test_search_transcripts_pairs_each_session_with_its_turn_growth_sorted_by_added_tokens(
        self, tmp_path: Path
    ) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="done\n[AGENT_EXIT] 0\n",
        )
        reader = FakeAgentLogReader("claude", AgentRunReading())
        reader.turn_growth_reading = [
            TurnGrowth(turn=1, added_tokens=100, after_action=None),
            TurnGrowth(turn=2, added_tokens=6000, after_action="Bash · run tests"),
        ]
        repository = _repository(runs_dir, reader)

        transcripts = repository.search_transcripts(repo="owner/repo", slice_id=SliceId("12"))

        assert len(transcripts) == 1
        assert transcripts[0].session.slice_id == SliceId("12")
        assert [turn.turn for turn in transcripts[0].turn_growth] == [2, 1]

    def test_search_transcripts_returns_no_turn_growth_for_a_running_session(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="working\n",
        )
        repository = _repository(runs_dir, ClaudeLogReader())

        transcripts = repository.search_transcripts(repo="owner/repo", slice_id=SliceId("12"))

        assert transcripts[0].turn_growth == []

    def test_search_transcripts_caches_the_result_in_its_own_versioned_file_and_reuses_it(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="done\n[AGENT_EXIT] 0\n",
        )
        reader = FakeAgentLogReader("claude", AgentRunReading())
        reader.turn_growth_reading = [TurnGrowth(turn=1, added_tokens=100, after_action=None)]
        repository = _repository(runs_dir, reader)

        repository.search_transcripts(repo="owner/repo", slice_id=SliceId("12"))
        transcripts = repository.search_transcripts(repo="owner/repo", slice_id=SliceId("12"))

        assert reader.turn_growth_calls == 1
        stored = json.loads((runs_dir / "run-1" / "turns.json").read_text())
        assert stored["version"] == 1
        assert stored["turn_growth"] == [{"turn": 1, "added_tokens": 100, "after_action": None}]
        assert transcripts[0].turn_growth == [TurnGrowth(turn=1, added_tokens=100, after_action=None)]

    def test_search_transcripts_ignores_a_turns_file_with_a_stale_version(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="done\n[AGENT_EXIT] 0\n",
        )
        (runs_dir / "run-1" / "turns.json").write_text(
            json.dumps({"turn_growth": [{"turn": 9, "added_tokens": 1, "after_action": None}]})
        )
        reader = FakeAgentLogReader("claude", AgentRunReading())
        reader.turn_growth_reading = [TurnGrowth(turn=1, added_tokens=100, after_action=None)]
        repository = _repository(runs_dir, reader)

        transcripts = repository.search_transcripts(repo="owner/repo", slice_id=SliceId("12"))

        assert reader.turn_growth_calls == 1
        assert transcripts[0].turn_growth == [TurnGrowth(turn=1, added_tokens=100, after_action=None)]

    def test_search_transcripts_composes_the_session_metrics_and_the_turn_growth_from_a_single_walk(
        self, tmp_path: Path
    ) -> None:
        runs_dir = tmp_path / "runs"
        _seed_run(
            runs_dir,
            "run-1",
            repo="owner/repo",
            slice_id="12",
            task_type="implement_slice",
            started_at=_NOW,
            log="done\n[AGENT_EXIT] 0\n",
        )
        reader = FakeAgentLogReader("claude", AgentRunReading(total_cost_usd=0.42, models=[_OPUS_USAGE]))
        reader.turn_growth_reading = [TurnGrowth(turn=1, added_tokens=100, after_action=None)]
        repository = _repository(runs_dir, reader)

        transcripts = repository.search_transcripts(repo="owner/repo", slice_id=SliceId("12"))

        assert transcripts[0].session.total_cost_usd == 0.42
        assert transcripts[0].turn_growth == [TurnGrowth(turn=1, added_tokens=100, after_action=None)]
        assert (runs_dir / "run-1" / "usage.json").exists()
        assert (runs_dir / "run-1" / "turns.json").exists()
