from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.infrastructure.cached_github_repo import CachedGithubRepo
from grooveloop.shared.infrastructure.github_story_graph import GithubStoryGraph, story_number_of
from grooveloop.slicing.domain.story import Story
from grooveloop.slicing.domain.story_id import StoryId
from grooveloop.slicing.domain.story_repository import StoryRepository
from grooveloop.slicing.domain.story_status import StoryStatus
from grooveloop.slicing.infrastructure.spec_markdown_parser import parse_spec

if TYPE_CHECKING:
    from github.Repository import Repository

    from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
    from grooveloop.shared.infrastructure.github_story_graph import IssueNode
    from grooveloop.slicing.domain.slice import Slice

_MARKER_LABEL = "grooveloop"
_READY_FOR_IMPLEMENTATION_LABEL = "ready_for_implementation"
_SLICED_LABEL = "sliced"
_DONE_LABEL = "done"
_PENDING_LABEL = "pending"
_LIFECYCLE_LABELS = {_READY_FOR_IMPLEMENTATION_LABEL, _SLICED_LABEL, _DONE_LABEL}
_STORY_LABEL_PREFIX = "story:"
_ORDER_LABEL_PREFIX = "order:"
_VERIFY_DEPLOY_LABEL = "verify-deploy"
_DEPENDS_ON_MARKER = "<!-- grooveloop:depends-on -->"
_NO_DEPENDENCY = "none"


class GithubStoryRepository(StoryRepository):
    def __init__(self, repo: Repository, cache: GithubReadCache) -> None:
        self._repo = CachedGithubRepo(repo, cache)
        self._graph = GithubStoryGraph(repo, cache)

    def find(self, id: StoryId) -> Story | None:
        issue = self._repo.issue(int(id.value))
        labels = [label.name for label in issue.labels]

        if _MARKER_LABEL not in labels:
            return None

        return Story(id=id, spec=parse_spec(issue.body or ""), status=_status_of(labels), slices=[], title=issue.title)

    def save(self, story: Story) -> None:
        issue_number_by_order: dict[int, int] = {}

        for a_slice in story.slices:
            issue = self._repo.create_issue(
                title=a_slice.title,
                body=_body_with_depends_on(a_slice, issue_number_by_order),
                labels=_slice_labels(story.id, a_slice),
            )
            issue_number_by_order[a_slice.order.value] = issue.number

        if story.status == StoryStatus.SLICED:
            self._repo.add_issue_labels(int(story.id.value), [_SLICED_LABEL])
        elif story.status == StoryStatus.DONE:
            issue = self._repo.issue(int(story.id.value))
            kept = [label.name for label in issue.labels if label.name not in _LIFECYCLE_LABELS]
            self._repo.set_issue_labels(int(story.id.value), [*kept, _DONE_LABEL])
            self._repo.close_issue(int(story.id.value))

    def search(self, status: StoryStatus | None = None, open: bool | None = None) -> list[Story]:
        stories = (
            _to_story(node)
            for node in self._graph.nodes()
            if story_number_of(node) is None and (open is None or node.closed is not open)
        )

        return [story for story in stories if story.spec.items and (status is None or story.status == status)]


def _slice_labels(story_id: StoryId, a_slice: Slice) -> list[str]:
    labels = [
        _MARKER_LABEL,
        f"{_STORY_LABEL_PREFIX}{story_id.value}",
        _PENDING_LABEL,
        f"{_ORDER_LABEL_PREFIX}{a_slice.order.value}",
    ]

    return [*labels, _VERIFY_DEPLOY_LABEL] if a_slice.verify_deploy else labels


def _body_with_depends_on(a_slice: Slice, issue_number_by_order: dict[int, int]) -> str:
    if a_slice.depends_on is None:
        return a_slice.description

    references = (
        ", ".join(f"#{issue_number_by_order[position.value]}" for position in a_slice.depends_on)
        if a_slice.depends_on
        else _NO_DEPENDENCY
    )

    return f"{a_slice.description}\n\n{_DEPENDS_ON_MARKER}\n**Depends on:** {references}"


def _to_story(node: IssueNode) -> Story:
    return Story(
        id=StoryId(str(node.number)),
        spec=parse_spec(node.body),
        status=_status_of(node.labels),
        slices=[],
        title=node.title,
    )


def _status_of(labels: list[str]) -> StoryStatus:
    if _DONE_LABEL in labels:
        return StoryStatus.DONE

    if _SLICED_LABEL in labels:
        return StoryStatus.SLICED

    if _READY_FOR_IMPLEMENTATION_LABEL in labels:
        return StoryStatus.READY_FOR_IMPLEMENTATION

    return StoryStatus.DRAFT
