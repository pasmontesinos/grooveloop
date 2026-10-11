from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from grooveloop.shared.infrastructure.docker_workspace_containers import DockerWorkspaceContainers

_SURROGATE = """
import json, sys
from pathlib import Path

here = Path(__file__).parent
with (here / "calls.jsonl").open("a") as calls:
    calls.write(json.dumps(sys.argv[1:]) + "\\n")
state = json.loads((here / "state.json").read_text())
command = sys.argv[1]
if command in state["failing"]:
    sys.stderr.write(f"{command} exploded\\n")
    sys.exit(1)
if command == "ps":
    print("\\n".join(container["Id"] for container in state["containers"]))
if command == "inspect":
    print(json.dumps([container for container in state["containers"] if container["Id"] in sys.argv[2:]]))
"""


def _compose_container(container_id: str, project: str, working_dir: Path) -> dict[str, Any]:
    return {
        "Id": container_id,
        "Config": {
            "Labels": {
                "com.docker.compose.project": project,
                "com.docker.compose.project.working_dir": str(working_dir),
            }
        },
        "Mounts": [],
    }


def _loose_container(container_id: str, mount_source: Path) -> dict[str, Any]:
    return {
        "Id": container_id,
        "Config": {"Labels": None},
        "Mounts": [{"Type": "bind", "Source": str(mount_source), "Destination": "/src"}],
    }


def _surrogate_docker(tmp_path: Path, containers: list[dict[str, Any]], failing: list[str] | None = None) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(f"#!{sys.executable}\n{_SURROGATE}")
    docker.chmod(0o755)
    (bin_dir / "state.json").write_text(json.dumps({"containers": containers, "failing": failing or []}))

    return docker


def _calls(docker: Path) -> list[list[str]]:
    calls_file = docker.parent / "calls.jsonl"
    if not calls_file.is_file():
        return []

    return [json.loads(line) for line in calls_file.read_text().splitlines()]


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "runs" / "run-1" / "s12-abcdefgh"
    workspace.mkdir(parents=True)

    return workspace


@pytest.mark.integration
class TestDockerWorkspaceContainers:
    def test_downs_the_compose_projects_whose_working_dir_is_inside_the_workspace(self, tmp_path: Path) -> None:
        workspace = _workspace(tmp_path)
        docker = _surrogate_docker(
            tmp_path,
            [
                _compose_container("c1", "shop", workspace),
                _compose_container("c2", "shop", workspace),
                _compose_container("c3", "e2e", workspace / "e2e"),
            ],
        )

        DockerWorkspaceContainers(docker=str(docker)).remove(str(workspace))

        downs = [call for call in _calls(docker) if call[0] == "compose"]
        assert downs == [
            ["compose", "-p", "e2e", "down", "-v", "--remove-orphans"],
            ["compose", "-p", "shop", "down", "-v", "--remove-orphans"],
        ]

    def test_does_not_touch_a_compose_project_whose_working_dir_is_outside_the_workspace(self, tmp_path: Path) -> None:
        workspace = _workspace(tmp_path)
        docker = _surrogate_docker(
            tmp_path,
            [
                _compose_container("c1", "other", tmp_path / "runs" / "run-2" / "s12-zzzzzzzz"),
                _compose_container("c2", "sibling", Path(f"{workspace}-sibling")),
            ],
        )

        DockerWorkspaceContainers(docker=str(docker)).remove(str(workspace))

        assert [call for call in _calls(docker) if call[0] in ("compose", "rm")] == []

    def test_removes_with_their_volumes_the_containers_without_compose_that_mount_the_workspace(
        self, tmp_path: Path
    ) -> None:
        workspace = _workspace(tmp_path)
        docker = _surrogate_docker(
            tmp_path,
            [
                _loose_container("c1", workspace / "src"),
                _loose_container("c2", tmp_path / "elsewhere"),
                _loose_container("c3", workspace),
            ],
        )

        DockerWorkspaceContainers(docker=str(docker)).remove(str(workspace))

        assert [call for call in _calls(docker) if call[0] == "rm"] == [["rm", "-f", "-v", "c1", "c3"]]

    def test_does_nothing_when_docker_is_not_installed(self, tmp_path: Path) -> None:
        workspace = _workspace(tmp_path)

        DockerWorkspaceContainers(docker=str(tmp_path / "missing" / "docker")).remove(str(workspace))

    def test_does_nothing_when_the_daemon_does_not_respond(self, tmp_path: Path) -> None:
        workspace = _workspace(tmp_path)
        docker = _surrogate_docker(tmp_path, [_compose_container("c1", "shop", workspace)], failing=["ps"])

        DockerWorkspaceContainers(docker=str(docker)).remove(str(workspace))

        assert [call[0] for call in _calls(docker)] == ["ps"]

    def test_raises_naming_the_project_when_its_down_fails(self, tmp_path: Path) -> None:
        workspace = _workspace(tmp_path)
        docker = _surrogate_docker(tmp_path, [_compose_container("c1", "shop", workspace)], failing=["compose"])

        with pytest.raises(RuntimeError, match="docker compose -p shop down failed: compose exploded"):
            DockerWorkspaceContainers(docker=str(docker)).remove(str(workspace))
