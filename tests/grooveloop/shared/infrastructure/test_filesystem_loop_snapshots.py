from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from grooveloop.shared.domain.loop_snapshot import LoopSnapshot
from grooveloop.shared.domain.snapshot_lesson import SnapshotLesson
from grooveloop.shared.domain.snapshot_lesson_status import SnapshotLessonStatus
from grooveloop.shared.domain.snapshot_mergeability import SnapshotMergeability
from grooveloop.shared.domain.snapshot_pull_request import SnapshotPullRequest
from grooveloop.shared.domain.snapshot_slice import SnapshotSlice
from grooveloop.shared.domain.snapshot_slice_status import SnapshotSliceStatus
from grooveloop.shared.domain.snapshot_story import SnapshotStory
from grooveloop.shared.domain.snapshot_story_status import SnapshotStoryStatus
from grooveloop.shared.domain.snapshot_tick import SnapshotTick
from grooveloop.shared.domain.tick_outcome import TickOutcome
from grooveloop.shared.infrastructure.filesystem_loop_snapshots import FilesystemLoopSnapshots

if TYPE_CHECKING:
    from pathlib import Path

_T0 = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)


def _snapshot(outcome: TickOutcome = TickOutcome.OK, duration_seconds: int = 38) -> LoopSnapshot:
    return LoopSnapshot(
        repo="acme/tooling",
        tick=SnapshotTick(outcome=outcome, at=_T0, duration_seconds=duration_seconds, interval_seconds=600),
        stories=[
            SnapshotStory(
                number="348",
                status=SnapshotStoryStatus.SLICED,
                title="Panel multirepo",
                slices=[
                    SnapshotSlice(
                        number="351",
                        status=SnapshotSliceStatus.PR_OPEN,
                        title="The snapshot",
                        pr_number="360",
                        depends_on=["349", "350"],
                        pull_request=SnapshotPullRequest(
                            title="The snapshot",
                            additions=180,
                            deletions=22,
                            changed_files=7,
                            updated_at=_T0,
                            head_ref_oid="abc123",
                            mergeable=SnapshotMergeability.MERGEABLE,
                            checks="success",
                        ),
                    ),
                    SnapshotSlice(number="352", status=SnapshotSliceStatus.PENDING, title="The panel", pr_number=None),
                ],
                lessons=[
                    SnapshotLesson(
                        number="191",
                        source_pull_request_number=190,
                        status=SnapshotLessonStatus.LEARNED,
                        conventions_pull_request_number=192,
                        resolved=False,
                    )
                ],
            )
        ],
    )


@pytest.mark.integration
class TestFilesystemLoopSnapshots:
    def test_should_write_the_snapshot_under_the_repo_directory(self, tmp_path: Path) -> None:
        snapshots = FilesystemLoopSnapshots(repos_dir=tmp_path)

        snapshots.publish(_snapshot())

        stored = json.loads((tmp_path / "acme" / "tooling" / "snapshot.json").read_text())
        assert stored["repo"] == "acme/tooling"
        assert stored["tick"] == {
            "outcome": "ok",
            "at": _T0.isoformat(),
            "duration_seconds": 38,
            "interval_seconds": 600,
        }
        assert stored["stories"][0]["slices"][0]["pr_number"] == "360"
        assert stored["stories"][0]["slices"][0]["depends_on"] == ["349", "350"]
        assert stored["stories"][0]["slices"][0]["pull_request"] == {
            "title": "The snapshot",
            "additions": 180,
            "deletions": 22,
            "changed_files": 7,
            "updated_at": "2026-09-02T12:00:00+00:00",
            "head_ref_oid": "abc123",
            "mergeable": "mergeable",
            "checks": "success",
        }
        assert stored["stories"][0]["slices"][1]["pull_request"] is None
        assert stored["stories"][0]["lessons"][0]["source_pull_request_number"] == 190

    def test_should_write_every_status_as_its_plain_string(self, tmp_path: Path) -> None:
        snapshots = FilesystemLoopSnapshots(repos_dir=tmp_path)

        snapshots.publish(_snapshot())

        story = json.loads((tmp_path / "acme" / "tooling" / "snapshot.json").read_text())["stories"][0]
        assert story["status"] == "sliced"
        assert [a_slice["status"] for a_slice in story["slices"]] == ["pr_open", "pending"]
        assert story["lessons"][0]["status"] == "learned"

    def test_should_read_back_the_snapshot_it_wrote(self, tmp_path: Path) -> None:
        snapshots = FilesystemLoopSnapshots(repos_dir=tmp_path)
        snapshots.publish(_snapshot())

        assert snapshots.find("acme/tooling") == _snapshot()

    def test_should_read_a_slice_written_without_dependencies_as_having_none(self, tmp_path: Path) -> None:
        repo_dir = tmp_path / "acme" / "tooling"
        repo_dir.mkdir(parents=True)
        (repo_dir / "snapshot.json").write_text(
            '{"repo": "acme/tooling",'
            ' "tick": {"outcome": "ok", "at": "2026-09-02T12:00:00+00:00",'
            ' "duration_seconds": 1, "interval_seconds": 600},'
            ' "stories": [{"number": "348", "status": "sliced", "title": "Panel", "lessons": [],'
            ' "slices": [{"number": "351", "status": "pr_open", "title": "The snapshot", "pr_number": null}]}]}'
        )

        found = FilesystemLoopSnapshots(repos_dir=tmp_path).find("acme/tooling")

        assert found is not None
        assert found.stories[0].slices[0].depends_on == []

    def test_should_read_a_slice_written_without_a_pull_request_summary_as_having_none(self, tmp_path: Path) -> None:
        repo_dir = tmp_path / "acme" / "tooling"
        repo_dir.mkdir(parents=True)
        (repo_dir / "snapshot.json").write_text(
            '{"repo": "acme/tooling",'
            ' "tick": {"outcome": "ok", "at": "2026-09-02T12:00:00+00:00",'
            ' "duration_seconds": 1, "interval_seconds": 600},'
            ' "stories": [{"number": "348", "status": "sliced", "title": "Panel", "lessons": [],'
            ' "slices": [{"number": "351", "status": "pr_open", "title": "The snapshot", "pr_number": "360",'
            ' "depends_on": []}]}]}'
        )

        found = FilesystemLoopSnapshots(repos_dir=tmp_path).find("acme/tooling")

        assert found is not None
        assert found.stories[0].slices[0].pull_request is None

    def test_should_replace_the_snapshot_on_every_publish(self, tmp_path: Path) -> None:
        snapshots = FilesystemLoopSnapshots(repos_dir=tmp_path)
        snapshots.publish(_snapshot())

        snapshots.publish(_snapshot(outcome=TickOutcome.FAILED, duration_seconds=41))

        found = snapshots.find("acme/tooling")
        assert found is not None
        assert found.tick == SnapshotTick(outcome=TickOutcome.FAILED, at=_T0, duration_seconds=41, interval_seconds=600)

    def test_should_find_no_snapshot_when_the_file_is_missing(self, tmp_path: Path) -> None:
        snapshots = FilesystemLoopSnapshots(repos_dir=tmp_path)

        assert snapshots.find("acme/tooling") is None

    def test_should_find_no_snapshot_when_the_file_is_unreadable(self, tmp_path: Path) -> None:
        repo_dir = tmp_path / "acme" / "tooling"
        repo_dir.mkdir(parents=True)
        (repo_dir / "snapshot.json").write_text("{not json")

        assert FilesystemLoopSnapshots(repos_dir=tmp_path).find("acme/tooling") is None

    def test_should_find_no_snapshot_when_the_tick_fields_are_absent(self, tmp_path: Path) -> None:
        repo_dir = tmp_path / "acme" / "tooling"
        repo_dir.mkdir(parents=True)
        (repo_dir / "snapshot.json").write_text('{"repo": "acme/tooling", "stories": []}')

        assert FilesystemLoopSnapshots(repos_dir=tmp_path).find("acme/tooling") is None

    def test_should_find_no_snapshot_when_the_tick_instant_has_no_timezone(self, tmp_path: Path) -> None:
        repo_dir = tmp_path / "acme" / "tooling"
        repo_dir.mkdir(parents=True)
        (repo_dir / "snapshot.json").write_text(
            '{"repo": "acme/tooling", "stories": [],'
            ' "tick": {"outcome": "ok", "at": "2026-09-02T12:00:00", "duration_seconds": 1}}'
        )

        assert FilesystemLoopSnapshots(repos_dir=tmp_path).find("acme/tooling") is None

    def test_should_find_no_snapshot_when_the_outcome_is_unknown(self, tmp_path: Path) -> None:
        repo_dir = tmp_path / "acme" / "tooling"
        repo_dir.mkdir(parents=True)
        (repo_dir / "snapshot.json").write_text(
            '{"repo": "acme/tooling", "stories": [],'
            ' "tick": {"outcome": "boom", "at": "2026-09-02T12:00:00+00:00", "duration_seconds": 1}}'
        )

        assert FilesystemLoopSnapshots(repos_dir=tmp_path).find("acme/tooling") is None
