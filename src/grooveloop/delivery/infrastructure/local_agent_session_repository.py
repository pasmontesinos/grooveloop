from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from grooveloop.delivery.domain.agent_session import AgentSession
from grooveloop.delivery.domain.agent_session_repository import AgentSessionRepository
from grooveloop.delivery.domain.agent_session_transcript import AgentSessionTranscript
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.agent_run_reading import AgentRunReading
from grooveloop.shared.domain.agent_task_type import AgentTaskType
from grooveloop.shared.domain.cost_basis import CostBasis
from grooveloop.shared.domain.cost_share import CostShare
from grooveloop.shared.domain.cost_split import CostSplit
from grooveloop.shared.domain.model_usage import ModelUsage
from grooveloop.shared.domain.token_class import TokenClass
from grooveloop.shared.domain.tool_tally import ToolTally
from grooveloop.shared.domain.turn_growth import TurnGrowth
from grooveloop.shared.infrastructure.agent_run_verdict_reader import read_run_verdict
from grooveloop.shared.infrastructure.log_tail import read_log_tail

if TYPE_CHECKING:
    from pathlib import Path

    from grooveloop.shared.domain.agent_log_reader import AgentLogReader
    from grooveloop.shared.domain.agent_run_cause import AgentRunCause
    from grooveloop.shared.domain.clock import Clock

_METADATA_FILE = "run.json"
_LOG_FILE = "agent.log"
_USAGE_FILE = "usage.json"
_USAGE_VERSION = 3
_TURNS_FILE = "turns.json"
_TURNS_VERSION = 1
_TAIL_LINES = 40
_TAIL_BYTES = 262_144
_DEFAULT_ENGINE = "claude"


@dataclass(frozen=True)
class _Match:
    started_at: datetime
    run_dir: Path
    data: dict[str, Any]
    state: AgentOutcome
    cause: AgentRunCause
    engine: str


class LocalAgentSessionRepository(AgentSessionRepository):
    def __init__(self, runs_dir: Path, clock: Clock, log_readers: dict[str, AgentLogReader]) -> None:
        self._runs_dir = runs_dir
        self._clock = clock
        self._log_readers = log_readers

    def search(self, repo: str, slice_id: SliceId | None = None) -> list[AgentSession]:
        return [self._to_session(match) for match in self._matches(repo, slice_id)]

    def search_transcripts(self, repo: str, slice_id: SliceId | None = None) -> list[AgentSessionTranscript]:
        return [
            AgentSessionTranscript(session=self._to_session(match), turn_growth=self._turns(match))
            for match in self._matches(repo, slice_id)
        ]

    def _matches(self, repo: str, slice_id: SliceId | None) -> list[_Match]:
        if not self._runs_dir.is_dir():
            return []

        matched = [
            match for run_dir in self._runs_dir.iterdir() if (match := self._match(run_dir, repo, slice_id)) is not None
        ]
        matched.sort(key=lambda match: match.started_at)

        return matched

    def _match(self, run_dir: Path, repo: str, slice_id: SliceId | None) -> _Match | None:
        metadata = run_dir / _METADATA_FILE
        if not metadata.is_file():
            return None

        data = json.loads(metadata.read_text())
        if data.get("repo") != repo:
            return None

        run_slice_id = data.get("slice_id")
        if run_slice_id is None or (slice_id is not None and run_slice_id != slice_id.value):
            return None

        started_at = datetime.fromisoformat(data["started_at"])
        engine = data.get("engine", _DEFAULT_ENGINE)
        verdict = read_run_verdict(run_dir, engine, self._log_readers)

        return _Match(started_at, run_dir, data, verdict.outcome, verdict.cause, engine)

    def _to_session(self, match: _Match) -> AgentSession:
        reading = self._metrics(match.run_dir, match.state, match.engine)

        return AgentSession(
            slice_id=SliceId(match.data["slice_id"]),
            outcome=match.state,
            cause=match.cause,
            task_type=AgentTaskType(match.data["task_type"]),
            engine=match.engine,
            run_id=match.run_dir.name,
            started_at=match.started_at,
            has_log=(match.run_dir / _LOG_FILE).is_file(),
            elapsed_seconds=self._elapsed(match.run_dir, match.started_at, match.state),
            total_cost_usd=reading.total_cost_usd,
            models=reading.models,
            launch_model=match.data.get("launch_model"),
            last_event_at=self._last_event_at(match.run_dir),
            last_action=reading.last_action,
            turns=reading.turns,
            subagents=reading.subagents,
            skills=reading.skills,
            tools=reading.tools,
            cost_split=reading.cost_split,
            profile=match.data.get("profile"),
        )

    def _metrics(self, run_dir: Path, state: AgentOutcome, engine: str) -> AgentRunReading:
        log = run_dir / _LOG_FILE
        if not log.is_file():
            return AgentRunReading()

        if state == AgentOutcome.RUNNING:
            return AgentRunReading(last_action=self._last_action(log, engine))

        cached = self._cached_metrics(run_dir)
        if cached is not None:
            return cached

        reader = self._log_readers.get(engine)
        if reader is None:
            return AgentRunReading()

        reading = reader.read(log.read_text(encoding="utf-8", errors="replace"))
        self._store_metrics(run_dir, reading)

        return reading

    def _turns(self, match: _Match) -> list[TurnGrowth]:
        if match.state == AgentOutcome.RUNNING:
            return []

        log = match.run_dir / _LOG_FILE
        if not log.is_file():
            return []

        cached = self._cached_turn_growth(match.run_dir)
        if cached is not None:
            return cached

        reader = self._log_readers.get(match.engine)
        if reader is None:
            return []

        turns = sorted(
            reader.turn_growth(log.read_text(encoding="utf-8", errors="replace")),
            key=lambda turn: turn.added_tokens,
            reverse=True,
        )
        self._store_turn_growth(match.run_dir, turns)

        return turns

    def _last_action(self, log: Path, engine: str) -> str | None:
        reader = self._log_readers.get(engine)
        if reader is None:
            return None

        return reader.last_action(self._log_tail(log))

    def _log_tail(self, log: Path) -> str:
        return "\n".join(read_log_tail(log, _TAIL_LINES, _TAIL_BYTES))

    def _cached_metrics(self, run_dir: Path) -> AgentRunReading | None:
        usage = run_dir / _USAGE_FILE
        if not usage.is_file():
            return None

        data = json.loads(usage.read_text())
        if data.get("version") != _USAGE_VERSION:
            return None

        return AgentRunReading(
            total_cost_usd=data.get("total_cost_usd"),
            models=[ModelUsage(**model) for model in data.get("models", [])],
            turns=data.get("turns"),
            subagents=data.get("subagents"),
            skills=data.get("skills", []),
            tools=[ToolTally(**tool) for tool in data.get("tools", [])],
            cost_split=_cost_split_from_json(data.get("cost_split")),
        )

    def _store_metrics(self, run_dir: Path, reading: AgentRunReading) -> None:
        payload = {
            "version": _USAGE_VERSION,
            "total_cost_usd": reading.total_cost_usd,
            "models": [asdict(model) for model in reading.models],
            "turns": reading.turns,
            "subagents": reading.subagents,
            "skills": reading.skills,
            "tools": [asdict(tool) for tool in reading.tools],
            "cost_split": _cost_split_to_json(reading.cost_split),
        }

        (run_dir / _USAGE_FILE).write_text(json.dumps(payload))

    def _cached_turn_growth(self, run_dir: Path) -> list[TurnGrowth] | None:
        turns_file = run_dir / _TURNS_FILE
        if not turns_file.is_file():
            return None

        data = json.loads(turns_file.read_text())
        if data.get("version") != _TURNS_VERSION:
            return None

        return [TurnGrowth(**turn) for turn in data.get("turn_growth", [])]

    def _store_turn_growth(self, run_dir: Path, turns: list[TurnGrowth]) -> None:
        payload = {"version": _TURNS_VERSION, "turn_growth": [asdict(turn) for turn in turns]}

        (run_dir / _TURNS_FILE).write_text(json.dumps(payload))

    def _elapsed(self, run_dir: Path, started_at: datetime, state: AgentOutcome) -> float:
        end = self._clock.now() if state == AgentOutcome.RUNNING else self._log_mtime(run_dir)

        return max(0.0, (end - started_at).total_seconds())

    def _log_mtime(self, run_dir: Path) -> datetime:
        return self._last_event_at(run_dir) or self._clock.now()

    def _last_event_at(self, run_dir: Path) -> datetime | None:
        log = run_dir / _LOG_FILE
        if not log.is_file():
            return None

        return datetime.fromtimestamp(log.stat().st_mtime, tz=UTC)


def _cost_split_from_json(data: dict[str, Any] | None) -> CostSplit | None:
    if data is None:
        return None

    return CostSplit(
        basis=CostBasis(data["basis"]),
        shares=[
            CostShare(
                token_class=TokenClass(share["token_class"]),
                tokens=share["tokens"],
                cost_usd=share.get("cost_usd"),
            )
            for share in data.get("shares", [])
        ],
    )


def _cost_split_to_json(cost_split: CostSplit | None) -> dict[str, Any] | None:
    if cost_split is None:
        return None

    return {
        "basis": cost_split.basis.value,
        "shares": [
            {"token_class": share.token_class.value, "tokens": share.tokens, "cost_usd": share.cost_usd}
            for share in cost_split.shares
        ],
    }
