from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from grooveloop.shared.domain.agent_log_action import AgentLogAction
from grooveloop.shared.domain.agent_log_reader import AgentLogReader
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.agent_run_cause import AgentRunCause
from grooveloop.shared.domain.agent_run_reading import AgentRunReading
from grooveloop.shared.domain.agent_run_verdict import AgentRunVerdict
from grooveloop.shared.domain.model_usage import ModelUsage
from grooveloop.shared.infrastructure.agent_action import describe_action, describe_actions, describe_last_action
from grooveloop.shared.infrastructure.agent_exit_marker import is_terminated
from grooveloop.shared.infrastructure.opencode_cost_split_parser import parse_cost_split
from grooveloop.shared.infrastructure.opencode_json_numbers import parse_float, parse_int
from grooveloop.shared.infrastructure.opencode_tool_tally_parser import parse_tool_tallies
from grooveloop.shared.infrastructure.opencode_turn_growth_parser import parse_turn_growth
from grooveloop.shared.infrastructure.opencode_turn_parser import parse_turns

if TYPE_CHECKING:
    from grooveloop.shared.domain.turn_growth import TurnGrowth

_ENGINE = "opencode"
_BINARY = "opencode"
_SESSION_KEY = "sessionID"
_EXPORT_FILE = "export.json"
_TOOL_USE_EVENT = "tool_use"


class OpencodeLogReader(AgentLogReader):
    @property
    def engine(self) -> str:
        return _ENGINE

    def read(self, log_text: str) -> AgentRunReading:
        turns, subagents = parse_turns(log_text)
        skills, tools = parse_tool_tallies(log_text)
        entries = _exported_usage_entries(log_text)
        models = _aggregate(entries)

        return AgentRunReading(
            total_cost_usd=sum(model.cost_usd for model in models) if len(models) > 0 else None,
            models=models,
            turns=turns,
            subagents=subagents,
            skills=skills,
            tools=tools,
            cost_split=parse_cost_split(entries),
        )

    def last_action(self, log_tail: str) -> str | None:
        return describe_last_action(log_tail, _describe)

    def turn_growth(self, log_text: str) -> list[TurnGrowth]:
        return parse_turn_growth(log_text)

    def actions(self, log_text: str) -> list[AgentLogAction]:
        return describe_actions(log_text, _actions_of)

    def verdict(self, log_tail: str, exit_code: int) -> AgentRunVerdict:
        if is_terminated(exit_code):
            return AgentRunVerdict(AgentOutcome.INTERRUPTED, AgentRunCause.TERMINATED)

        return AgentRunVerdict(AgentOutcome.FAILED, AgentRunCause.UNKNOWN)


def _actions_of(event: dict[str, Any]) -> list[AgentLogAction]:
    description = _describe(event)
    if description is None:
        return []

    part = event.get("part")
    part_id = part.get("id") if isinstance(part, dict) else None

    return [AgentLogAction(description, part_id if isinstance(part_id, str) else None)]


def _describe(event: dict[str, Any]) -> str | None:
    if event.get("type") != _TOOL_USE_EVENT:
        return None

    part = event.get("part")
    if not isinstance(part, dict):
        return None

    state = part.get("state")

    return describe_action(str(part.get("tool", "")), state.get("input") if isinstance(state, dict) else None)


def _exported_usage_entries(log_text: str) -> list[dict[str, Any]]:
    session_id = _session_id(log_text)
    if session_id is None:
        return []

    return _usage_entries(_export(session_id))


def _session_id(log_text: str) -> str | None:
    for line in log_text.splitlines():
        event = _load(line)
        session_id = event.get(_SESSION_KEY) if isinstance(event, dict) else None
        if isinstance(session_id, str) and len(session_id) > 0:
            return session_id

    return None


def _export(session_id: str) -> Any:
    with tempfile.TemporaryDirectory() as directory:
        export = Path(directory) / _EXPORT_FILE
        try:
            with export.open("w") as handle:
                subprocess.run(
                    [_BINARY, "export", session_id],
                    stdout=handle,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    check=True,
                )
        except (OSError, subprocess.SubprocessError):
            return None

        return _load(export.read_text())


def _load(text: str) -> Any:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _usage_entries(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [entry for item in payload for entry in _usage_entries(item)]

    if not isinstance(payload, dict):
        return []

    if _is_usage(payload):
        return [payload]

    return [entry for value in payload.values() for entry in _usage_entries(value)]


def _is_usage(payload: dict[str, Any]) -> bool:
    return isinstance(payload.get("tokens"), dict) and isinstance(payload.get("providerID"), str)


def _aggregate(entries: list[dict[str, Any]]) -> list[ModelUsage]:
    totals: dict[str, ModelUsage] = {}
    for entry in entries:
        usage = _to_model_usage(entry)
        totals[usage.model] = _merge(totals[usage.model], usage) if usage.model in totals else usage

    return list(totals.values())


def _to_model_usage(entry: dict[str, Any]) -> ModelUsage:
    tokens = entry["tokens"]
    cache = tokens["cache"] if isinstance(tokens.get("cache"), dict) else {}

    return ModelUsage(
        model=_model_name(entry),
        input_tokens=parse_int(tokens.get("input")),
        output_tokens=parse_int(tokens.get("output")),
        cache_read_tokens=parse_int(cache.get("read")),
        cache_creation_tokens=parse_int(cache.get("write")),
        cost_usd=parse_float(entry.get("cost")),
    )


def _model_name(entry: dict[str, Any]) -> str:
    parts = (entry.get("providerID"), entry.get("modelID"))

    return "/".join(str(part) for part in parts if part is not None)


def _merge(left: ModelUsage, right: ModelUsage) -> ModelUsage:
    return ModelUsage(
        model=left.model,
        input_tokens=left.input_tokens + right.input_tokens,
        output_tokens=left.output_tokens + right.output_tokens,
        cache_read_tokens=left.cache_read_tokens + right.cache_read_tokens,
        cache_creation_tokens=left.cache_creation_tokens + right.cache_creation_tokens,
        cost_usd=left.cost_usd + right.cost_usd,
    )
