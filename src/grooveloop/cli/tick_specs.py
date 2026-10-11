from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.shared.domain.story_specs import StorySpecs
    from grooveloop.shared.infrastructure.github_story_graph import GithubStoryGraph, IssueNode


class TickSpecs:
    def __init__(self, specs: StorySpecs, repo: str, graph: GithubStoryGraph | None) -> None:
        self._specs = specs
        self._repo = repo
        self._graph = graph

    def publish(self) -> None:
        if self._graph is None:
            return

        try:
            stories = [story_nodes.story for story_nodes in self._graph.stories()]
        except Exception as error:
            print(f"[warn] story specs read failed in {self._repo}: {error}", file=sys.stderr)

            return

        for story in stories:
            self._sync(story)

    def _sync(self, story: IssueNode) -> None:
        try:
            if self._specs.find(self._repo, story.number) == story.body:
                return

            self._specs.publish(self._repo, story.number, story.body)
        except OSError as error:
            print(f"[warn] story #{story.number} spec write failed in {self._repo}: {error}", file=sys.stderr)
