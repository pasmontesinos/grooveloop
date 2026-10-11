from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grooveloop.bootstrap import container
from grooveloop.shared.domain.abandoned_agent_runs import AbandonedAgentRuns
from grooveloop.shared.domain.agent_workspaces import AgentWorkspaces
from grooveloop.shared.domain.pull_request_details import PullRequestDetails
from grooveloop.shared.domain.story_specs import StorySpecs
from grooveloop.shared.domain.workspace_containers import WorkspaceContainers
from grooveloop.shared.domain.workspace_processes import WorkspaceProcesses
from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
from tests.playground.shared.infrastructure.fake_abandoned_agent_runs import FakeAbandonedAgentRuns
from tests.playground.shared.infrastructure.fake_agent_workspaces import FakeAgentWorkspaces
from tests.playground.shared.infrastructure.fake_pull_request_details import FakePullRequestDetails
from tests.playground.shared.infrastructure.fake_story_specs import FakeStorySpecs
from tests.playground.shared.infrastructure.fake_workspace_containers import FakeWorkspaceContainers
from tests.playground.shared.infrastructure.fake_workspace_processes import FakeWorkspaceProcesses

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _restore_root_bindings() -> Iterator[None]:
    with container.restoring_bindings():
        yield


@pytest.fixture(autouse=True)
def _flush_github_read_cache() -> None:
    container.get(GithubReadCache).flush()


@pytest.fixture(autouse=True)
def _isolate_agent_workspaces() -> Iterator[None]:
    with container.override(AgentWorkspaces, FakeAgentWorkspaces()):
        yield


@pytest.fixture(autouse=True)
def _isolate_abandoned_agent_runs() -> Iterator[None]:
    with container.override(AbandonedAgentRuns, FakeAbandonedAgentRuns()):
        yield


@pytest.fixture(autouse=True)
def _isolate_workspace_processes() -> Iterator[None]:
    with container.override(WorkspaceProcesses, FakeWorkspaceProcesses()):
        yield


@pytest.fixture(autouse=True)
def _isolate_workspace_containers() -> Iterator[None]:
    with container.override(WorkspaceContainers, FakeWorkspaceContainers()):
        yield


@pytest.fixture(autouse=True)
def _isolate_pull_request_details() -> Iterator[None]:
    with container.override(PullRequestDetails, FakePullRequestDetails()):
        yield


@pytest.fixture(autouse=True)
def _isolate_story_specs() -> Iterator[None]:
    with container.override(StorySpecs, FakeStorySpecs()):
        yield
