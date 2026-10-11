from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from grooveloop.shared.domain.loop_heartbeat import LoopHeartbeat
from grooveloop.shared.infrastructure.filesystem_loop_presence import FilesystemLoopPresence
from tests.playground.shared.infrastructure.clock import clock_at

if TYPE_CHECKING:
    from pathlib import Path

_T0 = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)


@pytest.mark.integration
class TestFilesystemLoopPresence:
    def test_should_write_the_heartbeat_under_the_repo_directory(self, tmp_path: Path) -> None:
        presence = FilesystemLoopPresence(repos_dir=tmp_path, clock=clock_at(_T0))

        presence.beat("acme/tooling")

        heartbeat = json.loads((tmp_path / "acme" / "tooling" / "heartbeat.json").read_text())
        assert heartbeat == {"pid": os.getpid(), "repo": "acme/tooling", "at": _T0.isoformat()}

    def test_should_move_the_heartbeat_instant_forward_on_every_beat(self, tmp_path: Path) -> None:
        clock = clock_at(_T0)
        presence = FilesystemLoopPresence(repos_dir=tmp_path, clock=clock)
        presence.beat("acme/tooling")

        clock.now.return_value = datetime(2026, 9, 2, 12, 0, 5, tzinfo=UTC)
        presence.beat("acme/tooling")

        heartbeat = json.loads((tmp_path / "acme" / "tooling" / "heartbeat.json").read_text())
        assert heartbeat["at"] == "2026-09-02T12:00:05+00:00"

    def test_should_keep_the_heartbeat_of_each_repo_in_its_own_directory(self, tmp_path: Path) -> None:
        presence = FilesystemLoopPresence(repos_dir=tmp_path, clock=clock_at(_T0))

        presence.beat("acme/tooling")
        presence.beat("acme/shop")

        assert json.loads((tmp_path / "acme" / "tooling" / "heartbeat.json").read_text())["repo"] == ("acme/tooling")
        assert json.loads((tmp_path / "acme" / "shop" / "heartbeat.json").read_text())["repo"] == ("acme/shop")

    def test_should_leave_no_partial_file_behind(self, tmp_path: Path) -> None:
        presence = FilesystemLoopPresence(repos_dir=tmp_path, clock=clock_at(_T0))

        presence.beat("acme/tooling")

        assert sorted(path.name for path in (tmp_path / "acme" / "tooling").iterdir()) == ["heartbeat.json"]

    def test_should_read_back_the_heartbeat_it_wrote(self, tmp_path: Path) -> None:
        presence = FilesystemLoopPresence(repos_dir=tmp_path, clock=clock_at(_T0))
        presence.beat("acme/tooling")

        assert presence.heartbeats() == [LoopHeartbeat(repo="acme/tooling", pid=os.getpid(), at=_T0)]

    def test_should_read_the_heartbeat_of_every_repo(self, tmp_path: Path) -> None:
        presence = FilesystemLoopPresence(repos_dir=tmp_path, clock=clock_at(_T0))
        presence.beat("acme/tooling")
        presence.beat("acme/shop")

        assert sorted(heartbeat.repo for heartbeat in presence.heartbeats()) == [
            "acme/shop",
            "acme/tooling",
        ]

    def test_should_read_no_heartbeat_when_the_directory_is_missing(self, tmp_path: Path) -> None:
        presence = FilesystemLoopPresence(repos_dir=tmp_path / "absent", clock=clock_at(_T0))

        assert presence.heartbeats() == []

    def test_should_skip_an_unreadable_heartbeat(self, tmp_path: Path) -> None:
        presence = FilesystemLoopPresence(repos_dir=tmp_path, clock=clock_at(_T0))
        presence.beat("acme/tooling")
        broken = tmp_path / "acme" / "shop"
        broken.mkdir(parents=True)
        (broken / "heartbeat.json").write_text("{not json")

        assert [heartbeat.repo for heartbeat in presence.heartbeats()] == ["acme/tooling"]

    def test_should_skip_a_heartbeat_without_its_fields(self, tmp_path: Path) -> None:
        presence = FilesystemLoopPresence(repos_dir=tmp_path, clock=clock_at(_T0))
        incomplete = tmp_path / "acme" / "shop"
        incomplete.mkdir(parents=True)
        (incomplete / "heartbeat.json").write_text('{"repo": "acme/shop"}')

        assert presence.heartbeats() == []

    def test_should_skip_a_heartbeat_whose_instant_has_no_time_zone(self, tmp_path: Path) -> None:
        presence = FilesystemLoopPresence(repos_dir=tmp_path, clock=clock_at(_T0))
        naive = tmp_path / "acme" / "shop"
        naive.mkdir(parents=True)
        (naive / "heartbeat.json").write_text('{"repo": "acme/shop", "pid": 1, "at": "2026-09-02T12:00:00"}')

        assert presence.heartbeats() == []
