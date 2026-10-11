from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime
from typing import TYPE_CHECKING, Any

from grooveloop.shared.domain.pull_request_comment import PullRequestComment
from grooveloop.shared.domain.pull_request_detail import PullRequestDetail
from grooveloop.shared.domain.pull_request_detail_reading import PullRequestDetailReading
from grooveloop.shared.domain.pull_request_detail_state import PullRequestDetailState
from grooveloop.shared.domain.pull_request_details import PullRequestDetails
from grooveloop.shared.domain.pull_request_file import PullRequestFile

if TYPE_CHECKING:
    from pathlib import Path

_VERSION = 1
_PULLS_DIR = "pulls"
_SUFFIX = ".json"
_PENDING_SUFFIX = ".json.tmp"


class FilesystemPullRequestDetails(PullRequestDetails):
    def __init__(self, repos_dir: Path) -> None:
        self._repos_dir = repos_dir
        self._readings: dict[Path, tuple[int, PullRequestDetailReading]] = {}

    def publish(self, repo: str, detail: PullRequestDetail) -> None:
        pulls_dir = self._pulls_dir(repo)
        pulls_dir.mkdir(parents=True, exist_ok=True)

        pending = pulls_dir / f"{detail.number}{_PENDING_SUFFIX}"
        pending.write_text(json.dumps({"version": _VERSION, **asdict(detail)}, default=_json_value))
        os.replace(pending, pulls_dir / f"{detail.number}{_SUFFIX}")

    def find(self, repo: str, number: int) -> PullRequestDetail | None:
        try:
            return _parse(self._pulls_dir(repo) / f"{number}{_SUFFIX}")
        except (OSError, TypeError, ValueError, KeyError):
            return None

    def read(self, repo: str, number: int) -> PullRequestDetailReading:
        path = self._pulls_dir(repo) / f"{number}{_SUFFIX}"
        try:
            mtime_ns = path.stat().st_mtime_ns
        except OSError:
            return PullRequestDetailReading(state=PullRequestDetailState.MISSING)

        memo = self._readings.get(path)
        if memo is not None and memo[0] == mtime_ns:
            return memo[1]

        reading = _reading_of(path)
        self._readings[path] = (mtime_ns, reading)

        return reading

    def retain(self, repo: str, numbers: list[int]) -> None:
        pulls_dir = self._pulls_dir(repo)
        if not pulls_dir.is_dir():
            return

        kept = {f"{number}{_SUFFIX}" for number in numbers}
        for path in pulls_dir.glob(f"*{_SUFFIX}"):
            if path.name not in kept:
                path.unlink(missing_ok=True)

    def _pulls_dir(self, repo: str) -> Path:
        return self._repos_dir / repo / _PULLS_DIR


def _json_value(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()

    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def _parse(path: Path) -> PullRequestDetail | None:
    return _to_domain(json.loads(path.read_text()))


def _reading_of(path: Path) -> PullRequestDetailReading:
    try:
        detail = _parse(path)
    except OSError:
        return PullRequestDetailReading(state=PullRequestDetailState.MISSING)
    except (TypeError, ValueError, KeyError):
        return PullRequestDetailReading(state=PullRequestDetailState.UNREADABLE)

    if detail is None:
        return PullRequestDetailReading(state=PullRequestDetailState.UNREADABLE)

    return PullRequestDetailReading(state=PullRequestDetailState.SYNCED, detail=detail)


def _to_domain(stored: Any) -> PullRequestDetail | None:
    if stored["version"] != _VERSION:
        return None

    return PullRequestDetail(
        number=int(stored["number"]),
        body=str(stored["body"]),
        updated_at=datetime.fromisoformat(str(stored["updated_at"])),
        head_ref_oid=str(stored["head_ref_oid"]),
        checks=_text_or_none(stored["checks"]),
        synced_at=datetime.fromisoformat(str(stored["synced_at"])),
        files=[_file_of(file) for file in stored["files"]],
        conversation=[_comment_of(comment) for comment in stored["conversation"]],
        review=[_comment_of(comment) for comment in stored["review"]],
    )


def _file_of(stored: Any) -> PullRequestFile:
    return PullRequestFile(
        filename=str(stored["filename"]),
        status=str(stored["status"]),
        additions=int(stored["additions"]),
        deletions=int(stored["deletions"]),
        patch=_text_or_none(stored["patch"]),
    )


def _comment_of(stored: Any) -> PullRequestComment:
    return PullRequestComment(
        author=_text_or_none(stored["author"]),
        body=str(stored["body"]),
        created_at=datetime.fromisoformat(str(stored["created_at"])),
        path=_text_or_none(stored["path"]),
        line=None if stored["line"] is None else int(stored["line"]),
        diff_hunk=_text_or_none(stored["diff_hunk"]),
    )


def _text_or_none(value: Any) -> str | None:
    return None if value is None else str(value)
