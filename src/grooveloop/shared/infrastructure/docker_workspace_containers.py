from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

from grooveloop.shared.domain.workspace_containers import WorkspaceContainers

_PROJECT_LABEL = "com.docker.compose.project"
_WORKING_DIR_LABEL = "com.docker.compose.project.working_dir"
_LIST_TIMEOUT_SECONDS = 30
_REMOVE_TIMEOUT_SECONDS = 300


@dataclass(frozen=True)
class _Container:
    id: str
    project: str | None
    working_dir: str | None
    mount_sources: list[str]

    @classmethod
    def from_inspect(cls, entry: dict[str, Any]) -> Self:
        labels = (entry.get("Config") or {}).get("Labels") or {}

        return cls(
            id=entry["Id"],
            project=labels.get(_PROJECT_LABEL),
            working_dir=labels.get(_WORKING_DIR_LABEL),
            mount_sources=[mount["Source"] for mount in entry.get("Mounts") or [] if mount.get("Source")],
        )


class DockerWorkspaceContainers(WorkspaceContainers):
    def __init__(self, docker: str = "docker") -> None:
        self._docker = docker

    def remove(self, workspace: str) -> None:
        containers = self._containers()
        root = Path(workspace).resolve()
        projects = sorted(
            {
                container.project
                for container in containers
                if container.project is not None
                and container.working_dir is not None
                and _is_within(container.working_dir, root)
            }
        )
        loose = [
            container.id
            for container in containers
            if container.project is None and any(_is_within(source, root) for source in container.mount_sources)
        ]

        for project in projects:
            self._run(["compose", "-p", project, "down", "-v", "--remove-orphans"], f"docker compose -p {project} down")

        if loose:
            self._run(["rm", "-f", "-v", *loose], f"docker rm {' '.join(loose)}")

    def _containers(self) -> list[_Container]:
        try:
            listed = subprocess.run(
                [self._docker, "ps", "-aq", "--no-trunc"],
                capture_output=True,
                text=True,
                timeout=_LIST_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return []

        ids = listed.stdout.split()
        if listed.returncode != 0 or not ids:
            return []

        inspected = subprocess.run(
            [self._docker, "inspect", *ids],
            capture_output=True,
            text=True,
            timeout=_LIST_TIMEOUT_SECONDS,
            check=False,
        )

        return [_Container.from_inspect(entry) for entry in json.loads(inspected.stdout or "[]")]

    def _run(self, args: list[str], description: str) -> None:
        with tempfile.TemporaryDirectory() as neutral_dir:
            completed = subprocess.run(
                [self._docker, *args],
                cwd=neutral_dir,
                capture_output=True,
                text=True,
                timeout=_REMOVE_TIMEOUT_SECONDS,
                check=False,
            )

        if completed.returncode != 0:
            raise RuntimeError(f"{description} failed: {completed.stderr.strip()}")


def _is_within(path: str, root: Path) -> bool:
    return Path(path).resolve().is_relative_to(root)
