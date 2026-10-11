from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from grooveloop.shared.domain.pull_request_comment import PullRequestComment
from grooveloop.shared.domain.pull_request_detail import PullRequestDetail
from grooveloop.shared.domain.pull_request_detail_reading import PullRequestDetailReading
from grooveloop.shared.domain.pull_request_detail_state import PullRequestDetailState
from grooveloop.shared.domain.pull_request_file import PullRequestFile
from grooveloop.shared.infrastructure.filesystem_pull_request_details import FilesystemPullRequestDetails

if TYPE_CHECKING:
    from pathlib import Path

_REPO = "acme/tooling"
_T0 = datetime(2026, 9, 25, 12, 0, 0, tzinfo=UTC)


def _detail(number: int = 2115, head_ref_oid: str = "abc123") -> PullRequestDetail:
    return PullRequestDetail(
        number=number,
        body="## Summary",
        updated_at=_T0,
        head_ref_oid=head_ref_oid,
        checks="success",
        synced_at=_T0,
        files=[PullRequestFile(filename="src/x.py", status="modified", additions=3, deletions=1, patch="@@ -1 +1 @@")],
        conversation=[PullRequestComment(author="reviewer-bot", body="summary", created_at=_T0)],
        review=[
            PullRequestComment(
                author=None, body="use the port", created_at=_T0, path="src/x.py", line=10, diff_hunk="@@ @@"
            )
        ],
    )


def _pulls_dir(tmp_path: Path) -> Path:
    return tmp_path / "acme" / "tooling" / "pulls"


@pytest.mark.integration
class TestFilesystemPullRequestDetails:
    def test_should_write_the_detail_of_a_pull_request_under_the_pulls_directory(self, tmp_path: Path) -> None:
        FilesystemPullRequestDetails(repos_dir=tmp_path).publish(_REPO, _detail())

        stored = json.loads((_pulls_dir(tmp_path) / "2115.json").read_text())
        assert stored["version"] == 1
        assert stored["number"] == 2115
        assert stored["body"] == "## Summary"
        assert stored["updated_at"] == "2026-09-25T12:00:00+00:00"
        assert stored["synced_at"] == "2026-09-25T12:00:00+00:00"
        assert stored["files"] == [
            {"filename": "src/x.py", "status": "modified", "additions": 3, "deletions": 1, "patch": "@@ -1 +1 @@"}
        ]
        assert stored["review"][0]["path"] == "src/x.py"
        assert stored["review"][0]["line"] == 10

    def test_should_read_back_the_detail_it_wrote(self, tmp_path: Path) -> None:
        details = FilesystemPullRequestDetails(repos_dir=tmp_path)
        details.publish(_REPO, _detail())

        assert details.find(_REPO, 2115) == _detail()

    def test_should_leave_no_temporary_file_behind(self, tmp_path: Path) -> None:
        FilesystemPullRequestDetails(repos_dir=tmp_path).publish(_REPO, _detail())

        assert [path.name for path in _pulls_dir(tmp_path).iterdir()] == ["2115.json"]

    def test_should_find_no_detail_when_the_file_is_missing(self, tmp_path: Path) -> None:
        assert FilesystemPullRequestDetails(repos_dir=tmp_path).find(_REPO, 2115) is None

    def test_should_find_no_detail_when_the_file_is_unreadable(self, tmp_path: Path) -> None:
        _pulls_dir(tmp_path).mkdir(parents=True)
        (_pulls_dir(tmp_path) / "2115.json").write_text("{not json")

        assert FilesystemPullRequestDetails(repos_dir=tmp_path).find(_REPO, 2115) is None

    def test_should_find_no_detail_when_its_version_is_unknown(self, tmp_path: Path) -> None:
        details = FilesystemPullRequestDetails(repos_dir=tmp_path)
        details.publish(_REPO, _detail())
        path = _pulls_dir(tmp_path) / "2115.json"
        path.write_text(json.dumps({**json.loads(path.read_text()), "version": 99}))

        assert details.find(_REPO, 2115) is None

    def test_should_remove_the_detail_of_every_pull_request_not_retained(self, tmp_path: Path) -> None:
        details = FilesystemPullRequestDetails(repos_dir=tmp_path)
        details.publish(_REPO, _detail(number=2115))
        details.publish(_REPO, _detail(number=2116))

        details.retain(_REPO, [2116])

        assert [path.name for path in _pulls_dir(tmp_path).iterdir()] == ["2116.json"]

    def test_should_retain_nothing_when_no_detail_was_ever_written(self, tmp_path: Path) -> None:
        FilesystemPullRequestDetails(repos_dir=tmp_path).retain(_REPO, [])

        assert not _pulls_dir(tmp_path).exists()


@pytest.mark.integration
class TestFilesystemPullRequestDetailsReading:
    def test_should_read_the_detail_it_wrote_as_synced(self, tmp_path: Path) -> None:
        details = FilesystemPullRequestDetails(repos_dir=tmp_path)
        details.publish(_REPO, _detail())

        assert details.read(_REPO, 2115) == PullRequestDetailReading(
            state=PullRequestDetailState.SYNCED, detail=_detail()
        )

    def test_should_read_a_missing_file_as_missing(self, tmp_path: Path) -> None:
        reading = FilesystemPullRequestDetails(repos_dir=tmp_path).read(_REPO, 2115)

        assert reading == PullRequestDetailReading(state=PullRequestDetailState.MISSING)

    def test_should_read_a_file_of_unknown_version_as_unreadable(self, tmp_path: Path) -> None:
        details = FilesystemPullRequestDetails(repos_dir=tmp_path)
        details.publish(_REPO, _detail())
        path = _pulls_dir(tmp_path) / "2115.json"
        path.write_text(json.dumps({**json.loads(path.read_text()), "version": 99}))

        assert details.read(_REPO, 2115) == PullRequestDetailReading(state=PullRequestDetailState.UNREADABLE)

    def test_should_read_a_corrupt_file_as_unreadable(self, tmp_path: Path) -> None:
        _pulls_dir(tmp_path).mkdir(parents=True)
        (_pulls_dir(tmp_path) / "2115.json").write_text("{not json")

        reading = FilesystemPullRequestDetails(repos_dir=tmp_path).read(_REPO, 2115)

        assert reading == PullRequestDetailReading(state=PullRequestDetailState.UNREADABLE)

    def test_should_reread_the_file_only_when_its_mtime_changes(self, tmp_path: Path) -> None:
        details = FilesystemPullRequestDetails(repos_dir=tmp_path)
        details.publish(_REPO, _detail(head_ref_oid="abc123"))
        path = _pulls_dir(tmp_path) / "2115.json"
        mtime_ns = path.stat().st_mtime_ns
        details.read(_REPO, 2115)
        details.publish(_REPO, _detail(head_ref_oid="def456"))
        os.utime(path, ns=(mtime_ns, mtime_ns))

        unchanged = details.read(_REPO, 2115)
        os.utime(path, ns=(mtime_ns + 1_000_000_000, mtime_ns + 1_000_000_000))
        changed = details.read(_REPO, 2115)

        assert unchanged.detail == _detail(head_ref_oid="abc123")
        assert changed.detail == _detail(head_ref_oid="def456")
