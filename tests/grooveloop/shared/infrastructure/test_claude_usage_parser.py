from __future__ import annotations

import json

from hypothesis import given
from hypothesis import strategies as st

from grooveloop.shared.domain.model_usage import ModelUsage
from grooveloop.shared.infrastructure.claude_usage_parser import load_result_event, parse_usage

_RESULT = json.dumps(
    {
        "type": "result",
        "subtype": "success",
        "total_cost_usd": 0.1234,
        "modelUsage": {
            "claude-opus-4-20250101": {
                "inputTokens": 100,
                "outputTokens": 200,
                "cacheReadInputTokens": 50,
                "cacheCreationInputTokens": 10,
                "costUSD": 0.1,
            }
        },
    }
)


class TestParseUsage:
    def test_extracts_total_cost_and_model_breakdown_from_the_result_event(self) -> None:
        total_cost_usd, models = parse_usage(f"{_RESULT}\n[AGENT_EXIT] 0\n")

        assert total_cost_usd == 0.1234
        assert models == [
            ModelUsage(
                model="claude-opus-4-20250101",
                input_tokens=100,
                output_tokens=200,
                cache_read_tokens=50,
                cache_creation_tokens=10,
                cost_usd=0.1,
            )
        ]

    def test_ignores_intermediate_events_that_precede_the_result(self) -> None:
        events = "\n".join(
            [
                json.dumps({"type": "system", "subtype": "init", "session_id": "s-1"}),
                json.dumps({"type": "assistant", "message": {"usage": {"input_tokens": 9}}}),
                _RESULT,
            ]
        )

        assert parse_usage(f"{events}\n[AGENT_EXIT] 0\n")[0] == 0.1234

    def test_returns_empty_when_the_log_has_no_result_event(self) -> None:
        events = "\n".join(
            [
                json.dumps({"type": "system", "subtype": "init"}),
                json.dumps({"type": "assistant", "total_cost_usd": 9.99}),
            ]
        )

        assert parse_usage(f"{events}\n") == (None, [])

    def test_returns_empty_when_the_log_has_no_json(self) -> None:
        assert parse_usage("working on it\n[AGENT_EXIT] 0\n") == (None, [])

    def test_returns_empty_when_the_result_event_is_malformed(self) -> None:
        assert parse_usage('{"type": "result", "total_cost_usd": 0.1, oops\n[AGENT_EXIT] 0\n') == (None, [])

    def test_is_defensive_about_missing_keys_in_a_model_entry(self) -> None:
        log = json.dumps({"type": "result", "total_cost_usd": 0.5, "modelUsage": {"claude-haiku": {"costUSD": 0.5}}})

        total_cost_usd, models = parse_usage(log)

        assert total_cost_usd == 0.5
        assert models == [
            ModelUsage(
                model="claude-haiku",
                input_tokens=0,
                output_tokens=0,
                cache_read_tokens=0,
                cache_creation_tokens=0,
                cost_usd=0.5,
            )
        ]

    def test_returns_cost_with_empty_models_when_model_usage_is_absent(self) -> None:
        assert parse_usage(json.dumps({"type": "result", "total_cost_usd": 0.2})) == (0.2, [])


_noise_lines = st.lists(st.text(alphabet=st.characters(exclude_categories=("Cc", "Zl", "Zp"), exclude_characters="{")))
_events = st.lists(st.sampled_from(["system", "assistant", "user"]).map(lambda kind: json.dumps({"type": kind})))


class TestLoadResultEventProperties:
    @given(log_text=st.text())
    def test_returns_nothing_or_a_result_event_for_any_text(self, log_text: str) -> None:
        event = load_result_event(log_text)

        assert event is None or event["type"] == "result"

    @given(before=_noise_lines, after=_events, exit_code=st.integers(min_value=0, max_value=255))
    def test_finds_the_result_event_behind_later_events_and_the_exit_marker(
        self, before: list[str], after: list[str], exit_code: int
    ) -> None:
        log_text = "\n".join([*before, _RESULT, *after, f"[AGENT_EXIT] {exit_code}"])

        assert load_result_event(log_text) == json.loads(_RESULT)

    @given(
        first_cost=st.floats(allow_nan=False, allow_infinity=False),
        last_cost=st.floats(allow_nan=False, allow_infinity=False),
    )
    def test_returns_the_last_result_event_of_the_log(self, first_cost: float, last_cost: float) -> None:
        results = [json.dumps({"type": "result", "total_cost_usd": cost}) for cost in [first_cost, last_cost]]

        assert load_result_event("\n".join(results)) == {"type": "result", "total_cost_usd": last_cost}

    @given(lines=st.lists(st.one_of(_noise_lines.map("\n".join), _events.map("\n".join))))
    def test_returns_nothing_without_a_result_event(self, lines: list[str]) -> None:
        assert load_result_event("\n".join(lines)) is None
