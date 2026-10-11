from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.domain.loop_snapshots import LoopSnapshots

if TYPE_CHECKING:
    from grooveloop.shared.domain.loop_snapshot import LoopSnapshot


class FakeLoopSnapshots(LoopSnapshots):
    def __init__(self, snapshots: list[LoopSnapshot] | None = None) -> None:
        self.published: list[LoopSnapshot] = []
        self._snapshots = {snapshot.repo: snapshot for snapshot in (snapshots or [])}

    def publish(self, snapshot: LoopSnapshot) -> None:
        self.published.append(snapshot)
        self._snapshots[snapshot.repo] = snapshot

    def find(self, repo: str) -> LoopSnapshot | None:
        return self._snapshots.get(repo)


class FailingLoopSnapshots(LoopSnapshots):
    def publish(self, snapshot: LoopSnapshot) -> None:
        raise OSError("read-only file system")

    def find(self, repo: str) -> LoopSnapshot | None:
        return None
