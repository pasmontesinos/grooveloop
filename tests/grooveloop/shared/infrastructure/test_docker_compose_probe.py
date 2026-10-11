from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from grooveloop.shared.infrastructure.docker_compose_probe import DockerComposeProbe


@pytest.mark.integration
class TestDockerComposeProbe:
    def test_check_should_pass_when_docker_compose_is_available(self) -> None:
        with patch("grooveloop.shared.infrastructure.docker_compose_probe.subprocess.run") as run:
            DockerComposeProbe().check()

        run.assert_called_once()

    def test_check_should_pass_when_docker_is_not_installed(self) -> None:
        with patch(
            "grooveloop.shared.infrastructure.docker_compose_probe.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            DockerComposeProbe().check()

    def test_check_should_raise_when_docker_lacks_compose(self) -> None:
        with patch(
            "grooveloop.shared.infrastructure.docker_compose_probe.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, ["docker", "compose", "version"]),
        ):
            with pytest.raises(subprocess.CalledProcessError):
                DockerComposeProbe().check()

    def test_should_expose_a_name(self) -> None:
        assert DockerComposeProbe().name == "docker-compose-cli"
