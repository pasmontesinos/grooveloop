from __future__ import annotations

import json

import pytest

from grooveloop.shared.infrastructure.claude_log_reader import ClaudeLogReader

_PAYLOAD = json.dumps(
    {
        "type": "result",
        "total_cost_usd": 0.42,
        "modelUsage": {"claude-opus-4": {"inputTokens": 10, "outputTokens": 20, "costUSD": 0.42}},
    }
)


@pytest.mark.integration
class TestClaudeLogReader:
    def test_should_declare_its_engine(self) -> None:
        assert ClaudeLogReader().engine == "claude"

    def test_should_read_the_cost_and_models_of_the_result_event_of_the_log(self) -> None:
        reading = ClaudeLogReader().read(f"{_PAYLOAD}\n[AGENT_EXIT] 0\n")

        assert reading.total_cost_usd == 0.42
        assert [(model.model, model.input_tokens, model.output_tokens) for model in reading.models] == [
            ("claude-opus-4", 10, 20)
        ]

    def test_should_read_no_metrics_when_the_log_has_no_result_event(self) -> None:
        reading = ClaudeLogReader().read("working\n")

        assert reading.total_cost_usd is None
        assert reading.models == []
        assert reading.cost_split is not None
        assert reading.cost_split.basis.value == "unavailable"

    def test_should_derive_the_cost_split_from_the_result_event(self) -> None:
        reading = ClaudeLogReader().read(f"{_PAYLOAD}\n[AGENT_EXIT] 0\n")

        assert reading.cost_split is not None
        assert reading.cost_split.basis.value == "derived"


_TOOL_USE = json.dumps(
    {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "thinking", "thinking": "…"},
                {"type": "tool_use", "name": "Bash", "input": {"description": "Run the tests"}},
            ]
        },
    }
)
_EARLIER_TOOL_USE = json.dumps(
    {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "src/main.py"}}]},
    }
)


@pytest.mark.integration
class TestClaudeLogReaderLastAction:
    def test_should_describe_the_last_tool_use_of_the_log(self) -> None:
        log_tail = f"{_EARLIER_TOOL_USE}\n{_TOOL_USE}\n"

        assert ClaudeLogReader().last_action(log_tail) == "Bash · Run the tests"

    def test_should_ignore_the_events_after_the_last_tool_use(self) -> None:
        log_tail = f"{_TOOL_USE}\n" + json.dumps({"type": "system", "subtype": "thinking_tokens"}) + "\n"

        assert ClaudeLogReader().last_action(log_tail) == "Bash · Run the tests"

    def test_should_not_describe_an_action_when_the_log_has_no_tool_use(self) -> None:
        assert ClaudeLogReader().last_action("working\n[AGENT_EXIT] 0\n") is None


@pytest.mark.integration
class TestClaudeLogReaderRunStats:
    def test_should_read_the_turns_subagents_skills_and_tools_of_the_full_log(self) -> None:
        result = json.dumps(
            {
                "type": "result",
                "total_cost_usd": 0.42,
                "num_turns": 2,
                "subagent_stats": {"spawned": 1},
                "modelUsage": {"claude-opus-4": {"inputTokens": 10, "outputTokens": 20, "costUSD": 0.42}},
            }
        )
        bash_call = json.dumps(
            {
                "type": "assistant",
                "message": {"id": "m1", "content": [{"type": "tool_use", "name": "Bash", "input": {}}]},
            }
        )
        skill_call = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "id": "m2",
                    "content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "brainstorming"}}],
                },
            }
        )
        log = f"{bash_call}\n{skill_call}\n{result}\n[AGENT_EXIT] 0\n"

        reading = ClaudeLogReader().read(log)

        assert reading.turns == 2
        assert reading.subagents == 1
        assert reading.skills == ["brainstorming"]
        assert {tool.name: tool.count for tool in reading.tools} == {"Bash": 1, "Skill": 1}


@pytest.mark.integration
class TestClaudeLogReaderTurnGrowth:
    def test_should_delegate_the_turn_growth_calculation(self) -> None:
        chunk = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "id": "m1",
                    "usage": {"input_tokens": 2, "cache_creation_input_tokens": 100},
                    "content": [{"type": "text", "text": "ok"}],
                },
            }
        )

        growth = ClaudeLogReader().turn_growth(chunk)

        assert [(turn.turn, turn.added_tokens) for turn in growth] == [(1, 102)]


def _assistant_tool_uses(*blocks: tuple[str, str, dict[str, str]]) -> str:
    return json.dumps(
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "Let me look at the code"},
                    *[
                        {"type": "tool_use", "id": tool_use_id, "name": name, "input": tool_input}
                        for tool_use_id, name, tool_input in blocks
                    ],
                ]
            },
        }
    )


@pytest.mark.integration
class TestClaudeLogReaderActions:
    def test_should_describe_each_tool_use_of_the_log_in_order(self) -> None:
        log_text = "\n".join(
            [
                _assistant_tool_uses(("toolu_1", "Read", {"file_path": "src/main.py"})),
                json.dumps({"type": "user", "message": {"content": [{"type": "tool_result"}]}}),
                _assistant_tool_uses(
                    ("toolu_2", "Bash", {"command": "make test"}), ("toolu_3", "Edit", {"file_path": "src/app.py"})
                ),
                "[AGENT_EXIT] 0",
            ]
        )

        actions = ClaudeLogReader().actions(log_text)

        assert [(action.tool_use_id, action.description) for action in actions] == [
            ("toolu_1", "Read · src/main.py"),
            ("toolu_2", "Bash · make test"),
            ("toolu_3", "Edit · src/app.py"),
        ]

    def test_should_describe_no_action_when_the_log_has_no_tool_use(self) -> None:
        assert ClaudeLogReader().actions("working\n[AGENT_EXIT] 0\n") == []


def _result(result: str, api_error_status: int | None = None) -> str:
    return json.dumps({"type": "result", "is_error": True, "api_error_status": api_error_status, "result": result})


def _api_retry(error: str, error_status: int | None) -> str:
    return json.dumps({"type": "system", "subtype": "api_retry", "error_status": error_status, "error": error})


@pytest.mark.integration
class TestClaudeLogReaderVerdict:
    def test_should_declare_an_overloaded_api_as_interrupted(self) -> None:
        log_tail = f"{_result('API Error: 529 Overloaded.', 529)}\n[AGENT_EXIT] 1\n"

        verdict = ClaudeLogReader().verdict(log_tail, exit_code=1)

        assert (verdict.outcome.value, verdict.cause.value) == ("interrupted", "overloaded")

    def test_should_declare_an_unreachable_api_as_an_interrupted_network(self) -> None:
        log_tail = _result("API Error: Can't reach the API server — check your internet or DNS (ENOTFOUND)")

        verdict = ClaudeLogReader().verdict(log_tail, exit_code=1)

        assert (verdict.outcome.value, verdict.cause.value) == ("interrupted", "network")

    def test_should_declare_a_lost_connection_as_an_interrupted_network(self) -> None:
        log_tail = _result("API Error: Connection closed mid-response. The response above may be incomplete.")

        verdict = ClaudeLogReader().verdict(log_tail, exit_code=1)

        assert (verdict.outcome.value, verdict.cause.value) == ("interrupted", "network")

    def test_should_declare_a_computer_gone_to_sleep_as_an_interrupted_network(self) -> None:
        log_tail = _result("API Error: Your computer went to sleep mid-response.")

        verdict = ClaudeLogReader().verdict(log_tail, exit_code=1)

        assert (verdict.outcome.value, verdict.cause.value) == ("interrupted", "network")

    def test_should_declare_a_server_error_as_interrupted(self) -> None:
        log_tail = _result("API Error: Server error mid-response.")

        verdict = ClaudeLogReader().verdict(log_tail, exit_code=1)

        assert (verdict.outcome.value, verdict.cause.value) == ("interrupted", "server_error")

    def test_should_declare_a_5xx_status_as_an_interrupted_server_error(self) -> None:
        log_tail = _result("API Error: 503", 503)

        verdict = ClaudeLogReader().verdict(log_tail, exit_code=1)

        assert (verdict.outcome.value, verdict.cause.value) == ("interrupted", "server_error")

    def test_should_declare_a_failed_authentication_as_failed(self) -> None:
        log_tail = _result("Failed to authenticate: OAuth session expired and could not be refreshed")

        verdict = ClaudeLogReader().verdict(log_tail, exit_code=1)

        assert (verdict.outcome.value, verdict.cause.value) == ("failed", "auth")

    def test_should_declare_a_run_killed_while_retrying_a_failed_authentication_as_failed(self) -> None:
        log_tail = f"{_api_retry('authentication_failed', 401)}\n[AGENT_EXIT] 143\n"

        verdict = ClaudeLogReader().verdict(log_tail, exit_code=143)

        assert (verdict.outcome.value, verdict.cause.value) == ("failed", "auth")

    def test_should_declare_a_session_limit_as_failed(self) -> None:
        log_tail = _result("You've hit your session limit · resets 1:40pm (Europe/Madrid)", 429)

        verdict = ClaudeLogReader().verdict(log_tail, exit_code=1)

        assert (verdict.outcome.value, verdict.cause.value) == ("failed", "rate_limit")

    def test_should_declare_an_unknown_error_as_failed(self) -> None:
        log_tail = _result("Something nobody has seen before")

        verdict = ClaudeLogReader().verdict(log_tail, exit_code=1)

        assert (verdict.outcome.value, verdict.cause.value) == ("failed", "unknown")

    def test_should_declare_a_terminated_run_as_interrupted(self) -> None:
        log_tail = f"{json.dumps({'type': 'assistant'})}\n[AGENT_EXIT] 143\n"

        verdict = ClaudeLogReader().verdict(log_tail, exit_code=143)

        assert (verdict.outcome.value, verdict.cause.value) == ("interrupted", "terminated")

    def test_should_declare_a_nonzero_exit_without_result_event_as_a_crash(self) -> None:
        log_tail = f"{json.dumps({'type': 'assistant'})}\n[AGENT_EXIT] 1\n"

        verdict = ClaudeLogReader().verdict(log_tail, exit_code=1)

        assert (verdict.outcome.value, verdict.cause.value) == ("interrupted", "crashed")

    def test_should_ignore_a_retry_the_run_recovered_from(self) -> None:
        log_tail = f"{_api_retry('overloaded', 529)}\n{json.dumps({'type': 'assistant'})}\n[AGENT_EXIT] 1\n"

        verdict = ClaudeLogReader().verdict(log_tail, exit_code=1)

        assert (verdict.outcome.value, verdict.cause.value) == ("interrupted", "crashed")

    def test_should_declare_a_run_killed_during_an_unrecognized_retry_as_terminated(self) -> None:
        log_tail = f"{_api_retry('unknown', None)}\n[AGENT_EXIT] 143\n"

        verdict = ClaudeLogReader().verdict(log_tail, exit_code=143)

        assert (verdict.outcome.value, verdict.cause.value) == ("interrupted", "terminated")

    def test_should_declare_a_run_dead_during_an_unrecognized_retry_as_a_crash(self) -> None:
        log_tail = f"{_api_retry('unknown', None)}\n[AGENT_EXIT] 1\n"

        verdict = ClaudeLogReader().verdict(log_tail, exit_code=1)

        assert (verdict.outcome.value, verdict.cause.value) == ("interrupted", "crashed")

    def test_should_not_read_a_cause_from_a_result_that_only_quotes_an_api_error(self) -> None:
        log_tail = _result("Done. The handler now survives an API Error: Connection closed mid-response.")

        verdict = ClaudeLogReader().verdict(log_tail, exit_code=1)

        assert (verdict.outcome.value, verdict.cause.value) == ("failed", "unknown")
