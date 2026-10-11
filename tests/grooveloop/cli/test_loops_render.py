from __future__ import annotations

from io import StringIO

import pytest
from rich.console import Console, Group

from grooveloop.cli.loops_render import COLUMN_WIDTH, alive_prompt, idle_heading, idle_prompt, title
from grooveloop.shared.application.queries.list_loops import ActivityDTO, LoopDTO, SignalDTO, TickDTO


def _render(loops: list[LoopDTO], color: bool, selected: str | None = None) -> str:
    alive = [loop for loop in loops if loop.alive]
    idle = [loop for loop in loops if not loop.alive]
    prompts = [title(len(alive))]
    prompts.extend(alive_prompt(loop, selected=loop.repo == selected) for loop in alive)
    if len(idle) > 0:
        prompts.append(idle_heading())
        prompts.extend(idle_prompt(loop) for loop in idle)

    buffer = StringIO()
    Console(
        file=buffer,
        force_terminal=True,
        color_system="truecolor" if color else None,
        width=COLUMN_WIDTH,
        highlight=False,
        emoji=False,
    ).print(Group(*prompts))

    return buffer.getvalue()


def _alive(
    repo: str,
    age_seconds: int = 3,
    tick: TickDTO | None = None,
    signals: list[SignalDTO] | None = None,
    activity: ActivityDTO | None = None,
) -> LoopDTO:
    return LoopDTO(
        repo=repo,
        alive=True,
        age_seconds=age_seconds,
        tick=tick,
        signals=signals or [],
        activity=activity,
    )


def _broken(kind: str, reference: str | None = None) -> SignalDTO:
    return SignalDTO(kind=kind, category="broken", reference=reference)


def _waiting(kind: str, reference: str | None = None) -> SignalDTO:
    return SignalDTO(kind=kind, category="waiting", reference=reference)


def _idle(repo: str, age_seconds: int) -> LoopDTO:
    return LoopDTO(repo=repo, alive=False, age_seconds=age_seconds)


def _lines(output: str) -> list[str]:
    return [line.rstrip() for line in output.splitlines()]


def _line_with(output: str, needle: str) -> str:
    return next(line for line in _lines(output) if needle in line)


def _idle_block(output: str) -> list[str]:
    lines = _lines(output)

    return lines[lines.index("NO LOOP") + 1 :]


class TestLoopsRender:
    def test_should_name_every_alive_loop_by_its_repo_alone(self) -> None:
        output = _render([_alive("acme/shop"), _alive("acme/tooling")], color=False)

        assert _line_with(output, "acme/shop").strip() == "acme/shop"
        assert _line_with(output, "acme/tooling").strip() == "acme/tooling"

    @pytest.mark.parametrize(
        ("loops", "count"),
        [
            ([_alive("a/one"), _alive("b/two"), _alive("c/three")], "3 alive"),
            ([_alive("a/one")], "1 alive"),
            ([_idle("a/one", age_seconds=90)], "0 alive"),
        ],
    )
    def test_should_count_the_alive_loops_in_the_header(self, loops: list[LoopDTO], count: str) -> None:
        header = _lines(_render(loops, color=False))[0]

        assert header.startswith("LOOPS")
        assert header.endswith(count)

    def test_should_list_an_idle_loop_under_its_own_heading(self) -> None:
        output = _render([_alive("a/one"), _idle("b/two", age_seconds=2820)], color=False)

        assert "b/two" not in _line_with(output, "a/one")
        assert _idle_block(output)[0].strip().startswith("b/two")

    def test_should_omit_the_idle_heading_when_every_loop_is_alive(self) -> None:
        assert "NO LOOP" not in _render([_alive("a/one")], color=False)

    @pytest.mark.parametrize(("age_seconds", "age"), [(42, "42s ago"), (2820, "47m ago"), (10800, "3h ago")])
    def test_should_print_the_age_of_an_idle_loop(self, age_seconds: int, age: str) -> None:
        assert _idle_block(_render([_idle("b/two", age_seconds=age_seconds)], color=False))[0].endswith(age)

    def test_should_keep_the_escape_codes_out_when_color_is_off(self) -> None:
        assert "\x1b[" not in _render([_alive("a/one"), _idle("b/two", age_seconds=90)], color=False)

    def test_should_paint_the_escape_codes_when_color_is_on(self) -> None:
        assert "\x1b[" in _render([_alive("a/one")], color=True)

    def test_should_cut_a_long_alive_name_down_to_its_own_line(self) -> None:
        output = _render([_alive("some-very-long-organization-name/a-really-long-repository-name")], color=False)
        line = _line_with(output, "some-very-long")

        assert line.strip().startswith("some-very-long-organization-name/")
        assert line.endswith("…")

    def test_should_show_the_outcome_the_age_and_the_duration_of_the_last_tick(self) -> None:
        loop = _alive("acme/tooling", tick=TickDTO(outcome="ok", age_seconds=60, duration_seconds=38))

        output = _render([loop], color=False)

        assert _line_with(output, "tick ok").strip() == "tick ok · 1m ago · 38s"

    def test_should_shout_the_outcome_of_a_failed_tick(self) -> None:
        loop = _alive("acme/shop", tick=TickDTO(outcome="failed", age_seconds=120, duration_seconds=41))

        output = _render([loop], color=False)

        assert _line_with(output, "tick").strip() == "tick FAILED · 2m ago · 41s"

    def test_should_announce_the_first_tick_when_the_loop_has_no_snapshot(self) -> None:
        output = _render([_alive("acme/catalog")], color=False)

        assert _line_with(output, "first tick").strip() == "first tick running…"

    def test_should_align_the_tick_line_under_the_name_of_its_repo(self) -> None:
        output = _render(
            [
                _alive("acme/shop", tick=TickDTO(outcome="ok", age_seconds=1, duration_seconds=2)),
                _alive("acme/tooling"),
            ],
            color=False,
        )

        lines = _lines(output)
        assert lines[lines.index(_line_with(output, "acme/shop")) + 1].startswith("  tick ok")
        assert lines[lines.index(_line_with(output, "acme/tooling")) + 1].startswith("  first tick")

    def test_should_not_show_any_tick_line_for_a_loop_that_is_not_running(self) -> None:
        output = _render([_idle("acme/checkout", age_seconds=2820)], color=False)

        assert "first tick" not in output
        assert "tick ok" not in output

    def test_should_print_a_long_tick_duration_in_minutes(self) -> None:
        loop = _alive("acme/tooling", tick=TickDTO(outcome="ok", age_seconds=1, duration_seconds=98))

        output = _render([loop], color=False)

        assert _line_with(output, "tick ok").strip() == "tick ok · 1s ago · 1m38s"

    def test_should_paint_a_failed_tick_with_the_error_color(self) -> None:
        loop = _alive("acme/shop", tick=TickDTO(outcome="failed", age_seconds=1, duration_seconds=2))

        assert "\x1b[38;2;248;81;73m" in _render([loop], color=True)

    def test_should_mark_the_selected_loop_with_the_active_arrow(self) -> None:
        output = _render([_alive("a/one"), _alive("b/two")], color=False, selected="b/two")

        assert _line_with(output, "b/two").startswith("▶ b/two")
        assert _line_with(output, "a/one").startswith("  a/one")

    def test_should_mark_no_loop_when_nothing_is_selected(self) -> None:
        output = _render([_alive("a/one")], color=False)

        assert "▶" not in output

    def test_should_show_a_waiting_pull_request_with_its_own_number(self) -> None:
        loop = _alive("acme/tooling", signals=[_waiting("pull_request_waiting", "342")])

        output = _render([loop], color=False)

        assert _line_with(output, "awaits review").strip() == "⏳ PR #342 awaits review"

    def test_should_show_a_failed_slice_with_its_own_number(self) -> None:
        loop = _alive("acme/shop", signals=[_broken("failed_slice", "88")])

        output = _render([loop], color=False)

        assert _line_with(output, "in failed").strip() == "⛔ slice #88 in failed"

    @pytest.mark.parametrize(
        ("signal", "line"),
        [
            (_broken("failed_tick"), "⛔ the tick fails"),
            (_broken("stale_snapshot"), "⛔ the snapshot is not refreshing"),
            (_waiting("blocking_lesson", "351"), "⏳ slice #351 blocked by a lesson"),
            (_waiting("blocked_slice", "371"), "⏳ slice #371 awaits a decision"),
        ],
    )
    def test_should_word_every_signal_of_the_block(self, signal: SignalDTO, line: str) -> None:
        output = _render([_alive("a/one", signals=[signal])], color=False)

        assert _line_with(output, line.split(" ", 1)[1]).strip() == line

    def test_should_keep_a_quiet_block_down_to_its_two_header_lines(self) -> None:
        output = _render(
            [_alive("a/one", tick=TickDTO(outcome="ok", age_seconds=1, duration_seconds=2))],
            color=False,
        )
        lines = _lines(output)
        first = lines.index(_line_with(output, "a/one"))

        assert lines[first + 1].strip() == "tick ok · 1s ago · 2s"
        assert len(lines) == first + 2

    def test_should_close_a_long_list_of_signals_with_the_rest_count(self) -> None:
        loop = _alive(
            "acme/shop",
            signals=[
                _broken("failed_tick"),
                _broken("failed_slice", "88"),
                _broken("failed_slice", "89"),
                _broken("failed_slice", "90"),
                _waiting("pull_request_waiting", "342"),
                _waiting("pull_request_waiting", "343"),
            ],
        )

        output = _render([loop], color=False)

        assert len([line for line in _lines(output) if "⛔" in line or "⏳" in line]) == 4
        assert _line_with(output, "more").strip() == "+2 more"

    def test_should_align_every_signal_under_the_name_of_its_repo(self) -> None:
        loop = _alive("a/one", signals=[_broken("failed_tick")])

        output = _render([loop], color=False)

        assert _line_with(output, "the tick fails").startswith("  ⛔")

    def test_should_paint_a_broken_signal_with_the_error_color(self) -> None:
        assert "\x1b[38;2;248;81;73m" in _render([_alive("a/one", signals=[_broken("failed_tick")])], color=True)

    def test_should_not_show_any_signal_of_a_loop_that_is_not_running(self) -> None:
        idle = LoopDTO(
            repo="acme/checkout",
            alive=False,
            age_seconds=2820,
            signals=[_broken("failed_tick")],
        )

        assert "the tick fails" not in _render([idle], color=False)

    def test_should_show_the_count_the_time_and_the_cost_of_the_running_agents(self) -> None:
        loop = _alive("acme/tooling", activity=ActivityDTO(running=1, elapsed_seconds=240.0, cost_usd=0.82))

        output = _render([loop], color=False)

        assert _line_with(output, "agent").strip() == "\u25b6 1 agent \u00b7 4m00s \u00b7 $0.82"

    def test_should_pluralise_the_activity_line_with_more_than_one_agent(self) -> None:
        loop = _alive("acme/tooling", activity=ActivityDTO(running=3, elapsed_seconds=61.0, cost_usd=1.5))

        output = _render([loop], color=False)

        assert _line_with(output, "agents").strip() == "\u25b6 3 agents \u00b7 1m01s \u00b7 $1.50"

    def test_should_leave_the_activity_line_out_when_nothing_is_running(self) -> None:
        assert "agent" not in _render([_alive("acme/tooling")], color=False)

    def test_should_put_the_activity_line_between_the_tick_and_the_signals(self) -> None:
        loop = _alive(
            "acme/tooling",
            tick=TickDTO(outcome="ok", age_seconds=1, duration_seconds=2),
            signals=[_waiting("pull_request_waiting", "342")],
            activity=ActivityDTO(running=1, elapsed_seconds=10.0, cost_usd=0.0),
        )

        output = _render([loop], color=False)
        lines = _lines(output)
        first = lines.index(_line_with(output, "acme/tooling"))

        assert lines[first + 1].strip().startswith("tick ok")
        assert lines[first + 2].strip() == "\u25b6 1 agent \u00b7 10s \u00b7 $0.00"
        assert lines[first + 3].strip() == "\u23f3 PR #342 awaits review"

    def test_should_show_a_silent_agent_with_the_number_of_its_slice(self) -> None:
        loop = _alive("acme/tooling", signals=[_broken("silent_agent", "351")])

        output = _render([loop], color=False)

        assert _line_with(output, "is silent").strip() == "\u26d4 agent of #351 is silent"
