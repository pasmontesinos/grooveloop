from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from grooveloop.shared.domain.agent_workspaces import AgentWorkspaces
from grooveloop.shared.infrastructure.agent_exit_marker import read_exit_code

if TYPE_CHECKING:
    from grooveloop.shared.domain.clock import Clock

_WORKSPACE_DIR = "workdir"
_LOG_FILE = "agent.log"
_METADATA_FILE = "run.json"
_RECOVERY_GRACE = timedelta(minutes=30)


class LocalAgentWorkspaces(AgentWorkspaces):
    def __init__(self, runs_dir: Path, clock: Clock) -> None:
        self._runs_dir = runs_dir
        self._clock = clock

    def finished_run_ids(self) -> list[str]:
        if not self._runs_dir.is_dir():
            return []

        workspaces = {
            run_dir: workspace
            for run_dir in sorted(self._runs_dir.iterdir())
            if run_dir.is_dir() and (workspace := self._workspace_of(run_dir)) is not None
        }
        in_use = {workspace for run_dir, workspace in workspaces.items() if not self._is_over(run_dir)}
        sweepable: dict[Path, str] = {}
        for run_dir, workspace in workspaces.items():
            if workspace not in in_use and workspace not in sweepable and workspace.is_dir():
                sweepable[workspace] = run_dir.name

        return sorted(sweepable.values())

    def _is_over(self, run_dir: Path) -> bool:
        return self._has_finished(run_dir) and self._has_outlived_recovery(run_dir)

    def _has_finished(self, run_dir: Path) -> bool:
        log = run_dir / _LOG_FILE
        if not log.is_file():
            return False

        return read_exit_code(log) is not None

    def _has_outlived_recovery(self, run_dir: Path) -> bool:
        finished_at = datetime.fromtimestamp((run_dir / _LOG_FILE).stat().st_mtime, tz=UTC)

        return self._clock.now() - finished_at > _RECOVERY_GRACE

    def _workspace_of(self, run_dir: Path) -> Path | None:
        try:
            metadata = json.loads((run_dir / _METADATA_FILE).read_text())
        except (OSError, ValueError):
            metadata = None

        workdir = metadata.get("workdir") if isinstance(metadata, dict) else None
        if not isinstance(workdir, str):
            return (run_dir / _WORKSPACE_DIR).resolve()

        workspace = Path(workdir).resolve()
        runs_dir = self._runs_dir.resolve()
        is_inside_a_run_dir = workspace.is_relative_to(runs_dir) and len(workspace.relative_to(runs_dir).parts) >= 2

        return workspace if is_inside_a_run_dir else None

    def workspace_of(self, run_id: str) -> str | None:
        workspace = self._workspace_of(self._runs_dir / run_id)
        if workspace is None or not workspace.is_dir():
            return None

        return str(workspace)

    def remove(self, run_id: str) -> None:
        path = self.workspace_of(run_id)
        if path is None:
            return

        workspace = Path(path)
        common_dir = self._common_dir_of(workspace)
        if common_dir is None:
            shutil.rmtree(workspace, ignore_errors=True)

            return

        main_repo = self._main_repo_of(workspace, common_dir)
        subprocess.run(
            ["git", "-C", str(main_repo), "worktree", "remove", "--force", str(workspace)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["git", "-C", str(main_repo), "worktree", "prune"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _common_dir_of(self, workspace: Path) -> str | None:
        if not (workspace / ".git").exists():
            return None

        completed = subprocess.run(
            ["git", "-C", str(workspace), "rev-parse", "--git-common-dir"],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            return None

        return completed.stdout.strip()

    def _main_repo_of(self, workspace: Path, common_dir: str) -> Path:
        common = Path(common_dir)
        if not common.is_absolute():
            common = (workspace / common).resolve()

        return common.parent
