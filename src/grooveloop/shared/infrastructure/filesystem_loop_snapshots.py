from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime
from typing import TYPE_CHECKING, Any

from grooveloop.shared.domain.loop_snapshot import LoopSnapshot
from grooveloop.shared.domain.loop_snapshots import LoopSnapshots
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

if TYPE_CHECKING:
    from pathlib import Path

_SNAPSHOT_FILE = "snapshot.json"
_PENDING_FILE = "snapshot.json.tmp"


class FilesystemLoopSnapshots(LoopSnapshots):
    def __init__(self, repos_dir: Path) -> None:
        self._repos_dir = repos_dir

    def publish(self, snapshot: LoopSnapshot) -> None:
        repo_dir = self._repos_dir / snapshot.repo
        repo_dir.mkdir(parents=True, exist_ok=True)

        pending = repo_dir / _PENDING_FILE
        pending.write_text(json.dumps(_to_json(snapshot), default=_json_value))
        os.replace(pending, repo_dir / _SNAPSHOT_FILE)

    def find(self, repo: str) -> LoopSnapshot | None:
        try:
            stored = json.loads((self._repos_dir / repo / _SNAPSHOT_FILE).read_text())

            return _to_domain(stored)
        except (OSError, TypeError, ValueError, KeyError):
            return None


def _to_json(snapshot: LoopSnapshot) -> dict[str, Any]:
    payload = asdict(snapshot)
    payload["tick"]["outcome"] = snapshot.tick.outcome.value

    return payload


def _json_value(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()

    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def _to_domain(stored: Any) -> LoopSnapshot | None:
    tick = _tick_of(stored["tick"])
    if tick is None:
        return None

    return LoopSnapshot(
        repo=str(stored["repo"]),
        tick=tick,
        stories=[_story_of(story) for story in stored["stories"]],
    )


def _tick_of(stored: Any) -> SnapshotTick | None:
    at = datetime.fromisoformat(str(stored["at"]))
    if at.tzinfo is None:
        return None

    return SnapshotTick(
        outcome=TickOutcome(str(stored["outcome"])),
        at=at,
        duration_seconds=int(stored["duration_seconds"]),
        interval_seconds=int(stored["interval_seconds"]),
    )


def _story_of(stored: Any) -> SnapshotStory:
    return SnapshotStory(
        number=str(stored["number"]),
        status=SnapshotStoryStatus(str(stored["status"])),
        title=str(stored["title"]),
        slices=[_slice_of(a_slice) for a_slice in stored["slices"]],
        lessons=[_lesson_of(lesson) for lesson in stored["lessons"]],
    )


def _slice_of(stored: Any) -> SnapshotSlice:
    return SnapshotSlice(
        number=str(stored["number"]),
        status=SnapshotSliceStatus(str(stored["status"])),
        title=str(stored["title"]),
        pr_number=_text_or_none(stored["pr_number"]),
        depends_on=[str(number) for number in stored.get("depends_on", [])],
        pull_request=_pull_request_of(stored.get("pull_request")),
    )


def _pull_request_of(stored: Any) -> SnapshotPullRequest | None:
    if stored is None:
        return None

    return SnapshotPullRequest(
        title=str(stored["title"]),
        additions=int(stored["additions"]),
        deletions=int(stored["deletions"]),
        changed_files=int(stored["changed_files"]),
        updated_at=datetime.fromisoformat(str(stored["updated_at"])),
        head_ref_oid=str(stored["head_ref_oid"]),
        mergeable=SnapshotMergeability(str(stored["mergeable"])),
        checks=_text_or_none(stored["checks"]),
    )


def _lesson_of(stored: Any) -> SnapshotLesson:
    return SnapshotLesson(
        number=_text_or_none(stored["number"]),
        source_pull_request_number=int(stored["source_pull_request_number"]),
        status=SnapshotLessonStatus(str(stored["status"])),
        conventions_pull_request_number=_number_or_none(stored["conventions_pull_request_number"]),
        resolved=bool(stored["resolved"]),
    )


def _text_or_none(value: Any) -> str | None:
    return None if value is None else str(value)


def _number_or_none(value: Any) -> int | None:
    return None if value is None else int(value)
