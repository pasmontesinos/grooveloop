from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from grooveloop.journal.domain.agent_run_id import AgentRunId
from grooveloop.journal.infrastructure.local_agent_run_context_repository import (
    LocalAgentRunContextRepository,
)

if TYPE_CHECKING:
    from pathlib import Path


def _write_run_metadata(runs_dir: Path, run_id: str, **fields: str | None) -> None:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(json.dumps(fields))


@pytest.mark.integration
class TestLocalAgentRunContextRepository:
    def test_should_return_none_when_the_run_dir_does_not_exist(self, tmp_path: Path) -> None:
        repository = LocalAgentRunContextRepository(runs_dir=tmp_path)

        assert repository.find(AgentRunId("r-missing")) is None

    def test_should_return_the_context_stored_in_run_json(self, tmp_path: Path) -> None:
        _write_run_metadata(
            tmp_path,
            "r-1",
            repo="owner/repo",
            story_id="10",
            profile="developer",
            started_at="2026-09-23T15:46:13.351166+00:00",
        )
        repository = LocalAgentRunContextRepository(runs_dir=tmp_path)

        context = repository.find(AgentRunId("r-1"))

        assert context is not None
        assert context.repo == "owner/repo"
        assert context.story_id == "10"
        assert context.profile == "developer"
        assert context.started_at == datetime(2026, 9, 23, 15, 46, 13, 351166, tzinfo=UTC)

    def test_should_return_none_when_the_run_has_no_story(self, tmp_path: Path) -> None:
        _write_run_metadata(tmp_path, "r-2", repo="owner/repo", story_id=None, profile="developer")
        repository = LocalAgentRunContextRepository(runs_dir=tmp_path)

        assert repository.find(AgentRunId("r-2")) is None

    def test_should_return_none_when_the_run_json_predates_story_id_and_profile(self, tmp_path: Path) -> None:
        _write_run_metadata(tmp_path, "r-3", task_type="review_slice", slice_id="406", repo="owner/repo")
        repository = LocalAgentRunContextRepository(runs_dir=tmp_path)

        assert repository.find(AgentRunId("r-3")) is None
