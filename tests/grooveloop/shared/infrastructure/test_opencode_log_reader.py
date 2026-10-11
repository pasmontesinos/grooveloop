from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from grooveloop.shared.domain.model_usage import ModelUsage
from grooveloop.shared.infrastructure.opencode_log_reader import OpencodeLogReader

if TYPE_CHECKING:
    from collections.abc import Callable

_RUN = "grooveloop.shared.infrastructure.opencode_log_reader.subprocess.run"
_LOG = '{"type": "step_start", "sessionID": "ses_123"}\n{"type": "text"}\n[AGENT_EXIT] 0\n'
_MODEL = "openrouter/inclusionai/ling-3.0-flash:free"


def _assistant(cost: float, input_tokens: int, output_tokens: int, cache_read: int, cache_write: int) -> dict[str, Any]:
    return {
        "info": {
            "role": "assistant",
            "providerID": "openrouter",
            "modelID": "inclusionai/ling-3.0-flash:free",
            "cost": cost,
            "tokens": {
                "input": input_tokens,
                "output": output_tokens,
                "reasoning": 7,
                "cache": {"read": cache_read, "write": cache_write},
            },
        }
    }


def _export(*assistants: dict[str, Any]) -> str:
    session_tokens = {
        "input": sum(entry["info"]["tokens"]["input"] for entry in assistants),
        "output": sum(entry["info"]["tokens"]["output"] for entry in assistants),
        "reasoning": 0,
        "cache": {"read": 0, "write": 0},
    }
    payload = {
        "info": {"id": "ses_123", "cost": sum(entry["info"]["cost"] for entry in assistants), "tokens": session_tokens},
        "messages": [{"info": {"role": "user", "model": {}, "sessionID": "ses_123"}}, *assistants],
    }

    return json.dumps(payload)


def _writing(payload: str) -> Callable[..., subprocess.CompletedProcess[bytes]]:
    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        kwargs["stdout"].write(payload)

        return subprocess.CompletedProcess(args=argv, returncode=0)

    return run


@pytest.mark.integration
class TestOpencodeLogReader:
    def test_should_declare_its_engine(self) -> None:
        assert OpencodeLogReader().engine == "opencode"

    def test_should_export_the_session_of_the_log_and_map_its_usage(self) -> None:
        export = _export(_assistant(0.0, 120, 45, 30, 12))

        with patch(_RUN, side_effect=_writing(export)) as run:
            reading = OpencodeLogReader().read(_LOG)

        assert run.call_args.args[0] == ["opencode", "export", "ses_123"]
        assert reading.total_cost_usd == 0.0
        assert reading.models == [
            ModelUsage(
                model=_MODEL,
                input_tokens=120,
                output_tokens=45,
                cache_read_tokens=30,
                cache_creation_tokens=12,
                cost_usd=0.0,
            )
        ]

    def test_should_aggregate_the_usage_of_every_assistant_message_of_the_session(self) -> None:
        export = _export(_assistant(0.5, 1, 2, 3, 4), _assistant(0.25, 10, 20, 30, 40))

        with patch(_RUN, side_effect=_writing(export)):
            reading = OpencodeLogReader().read(_LOG)

        assert reading.total_cost_usd == 0.75
        assert reading.models == [
            ModelUsage(
                model=_MODEL,
                input_tokens=11,
                output_tokens=22,
                cache_read_tokens=33,
                cache_creation_tokens=44,
                cost_usd=0.75,
            )
        ]

    def test_should_read_no_metrics_when_the_log_has_no_session_id(self) -> None:
        with patch(_RUN) as run:
            reading = OpencodeLogReader().read("working\n")

        run.assert_not_called()
        assert reading.turns == 0
        assert reading.subagents == 0
        assert reading.total_cost_usd is None
        assert reading.models == []
        assert reading.cost_split is not None
        assert reading.cost_split.basis.value == "unavailable"

    def test_should_read_no_metrics_when_the_session_has_no_assistant_message(self) -> None:
        with patch(_RUN, side_effect=_writing(_export())):
            reading = OpencodeLogReader().read(_LOG)

        assert reading.turns == 0
        assert reading.subagents == 0
        assert reading.models == []
        assert reading.cost_split is not None
        assert reading.cost_split.basis.value == "unavailable"

    def test_should_read_no_metrics_when_the_session_cannot_be_exported(self) -> None:
        with patch(_RUN, side_effect=subprocess.CalledProcessError(returncode=1, cmd="opencode")):
            reading = OpencodeLogReader().read(_LOG)

        assert reading.turns == 0
        assert reading.subagents == 0
        assert reading.models == []
        assert reading.cost_split is not None
        assert reading.cost_split.basis.value == "unavailable"

    def test_should_read_no_metrics_when_the_binary_is_missing(self) -> None:
        with patch(_RUN, side_effect=FileNotFoundError):
            reading = OpencodeLogReader().read(_LOG)

        assert reading.turns == 0
        assert reading.subagents == 0
        assert reading.models == []
        assert reading.cost_split is not None
        assert reading.cost_split.basis.value == "unavailable"

    def test_should_read_no_metrics_when_the_export_is_not_json(self) -> None:
        with patch(_RUN, side_effect=_writing("not json")):
            reading = OpencodeLogReader().read(_LOG)

        assert reading.turns == 0
        assert reading.subagents == 0
        assert reading.models == []
        assert reading.cost_split is not None
        assert reading.cost_split.basis.value == "unavailable"

    def test_should_read_the_derived_cost_split_of_the_session(self) -> None:
        export = _export(_assistant(0.5, 1, 2, 3, 4))

        with patch(_RUN, side_effect=_writing(export)):
            reading = OpencodeLogReader().read(_LOG)

        assert reading.cost_split is not None
        assert reading.cost_split.basis.value == "derived"


def _tool_use(tool: str, tool_input: dict[str, Any]) -> str:
    return json.dumps(
        {
            "type": "tool_use",
            "sessionID": "ses_123",
            "part": {"type": "tool", "tool": tool, "state": {"status": "completed", "input": tool_input}},
        }
    )


@pytest.mark.integration
class TestOpencodeLogReaderLastAction:
    def test_should_describe_the_last_tool_use_of_the_log(self) -> None:
        log_tail = _tool_use("read", {"filePath": "src/main.py"}) + "\n" + _tool_use("bash", {"description": "Run"})

        assert OpencodeLogReader().last_action(log_tail) == "bash · Run"

    def test_should_ignore_the_events_after_the_last_tool_use(self) -> None:
        log_tail = _tool_use("bash", {"description": "Run"}) + "\n" + json.dumps({"type": "step_finish"}) + "\n"

        assert OpencodeLogReader().last_action(log_tail) == "bash · Run"

    def test_should_not_describe_an_action_when_the_log_has_no_tool_use(self) -> None:
        assert OpencodeLogReader().last_action("working\n[AGENT_EXIT] 0\n") is None


@pytest.mark.integration
class TestOpencodeLogReaderRunStats:
    def test_should_read_the_turns_subagents_skills_and_tools_of_the_full_log(self) -> None:
        log = "\n".join(
            [
                json.dumps({"type": "step_start", "sessionID": "ses_123"}),
                _tool_use("skill", {"name": "writing-plans"}),
                json.dumps({"type": "step_finish"}),
                _tool_use("task", {}),
                json.dumps({"type": "step_finish"}),
            ]
        )

        with patch(_RUN, side_effect=_writing(_export())):
            reading = OpencodeLogReader().read(log)

        assert reading.turns == 2
        assert reading.subagents == 1
        assert reading.skills == ["writing-plans"]
        assert {tool.name: tool.count for tool in reading.tools} == {"skill": 1, "task": 1}


@pytest.mark.integration
class TestOpencodeLogReaderTurnGrowth:
    def test_should_delegate_the_turn_growth_calculation(self) -> None:
        log = json.dumps(
            {"type": "step_finish", "part": {"tokens": {"input": 100, "output": 1, "cache": {"read": 0, "write": 0}}}}
        )

        growth = OpencodeLogReader().turn_growth(log)

        assert [(turn.turn, turn.added_tokens) for turn in growth] == [(1, 100)]


@pytest.mark.integration
class TestOpencodeLogReaderActions:
    def test_should_describe_each_tool_use_of_the_log_in_order(self) -> None:
        log_text = "\n".join(
            [
                json.dumps({"type": "step_start", "sessionID": "ses_123"}),
                _tool_use("read", {"filePath": "src/main.py"}),
                json.dumps({"type": "text", "part": {"text": "thinking"}}),
                _tool_use("bash", {"command": "make test"}),
                "[AGENT_EXIT] 0",
            ]
        )

        actions = OpencodeLogReader().actions(log_text)

        assert [action.description for action in actions] == ["read · src/main.py", "bash · make test"]


@pytest.mark.integration
class TestOpencodeLogReaderVerdict:
    def test_should_declare_a_terminated_run_as_interrupted(self) -> None:
        verdict = OpencodeLogReader().verdict("working\n[AGENT_EXIT] 143\n", exit_code=143)

        assert (verdict.outcome.value, verdict.cause.value) == ("interrupted", "terminated")

    def test_should_declare_any_other_exit_as_failed_for_an_unknown_cause(self) -> None:
        verdict = OpencodeLogReader().verdict("working\n[AGENT_EXIT] 1\n", exit_code=1)

        assert (verdict.outcome.value, verdict.cause.value) == ("failed", "unknown")
