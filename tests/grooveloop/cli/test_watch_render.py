from __future__ import annotations

import re
from dataclasses import replace
from io import StringIO
from typing import TYPE_CHECKING, Any

import pytest
from rich.console import Console, Group

from grooveloop.cli.watch_render import (
    OUTCOME_ICONS,
    STATUS_ICONS,
    LearningLine,
    ModelLine,
    RepoLinks,
    SessionLine,
    SessionTable,
    SliceLine,
    StoryLine,
    ToolTallyLine,
    column_widths,
    render,
    session_row,
    story_blocks,
)
from grooveloop.delivery.domain.slice_status import SliceStatus

if TYPE_CHECKING:
    from rich.text import Text

    from grooveloop.cli.watch_render import StoryBlock

_OSC8 = re.compile("\x1b]8;;.*?\x1b\\\\")


def _strip_osc8(text: str) -> str:
    return _OSC8.sub("", text)


def _plain(renderable: Any) -> str:
    buffer = StringIO()
    Console(file=buffer, width=200, color_system=None).print(renderable)

    return buffer.getvalue()


def _session(
    outcome: str = "done",
    task_type: str = "implement_slice",
    engine: str = "claude",
    elapsed_seconds: float = 83.0,
    run_id: str = "5cf547af-7d1e-4f1b-9d4e-3a0c1b2d4e5f",
    total_cost_usd: float | None = 0.1234,
    models: list[ModelLine] | None = None,
    launch_model: str | None = None,
    silent_seconds: float | None = None,
    last_action: str | None = None,
    turns: int | None = None,
    subagents: int | None = None,
    skills: list[str] | None = None,
    tools: list[ToolTallyLine] | None = None,
    cause: str | None = None,
) -> SessionLine:
    return SessionLine(
        outcome=outcome,
        task_type=task_type,
        engine=engine,
        elapsed_seconds=elapsed_seconds,
        run_id=run_id,
        total_cost_usd=total_cost_usd,
        models=models or [],
        launch_model=launch_model,
        silent_seconds=silent_seconds,
        last_action=last_action,
        turns=turns,
        subagents=subagents,
        skills=skills or [],
        tools=tools or [],
        cause=cause,
    )


def _tallied_session(task_type: str, turns: int, tools: int) -> SessionLine:
    return _session(
        outcome="done",
        task_type=task_type,
        turns=turns,
        subagents=0,
        tools=[ToolTallyLine("Bash", tools)],
    )


def _story_with(session: SessionLine) -> StoryLine:
    return StoryLine(
        number="49",
        title="watch panel",
        status="sliced",
        slices=[SliceLine("dispatched", "runner state", 1, sessions=[session])],
    )


def _truecolor(hex_color: str) -> str:
    red, green, blue = (int(hex_color[index : index + 2], 16) for index in (1, 3, 5))

    return f"38;2;{red};{green};{blue}m"


def _session_lines(output: str) -> list[str]:
    return [line for line in output.splitlines() if "⏱" in line]


def _session_cells(output: str) -> list[str]:
    return [" ".join(line.split()) for line in _session_lines(output)]


def _wip_story() -> StoryLine:
    return StoryLine(
        number="49",
        title="watch panel",
        status="sliced",
        slices=[
            SliceLine(status="merged", title="story tree", order=1, number="50"),
            SliceLine(status="dispatched", title="runner state", order=2, number="51"),
        ],
    )


def _done_story(number: str, title: str, silent_seconds: float | None) -> StoryLine:
    return StoryLine(
        number=number,
        title=title,
        status="sliced",
        slices=[
            SliceLine(
                status="merged",
                title="merged slice",
                order=1,
                number=f"{number}0",
                sessions=[_session(silent_seconds=silent_seconds)],
            ),
        ],
    )


class TestWatchRender:
    def test_should_return_a_string(self) -> None:
        output = render([_wip_story()])

        assert isinstance(output, str)

    def test_should_list_a_draft_story_as_live_work(self) -> None:
        draft = StoryLine(number="72", title="draft feature", status="draft", slices=[])

        output = render([draft])

        assert "draft feature" in output

    def test_should_not_list_the_stories_that_are_not_live_work(self) -> None:
        ready = StoryLine(number="72", title="ready feature", status="ready_for_implementation", slices=[])
        sliced = StoryLine(
            number="10", title="sliced feature", status="sliced", slices=[SliceLine("pending", "hidden slice", 1)]
        )
        done = StoryLine(number="29", title="done feature", status="done", slices=[])

        output = render([ready, sliced, done])

        assert "ready feature" not in output
        assert "sliced feature" not in output
        assert "done feature" not in output
        assert "hidden slice" not in output

    def test_should_expand_a_wip_story_into_its_slice_lines_with_titles(self) -> None:
        output = render([_wip_story()])

        assert "#49" in output
        assert "watch panel" in output
        assert "story tree" in output
        assert "runner state" in output

    def test_should_connect_the_wip_slices_with_tree_branches(self) -> None:
        output = render([_wip_story()])

        assert "├" in output
        assert "└" in output

    def test_should_not_draw_tree_branches_for_non_wip_phases(self) -> None:
        story = StoryLine(
            number="10", title="refactor parser", status="sliced", slices=[SliceLine("pending", "step one", 1)]
        )

        output = render([story])

        assert "├" not in output
        assert "└" not in output

    def test_should_show_the_github_status_icon_and_word_for_each_slice(self) -> None:
        output = render([_wip_story()])

        assert "● merged" in output
        assert "◔ dispatched" in output

    def test_should_show_an_icon_for_every_github_status(self) -> None:
        statuses = [status.value for status in SliceStatus]
        story = StoryLine(
            number="9",
            title="every state",
            status="sliced",
            slices=[SliceLine(status, status, order) for order, status in enumerate(statuses, start=1)],
        )

        output = render([story])

        for status in statuses:
            assert f" {status}" in output

    def test_should_render_the_running_session_with_its_duration_and_live_marker(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine(
                    "dispatched",
                    "runner state",
                    2,
                    sessions=[_session(outcome="running", elapsed_seconds=552.0, total_cost_usd=None)],
                ),
                SliceLine("merged", "story tree", 1),
            ],
        )

        output = render([story])
        session_line = _session_cells(output)[0]

        assert "▶" in session_line
        assert "LIVE" in session_line
        assert "⏱ 9m12s" in session_line

    def test_should_omit_the_session_line_when_the_slice_has_no_run(self) -> None:
        story = StoryLine(
            number="9",
            title="story",
            status="sliced",
            slices=[SliceLine("dispatched", "slice", 1), SliceLine("pending", "other", 2)],
        )

        output = render([story])

        assert _session_lines(output) == []

    def test_should_not_show_the_pull_request_number_on_any_run_line(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine(
                    "pr_open",
                    "runner state",
                    1,
                    pr_number="61",
                    sessions=[_session(task_type="implement_slice"), _session(task_type="review_slice")],
                ),
            ],
        )

        output = render([story])

        assert len(_session_lines(output)) == 2
        assert "#61" not in output

    def test_should_not_show_the_pull_request_number_when_the_slice_has_no_task(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[SliceLine("pr_open", "runner state", 1, pr_number="61")],
        )

        output = render([story])

        assert "#61" not in output

    def test_should_summarize_the_slice_statuses_in_the_story_header(self) -> None:
        output = render([_wip_story()])

        assert "WIP · 1 dispatched · 1 merged" in output
        assert "1/2" not in output
        assert "█" not in output

    def test_should_show_the_order_and_title_of_each_slice(self) -> None:
        output = render([_wip_story()])

        assert "1 · story tree" in output
        assert "2 · runner state" in output

    def test_should_render_session_metrics_on_their_own_line_under_the_slice(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine(
                    "pr_open",
                    "runner state",
                    1,
                    pr_number="61",
                    sessions=[_session(task_type="implement_slice", engine="claude", elapsed_seconds=12.0)],
                ),
            ],
        )

        output = render([story])
        slice_line = next(line for line in output.splitlines() if "runner state" in line)
        session_lines = _session_cells(output)

        assert "implement_slice" not in slice_line
        assert len(session_lines) == 1
        assert "implement_slice" in session_lines[0]
        assert "claude" in session_lines[0]
        assert "⏱ 12s" in session_lines[0]

    def test_should_not_render_a_session_line_for_a_slice_without_run(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[SliceLine("pending", "no run", 1)],
        )

        output = render([story])

        assert _session_lines(output) == []

    def test_should_show_the_aggregated_token_block_on_the_session_line(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine(
                    "pr_open",
                    "runner state",
                    1,
                    sessions=[
                        _session(
                            outcome="done",
                            elapsed_seconds=83.0,
                            total_cost_usd=4.8467555,
                            models=[ModelLine("claude-opus-5", 4.8467555, 96, 22898, 5652831, 144741)],
                        ),
                    ],
                ),
            ],
        )

        output = render([story])
        session_line = _session_cells(output)[0]

        assert "$4.8468" in session_line
        assert "↑5.8M 97.5% cached ↓22.9K" in session_line
        assert "claude-opus-5" not in session_line

    def test_should_count_a_missing_cache_write_only_in_the_cached_share(self) -> None:
        story = _story_with(_session(models=[ModelLine("qwen3-coder", 0.0, 120, 45, 30, 0)]))

        session_line = _session_cells(render([story]))[0]

        assert "↑150 20.0% cached ↓45" in session_line

    def test_should_show_no_cached_share_for_a_model_without_tokens(self) -> None:
        story = _story_with(_session(models=[ModelLine("claude-haiku", 0.0, 0, 0, 0, 0)]))

        session_line = _session_cells(render([story]))[0]

        assert "↑0 0.0% cached ↓0" in session_line

    def test_should_sum_every_model_into_a_single_token_block(self) -> None:
        story = _story_with(
            _session(
                models=[
                    ModelLine("claude-opus-5", 1.0, 100, 50, 900, 0),
                    ModelLine("claude-sonnet-5", 0.5, 0, 25, 1000, 0),
                ]
            )
        )

        session_line = _session_cells(render([story]))[0]

        assert "↑2.0K 95.0% cached ↓75" in session_line

    def test_should_show_a_pending_cost_while_the_session_is_in_flight(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine(
                    "dispatched",
                    "runner state",
                    1,
                    sessions=[_session(outcome="running", elapsed_seconds=12.0, total_cost_usd=None)],
                ),
            ],
        )

        output = render([story])
        session_line = _session_lines(output)[0]

        assert "—" in session_line
        assert "$0" not in session_line
        assert "LIVE" in session_line

    def test_should_format_session_elapsed_over_a_minute_as_minutes_and_seconds(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[SliceLine("dispatched", "runner state", 1, sessions=[_session(elapsed_seconds=83.0)])],
        )

        output = render([story])

        assert "⏱ 1m23s" in _session_cells(output)[0]

    def test_should_align_session_columns_globally_across_slices(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine(
                    "pr_open",
                    "short",
                    1,
                    sessions=[_session(task_type="address_review", elapsed_seconds=5.0)],
                ),
                SliceLine(
                    "pr_open",
                    "long",
                    2,
                    sessions=[_session(task_type="implement_slice", elapsed_seconds=3600.0)],
                ),
            ],
        )

        output = render([story])
        lines = _session_lines(output)

        assert lines[0].index("claude") == lines[1].index("claude")

    def test_should_show_the_launch_model_between_the_engine_and_the_elapsed(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine(
                    "pr_open",
                    "runner state",
                    1,
                    sessions=[_session(engine="claude", launch_model="opus", elapsed_seconds=12.0)],
                ),
            ],
        )

        output = render([story])
        session_line = _session_lines(output)[0]

        assert "opus" in session_line
        assert session_line.index("claude") < session_line.index("opus") < session_line.index("⏱")

    def test_should_align_the_launch_model_column_globally_across_slices(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine(
                    "pr_open",
                    "short",
                    1,
                    sessions=[_session(task_type="address_review", launch_model="opus", elapsed_seconds=5.0)],
                ),
                SliceLine(
                    "pr_open",
                    "long",
                    2,
                    sessions=[_session(task_type="implement_slice", launch_model="opus", elapsed_seconds=3600.0)],
                ),
            ],
        )

        output = render([story])
        lines = _session_lines(output)

        assert lines[0].index("⏱") == lines[1].index("⏱")

    def test_should_render_a_session_line_without_a_launch_model(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[SliceLine("pr_open", "runner state", 1, sessions=[_session(launch_model=None)])],
        )

        output = render([story])

        assert len(_session_lines(output)) == 1

    def test_should_dim_the_session_line_and_color_the_outcome_icon(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[SliceLine("pr_open", "runner state", 1, sessions=[_session(outcome="failed")])],
        )

        output = render([story], color=True)

        assert "\x1b[" in _session_lines(output)[0]

    def test_should_be_deterministic_for_the_same_input(self) -> None:
        story = _wip_story()

        assert render([story]) == render([story])

    def test_should_link_the_story_number_to_its_github_issue_when_links_are_enabled(self) -> None:
        output = render([_wip_story()], links=RepoLinks("acme/tooling"))

        assert "https://github.com/acme/tooling/issues/49" in output
        assert "\x1b]8" in output

    def test_should_link_the_slice_title_to_its_sub_issue_when_links_are_enabled(self) -> None:
        output = render([_wip_story()], links=RepoLinks("acme/tooling"))

        assert "https://github.com/acme/tooling/issues/50" in output

    def test_should_not_emit_any_osc8_escape_when_links_are_disabled(self) -> None:
        output = render([_wip_story()])

        assert "\x1b]8" not in output

    def test_should_keep_the_visible_text_identical_with_and_without_links(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine("merged", "story tree", 1, number="50"),
                SliceLine("pr_open", "runner state", 2, pr_number="61", number="51", sessions=[_session()]),
            ],
        )

        with_links = render([story], links=RepoLinks("acme/tooling"))
        without_links = render([story])

        assert _strip_osc8(with_links) == without_links

    def test_should_emit_ansi_color_for_a_failed_slice_in_color_mode(self) -> None:
        story = StoryLine(number="9", title="broken", status="sliced", slices=[SliceLine("failed", "broken slice", 1)])

        output = render([story], color=True)

        assert "\x1b[" in output

    def test_should_not_emit_any_ansi_color_in_plain_mode(self) -> None:
        story = StoryLine(number="9", title="broken", status="sliced", slices=[SliceLine("failed", "broken slice", 1)])

        output = render([story], color=False)

        assert "\x1b[" not in output

    def test_should_name_the_lesson_with_its_issue_number(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine("merged", "story tree", 1, number="50", learning=LearningLine(number="286")),
                SliceLine("pending", "runner state", 2, number="51"),
            ],
        )

        output = render([story], links=RepoLinks("acme/tooling"))
        learning_line = _strip_osc8(next(line for line in output.splitlines() if "lesson" in line))

        assert "✎ lesson #286" in learning_line
        assert "captured" in learning_line
        assert "https://github.com/acme/tooling/issues/286" in output

    def test_should_point_the_learning_subline_to_the_open_conventions_pull_request(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine(
                    "merged",
                    "story tree",
                    1,
                    number="50",
                    learning=LearningLine(number="286", status="learned", conventions_pr_number="101"),
                ),
                SliceLine("pending", "runner state", 2, number="51"),
            ],
        )

        output = render([story], links=RepoLinks("acme/tooling"))
        learning_line = _strip_osc8(next(line for line in output.splitlines() if "lesson" in line))

        assert "PR #101" in learning_line
        assert "learned" in learning_line
        assert "https://github.com/acme/tooling/pull/101" in output

    def test_should_mark_a_resolved_lesson_apart_from_a_pending_one(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine("merged", "story tree", 1, number="50", learning=LearningLine(number="286")),
                SliceLine(
                    "merged",
                    "runner state",
                    2,
                    number="51",
                    learning=LearningLine(number="287", status="discarded", resolved=True),
                ),
            ],
        )

        output = render([story])
        pending_line = next(line for line in output.splitlines() if "#286" in line)
        resolved_line = next(line for line in output.splitlines() if "#287" in line)

        assert "✎ lesson #286" in pending_line
        assert "✓ lesson #287" in resolved_line
        assert "discarded" in resolved_line

    def test_should_show_a_story_lesson_without_a_source_slice_under_the_story_tree(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine("merged", "story tree", 1, number="50"),
                SliceLine("pending", "runner state", 2, number="51"),
            ],
            lessons=[LearningLine(number="286")],
        )

        output = render([story], links=RepoLinks("acme/tooling"))
        learning_line = _strip_osc8(next(line for line in output.splitlines() if "lesson" in line))

        assert "✎ lesson #286" in learning_line
        assert "captured" in learning_line

    def test_should_show_the_learning_gate_reason_on_the_blocked_pending_slice(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine("merged", "story tree", 1, number="50", learning=LearningLine(number="286")),
                SliceLine("pending", "runner state", 2, number="51", blocked_by_order=1),
            ],
        )

        output = render([story])
        blocked_line = next(line for line in output.splitlines() if "runner state" in line)

        assert "⏸ blocked by the learning of slice 1" in blocked_line

    def test_should_count_the_pending_learning_slices_in_the_story_summary(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine("merged", "story tree", 1, number="50", learning=LearningLine(number="286")),
                SliceLine("pending", "runner state", 2, number="51", blocked_by_order=1),
            ],
        )

        output = render([story])

        assert "1 learning" in output

    def test_should_keep_an_all_merged_story_in_wip_while_a_lesson_is_pending(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine("merged", "story tree", 1, number="50", learning=LearningLine(number="286")),
                SliceLine("merged", "runner state", 2, number="51"),
            ],
        )

        output = render([story])

        assert "watch panel" in output

    def test_should_keep_an_all_merged_story_in_wip_while_a_story_lesson_is_pending(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine("merged", "story tree", 1, number="50"),
                SliceLine("merged", "runner state", 2, number="51"),
            ],
            lessons=[LearningLine(number="286")],
        )

        output = render([story])

        assert "watch panel" in output
        assert "1 learning" in output

    def test_should_move_an_all_merged_story_to_done_without_pending_lessons(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine("merged", "story tree", 1, number="50"),
                SliceLine("merged", "runner state", 2, number="51"),
            ],
        )

        output = render([story])

        assert "watch panel" not in output

    def test_should_count_the_resolved_learning_slices_apart_from_the_pending_ones(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine("merged", "story tree", 1, number="50", learning=LearningLine(number="286")),
                SliceLine(
                    "merged",
                    "runner state",
                    2,
                    number="51",
                    learning=LearningLine(number="287", status="learned", conventions_pr_number="101", resolved=True),
                ),
            ],
        )

        output = render([story])

        assert "1 learning" in output
        assert "1 learning ✓" in output

    def test_should_move_an_all_merged_story_to_done_when_every_lesson_is_resolved(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine(
                    "merged",
                    "story tree",
                    1,
                    number="50",
                    learning=LearningLine(number="286", status="learned", conventions_pr_number="101", resolved=True),
                ),
                SliceLine("merged", "runner state", 2, number="51"),
            ],
        )

        output = render([story])

        assert "watch panel" not in output


class TestLastDoneStory:
    def test_should_list_the_done_story_when_no_story_is_live(self) -> None:
        output = render([_done_story("49", "watch panel", silent_seconds=30.0)])

        assert "watch panel" in output

    def test_should_hide_the_done_story_while_another_story_waits_ready(self) -> None:
        ready = StoryLine(number="72", title="ready feature", status="ready_for_implementation", slices=[])

        output = render([_done_story("49", "watch panel", silent_seconds=30.0), ready])

        assert "watch panel" not in output

    def test_should_hide_the_done_story_while_another_story_is_sliced(self) -> None:
        sliced = StoryLine(
            number="72", title="sliced feature", status="sliced", slices=[SliceLine("pending", "first slice", 1)]
        )

        output = render([_done_story("49", "watch panel", silent_seconds=30.0), sliced])

        assert "watch panel" not in output

    def test_should_list_only_the_done_story_whose_agent_wrote_last(self) -> None:
        older = _done_story("90", "older story", silent_seconds=900.0)
        newer = _done_story("12", "newer story", silent_seconds=30.0)

        output = render([older, newer])

        assert "newer story" in output
        assert "older story" not in output

    def test_should_list_no_done_story_when_none_of_them_has_a_session(self) -> None:
        output = render([_done_story("49", "watch panel", silent_seconds=None)])

        assert "watch panel" not in output

    def test_should_name_the_done_phase_in_the_story_summary(self) -> None:
        output = render([_done_story("49", "watch panel", silent_seconds=30.0)])

        assert "Done · 1 merged" in output
        assert "WIP" not in output


class TestStallWarning:
    def test_should_mark_as_silent_a_running_session_whose_log_is_quiet_for_longer_than_the_threshold(self) -> None:
        story = _story_with(_session(outcome="running", total_cost_usd=None, silent_seconds=420.0))

        output = render([story], stall_after_seconds=300)

        assert "stalled 7m00s" in _session_lines(output)[0]

    def test_should_not_mark_as_silent_a_running_session_with_a_recent_event(self) -> None:
        story = _story_with(_session(outcome="running", total_cost_usd=None, silent_seconds=12.0))

        output = render([story], stall_after_seconds=300)

        assert "stalled" not in _session_lines(output)[0]

    def test_should_mark_every_running_session_as_silent_when_the_threshold_is_zero(self) -> None:
        story = _story_with(_session(outcome="running", total_cost_usd=None, silent_seconds=0.0))

        output = render([story], stall_after_seconds=0)

        assert "stalled" in _session_lines(output)[0]

    def test_should_not_mark_as_silent_a_terminal_session(self) -> None:
        story = _story_with(_session(outcome="done", silent_seconds=9_000.0))

        output = render([story], stall_after_seconds=300)

        assert "stalled" not in _session_lines(output)[0]

    def test_should_not_mark_as_silent_a_running_session_without_a_known_last_event(self) -> None:
        story = _story_with(_session(outcome="running", total_cost_usd=None, silent_seconds=None))

        output = render([story], stall_after_seconds=0)

        assert "stalled" not in _session_lines(output)[0]


class TestPalette:
    @pytest.mark.parametrize(
        ("status", "color"),
        [
            ("pending", "#6e7681"),
            ("dispatched", "#58a6ff"),
            ("under_review", "#58a6ff"),
            ("pr_open", "#e3b341"),
            ("changes_requested", "#58a6ff"),
            ("blocked", "#f85149"),
            ("merged", "#d2a8ff"),
            ("failed", "#f85149"),
        ],
    )
    def test_should_paint_each_slice_status_with_the_color_of_its_token(self, status: str, color: str) -> None:
        story = StoryLine(
            number="9",
            title="palette",
            status="sliced",
            slices=[SliceLine(status, "a slice", 1), SliceLine("dispatched", "another slice", 2)],
        )

        output = render([story], color=True)

        assert f"{_truecolor(color)}{STATUS_ICONS[status]} {status}" in output

    @pytest.mark.parametrize(
        ("outcome", "color"),
        [
            ("running", "#58a6ff"),
            ("done", "#3fb950"),
            ("interrupted", "#e3b341"),
            ("failed", "#f85149"),
            ("unstarted", "#6e7681"),
        ],
    )
    def test_should_paint_each_run_outcome_with_the_color_of_its_token(self, outcome: str, color: str) -> None:
        story = _story_with(_session(outcome=outcome, total_cost_usd=None))

        output = render([story], color=True)

        assert f"{_truecolor(color)}{OUTCOME_ICONS[outcome]}" in _session_lines(output)[0]


class TestFinishedSessionCause:
    def test_should_show_the_cause_of_a_session_that_did_not_succeed(self) -> None:
        story = _story_with(_session(outcome="interrupted", total_cost_usd=None, cause="overloaded"))

        line = _session_lines(render([story]))[0]

        assert "overloaded" in line


class TestUnstartedSession:
    def test_should_show_an_unstarted_session_as_not_started_instead_of_live(self) -> None:
        story = _story_with(_session(outcome="unstarted", total_cost_usd=None, silent_seconds=None))

        line = _session_lines(render([story]))[0]

        assert "not started" in line
        assert "LIVE" not in line
        assert "▶" not in line


class TestLastAction:
    def test_should_show_the_last_action_under_the_line_of_a_running_session(self) -> None:
        story = _story_with(_session(outcome="running", total_cost_usd=None, last_action="Bash · Run the tests"))

        output = render([story])

        lines = output.splitlines()
        session_index = lines.index(_session_lines(output)[0])

        assert "LIVE" in lines[session_index]
        assert "↳ Bash · Run the tests" in lines[session_index + 1]

    def test_should_not_add_a_line_when_the_session_has_no_last_action(self) -> None:
        story = _story_with(_session(outcome="running", total_cost_usd=None))

        output = render([story])

        assert "↳" not in output


class TestToolTallies:
    def test_should_show_the_tally_on_the_session_line_when_it_fits(self) -> None:
        story = _story_with(
            _session(
                outcome="done",
                turns=42,
                subagents=0,
                skills=["brainstorming", "testing", "code-review"],
                tools=[ToolTallyLine("Bash", 100), ToolTallyLine("Read", 18)],
            )
        )

        output = render([story])

        assert "Σ 42t 3sk 0sub 118tl" in _session_cells(output)[0]

    def test_should_not_add_a_tally_when_the_session_has_no_turns(self) -> None:
        story = _story_with(_session(outcome="running", total_cost_usd=None))

        output = render([story])

        assert "Σ" not in output

    def test_should_align_the_tally_across_sessions_of_different_slices(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine("pr_open", "short", 1, sessions=[_tallied_session("address_review", 23, 22)]),
                SliceLine("pr_open", "long", 2, sessions=[_tallied_session("implement_slice", 163, 207)]),
            ],
        )

        lines = _session_lines(render([story]))

        assert lines[0].index("Σ") == lines[1].index("Σ")

    def test_should_align_every_tally_counter_across_sessions_of_different_slices(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine("pr_open", "short", 1, sessions=[_tallied_session("implement_slice", 23, 22)]),
                SliceLine("pr_open", "long", 2, sessions=[_tallied_session("implement_slice", 163, 207)]),
            ],
        )

        lines = _session_lines(render([story]))

        assert lines[0].index("t ") == lines[1].index("t ")
        assert lines[0].index("tl") == lines[1].index("tl")

    def test_should_keep_the_model_and_hide_the_tool_count_in_a_panel_narrower_than_the_row(self) -> None:
        models = [ModelLine("claude-opus-5", 1.0, 100, 14600, 2600000, 0)]
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine(
                    "pr_open",
                    "runner state",
                    1,
                    sessions=[_session(launch_model="opus", turns=34, subagents=0, models=models)],
                ),
            ],
        )

        output = render([story], width=90)

        assert "opus" in output
        assert "tl" not in output

    def test_should_fit_the_session_rows_into_a_narrow_panel(self) -> None:
        story = _story_with(_tallied_session("implement_slice", 42, 118))

        output = render([story], width=70)

        assert all(len(line) <= 70 for line in output.splitlines())
        assert "Σ" in output


class TestStoryBlocks:
    def test_should_give_one_block_per_listed_story(self) -> None:
        ready = StoryLine(number="60", title="ready story", status="ready_for_implementation", slices=[])
        other = StoryLine(
            number="70", title="other panel", status="sliced", slices=[SliceLine("pr_open", "other", 1, number="71")]
        )

        blocks = story_blocks([_wip_story(), ready, other])

        assert [block.number for block in blocks] == ["49", "70"]

    def test_should_head_the_block_with_the_number_the_title_and_the_summary_of_the_story(self) -> None:
        header = story_blocks([_wip_story()])[0].header.plain

        assert header == "#49  watch panel   WIP · 1 dispatched · 1 merged"

    def test_should_leave_the_header_out_of_the_body_of_the_block(self) -> None:
        body = _plain(story_blocks([_wip_story()])[0].body)

        assert "watch panel" not in body
        assert "runner state" in body

    def test_should_link_the_number_in_the_header_to_the_issue_of_the_story(self) -> None:
        header = story_blocks([_wip_story()], links=RepoLinks("acme/tooling"))[0].header

        links = [span.style for span in header.spans if "link" in str(span.style)]
        assert links == ["link https://github.com/acme/tooling/issues/49"]


def _session_tables(block: StoryBlock) -> list[SessionTable]:
    return [
        part
        for node in block.body.children
        if isinstance(node.label, Group)
        for part in node.label.renderables
        if isinstance(part, SessionTable)
    ]


class TestSessionTable:
    def test_should_give_each_session_of_a_slice_a_row_of_the_table_under_the_slice(self) -> None:
        story = StoryLine(
            number="49",
            title="watch panel",
            status="sliced",
            slices=[
                SliceLine(
                    "pr_open",
                    "runner state",
                    1,
                    sessions=[_session(task_type="implement_slice"), _session(task_type="review_slice")],
                ),
                SliceLine("pending", "no run", 2),
            ],
        )

        tables = _session_tables(story_blocks([story])[0])

        assert [len(table.rows) for table in tables] == [2]

    def test_should_start_each_column_at_the_same_position_in_every_row_of_a_narrow_panel(self) -> None:
        rows = _runs_of_different_lengths()
        widths = column_widths(rows)

        lines = [_table_lines(SessionTable([row], widths), 60)[0] for row in rows]

        assert lines[0].index("⏱") == lines[1].index("⏱")
        assert lines[0].index("$") == lines[1].index("$")

    def test_should_show_every_column_of_the_runs_when_they_fit(self) -> None:
        rows = _runs_of_different_lengths()
        widths = column_widths(rows)

        lines = _table_lines(SessionTable(rows, widths), _full_width(widths))

        assert all("tl" in line and "cached" in line for line in lines)

    def test_should_hide_the_tool_count_of_every_row_first_when_the_runs_do_not_fit(self) -> None:
        rows = _runs_of_different_lengths()
        widths = column_widths(rows)

        lines = _table_lines(SessionTable(rows, widths), _full_width(widths) - 1)

        assert all("tl" not in line and "cached" in line for line in lines)

    def test_should_hide_the_token_block_of_every_row_before_the_duration(self) -> None:
        rows = _runs_of_different_lengths()
        widths = column_widths(rows)

        lines = _table_lines(SessionTable(rows, widths), 50)

        assert all("↑" not in line and "↓" not in line and "⏱" in line for line in lines)
        assert all(len(line) <= 50 for line in lines)


def _runs_of_different_lengths() -> list[list[Text]]:
    models = [ModelLine("claude-opus-5", 1.0, 100, 14600, 2600000, 0)]
    sessions = [
        _session(task_type="implement_slice", launch_model="opus", turns=163, subagents=2, models=models),
        replace(_tallied_session("review_slice", 3, 7), models=models, elapsed_seconds=4000.0),
    ]

    return [session_row(session, 300) for session in sessions]


def _full_width(widths: list[int]) -> int:
    shown = [width for width in widths if width > 0]

    return sum(shown) + len(shown) - 1


def _table_lines(table: SessionTable, width: int) -> list[str]:
    buffer = StringIO()
    Console(file=buffer, width=width, color_system=None).print(table)

    return buffer.getvalue().rstrip("\n").split("\n")
