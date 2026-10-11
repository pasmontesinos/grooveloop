from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

from grooveloop.cli.tick_specs import TickSpecs
from grooveloop.shared.infrastructure.github_story_graph import GithubStoryGraph, IssueNode, StoryNodes
from tests.playground.shared.infrastructure.fake_story_specs import FakeStorySpecs

if TYPE_CHECKING:
    import pytest

_REPO = "acme/sample"


def _story(number: int, body: str) -> StoryNodes:
    return StoryNodes(
        story=IssueNode(number=number, title="", body=body, labels=[], closed=False, pull_request=None), slices=[]
    )


def _graph_returning(*stories: StoryNodes) -> Any:
    graph = create_autospec(GithubStoryGraph, spec_set=True, instance=True)
    graph.stories.return_value = list(stories)

    return graph


class TestTickSpecs:
    def test_should_publish_the_body_of_every_story_of_the_graph(self) -> None:
        specs = FakeStorySpecs()

        TickSpecs(specs=specs, repo=_REPO, graph=_graph_returning(_story(10, "## Slices\n"), _story(20, ""))).publish()

        assert specs.find(_REPO, 10) == "## Slices\n"
        assert specs.find(_REPO, 20) == ""

    def test_should_not_rewrite_a_spec_that_did_not_change(self) -> None:
        specs = FakeStorySpecs({10: "## Slices\n"})

        TickSpecs(specs=specs, repo=_REPO, graph=_graph_returning(_story(10, "## Slices\n"))).publish()

        assert specs.published == []

    def test_should_rewrite_a_spec_whose_body_changed(self) -> None:
        specs = FakeStorySpecs({10: "before"})

        TickSpecs(specs=specs, repo=_REPO, graph=_graph_returning(_story(10, "after"))).publish()

        assert specs.published == [10]
        assert specs.find(_REPO, 10) == "after"

    def test_should_warn_and_go_on_when_a_spec_cannot_be_written(self, capsys: pytest.CaptureFixture[str]) -> None:
        specs = FakeStorySpecs(failing=[10])

        TickSpecs(specs=specs, repo=_REPO, graph=_graph_returning(_story(10, "a"), _story(20, "b"))).publish()

        assert specs.published == [20]
        assert "[warn] story #10 spec write failed in acme/sample: read-only file system" in (capsys.readouterr().err)

    def test_should_warn_when_the_graph_cannot_be_read(self, capsys: pytest.CaptureFixture[str]) -> None:
        graph = create_autospec(GithubStoryGraph, spec_set=True, instance=True)
        graph.stories.side_effect = RuntimeError("502 Bad Gateway")

        TickSpecs(specs=FakeStorySpecs(), repo=_REPO, graph=graph).publish()

        assert "[warn] story specs read failed in acme/sample: 502 Bad Gateway" in capsys.readouterr().err

    def test_should_publish_nothing_without_a_graph(self) -> None:
        specs = FakeStorySpecs()

        TickSpecs(specs=specs, repo=_REPO, graph=None).publish()

        assert specs.published == []
