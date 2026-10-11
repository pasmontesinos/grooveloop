from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from grooveloop.bootstrap import container
from grooveloop.cli import watch_command
from grooveloop.delivery.domain.agent_session_repository import AgentSessionRepository
from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.domain.loop_heartbeat import LoopHeartbeat
from grooveloop.shared.domain.loop_presence import LoopPresence
from grooveloop.shared.domain.loop_snapshot import LoopSnapshot
from grooveloop.shared.domain.loop_snapshots import LoopSnapshots
from grooveloop.shared.domain.process_liveness import ProcessLiveness
from grooveloop.shared.domain.snapshot_slice import SnapshotSlice
from grooveloop.shared.domain.snapshot_slice_status import SnapshotSliceStatus
from grooveloop.shared.domain.snapshot_story import SnapshotStory
from grooveloop.shared.domain.snapshot_story_status import SnapshotStoryStatus
from grooveloop.shared.domain.snapshot_tick import SnapshotTick
from grooveloop.shared.domain.tick_outcome import TickOutcome
from tests.playground.shared.infrastructure.clock import clock_at
from tests.playground.shared.infrastructure.fake_agent_session_repository import FakeAgentSessionRepository
from tests.playground.shared.infrastructure.fake_loop_presence import FakeLoopPresence
from tests.playground.shared.infrastructure.fake_loop_snapshots import FakeLoopSnapshots
from tests.playground.shared.infrastructure.fake_process_liveness import FakeProcessLiveness

if TYPE_CHECKING:
    from pathlib import Path

_NOW = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def one_alive_loop() -> Any:
    snapshots = FakeLoopSnapshots(
        [
            LoopSnapshot(
                repo="verify/alfa",
                tick=SnapshotTick(outcome=TickOutcome.OK, at=_NOW, duration_seconds=38, interval_seconds=600),
                stories=[
                    SnapshotStory(
                        number="338",
                        status=SnapshotStoryStatus.SLICED,
                        title="Alfa story",
                        slices=[
                            SnapshotSlice(
                                number="350", status=SnapshotSliceStatus.PR_OPEN, title="Alfa slice", pr_number=None
                            )
                        ],
                        lessons=[],
                    )
                ],
            )
        ]
    )
    with (
        container.override(
            LoopPresence, FakeLoopPresence([LoopHeartbeat(repo="verify/alfa", pid=100, at=_NOW - timedelta(seconds=2))])
        ),
        container.override(ProcessLiveness, FakeProcessLiveness([100])),
        container.override(LoopSnapshots, snapshots),
        container.override(AgentSessionRepository, FakeAgentSessionRepository({})),
        container.override(Clock, clock_at(_NOW)),
    ):
        yield snapshots


@pytest.mark.entrypoint
class TestWatchCommand:
    def test_should_refuse_to_watch_without_an_interactive_terminal(
        self, one_alive_loop: Any, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exit_code = watch_command.run()

        captured = capsys.readouterr()
        assert exit_code == 2
        assert captured.out == ""
        assert captured.err == "watch needs an interactive terminal\n"

    def test_should_open_the_textual_app_on_an_interactive_terminal(self, one_alive_loop: Any) -> None:
        with (
            patch.object(watch_command, "has_terminal", return_value=True),
            patch.object(watch_command, "LoopsApp") as loops_app,
        ):
            loops_app.return_value.run.return_value = 0
            exit_code = watch_command.run(interval=3, stall_after=42)

        assert exit_code == 0
        assert loops_app.call_args.args[1] is one_alive_loop
        assert loops_app.call_args.kwargs == {"interval": 3, "stall_after": 42}

    def test_should_save_a_screenshot_without_an_interactive_terminal(
        self, one_alive_loop: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        screenshot = tmp_path / "watch.svg"

        exit_code = watch_command.run(screenshot=str(screenshot))

        svg = screenshot.read_text(encoding="utf-8")
        assert exit_code == 0
        assert capsys.readouterr().err == ""
        assert svg.startswith("<svg")
        assert "verify/alfa" in svg
        assert "Alfa&#160;slice" in svg

    def test_should_paint_the_screenshot_with_the_background_of_the_palette(
        self, one_alive_loop: Any, tmp_path: Path
    ) -> None:
        screenshot = tmp_path / "watch.svg"

        watch_command.run(screenshot=str(screenshot))

        assert "#0f1419" in screenshot.read_text(encoding="utf-8").lower()

    def test_should_start_the_app_with_the_theme_of_the_palette_active(self, one_alive_loop: Any) -> None:
        with (
            patch.object(watch_command, "has_terminal", return_value=True),
            patch.object(watch_command, "LoopsApp") as loops_app,
        ):
            loops_app.return_value.run.return_value = 0
            watch_command.run()

        app = loops_app.return_value
        registered = app.register_theme.call_args.args[0]
        assert registered.background == "#0f1419"
        assert app.theme == registered.name

    def test_should_capture_a_fixed_screen_size(self, one_alive_loop: Any, tmp_path: Path) -> None:
        first = tmp_path / "first.svg"
        second = tmp_path / "second.svg"

        watch_command.run(screenshot=str(first))
        watch_command.run(screenshot=str(second))

        assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")
