from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from grooveloop.shared.infrastructure.github_graphql import GithubGraphQL

if TYPE_CHECKING:
    from collections.abc import Callable

    from github.Repository import Repository

    from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache

_MARKER_LABEL = "grooveloop"
_LESSON_LABEL = "lesson"
_STORY_LABEL_PREFIX = "story:"
_ORDER_LABEL_PREFIX = "order:"
_SLICE_LABEL_PREFIX = "slice:"
_DEPENDS_ON_MARKER = "<!-- grooveloop:depends-on -->"
_DEPENDS_ON_LINE = re.compile(r"^\*\*Depends on:\*\*\s*(.+)$", re.MULTILINE)
_ISSUE_REFERENCE = re.compile(r"#(\d+)")
_GRAPH_KEY = "issues:story-graph"
_TTL_SECONDS = 300
_PAGE_SIZE = 100
_STORY_PAGE_SIZE = 20
_LABELS_LIMIT = 20
_CONVERSATION_LIMIT = 30
_THREADS_LIMIT = 30
_THREAD_COMMENTS_LIMIT = 20

_PAGE_INFO = "pageInfo { hasNextPage endCursor }"
_REACTION_FIELDS = "reactionGroups { content viewerHasReacted }"
_CONVERSATION_COMMENT_FIELDS = f"id author {{ login }} body createdAt {_REACTION_FIELDS}"
_REVIEW_COMMENT_FIELDS = (
    f"id databaseId author {{ login }} body path line diffHunk createdAt replyTo {{ databaseId }} {_REACTION_FIELDS}"
)

_PULL_REQUEST_FIELDS = f"""
  number
  title
  state
  merged
  additions
  deletions
  changedFiles
  updatedAt
  headRefOid
  mergeable
  commits(last: 1) {{ nodes {{ commit {{ committedDate statusCheckRollup {{ state }} }} }} }}
  comments(first: {_CONVERSATION_LIMIT}) {{ {_PAGE_INFO} nodes {{ {_CONVERSATION_COMMENT_FIELDS} }} }}
  reviewThreads(first: {_THREADS_LIMIT}) {{
    {_PAGE_INFO}
    nodes {{
      id
      comments(first: {_THREAD_COMMENTS_LIMIT}) {{ {_PAGE_INFO} nodes {{ {_REVIEW_COMMENT_FIELDS} }} }}
    }}
  }}
"""

ISSUE_FIELDS = f"""
  number
  title
  body
  state
  labels(first: {_LABELS_LIMIT}) {{ nodes {{ name }} }}
  closedByPullRequestsReferences(first: 1, includeClosedPrs: true) {{
    nodes {{ {_PULL_REQUEST_FIELDS} }}
  }}
"""

_DISCOVERY_FIELDS = f"""
  number
  labels(first: {_LABELS_LIMIT}) {{ nodes {{ name }} }}
"""

_LIVE_STORIES_QUERY = (
    "query($owner: String!, $name: String!, $label: String!, $page: Int!, $after: String) {"
    " repository(owner: $owner, name: $name) {"
    " issues(first: $page, after: $after, labels: [$label], states: [OPEN],"
    " orderBy: {field: CREATED_AT, direction: DESC}) {"
    " pageInfo { hasNextPage endCursor }"
    " nodes {" + _DISCOVERY_FIELDS + "} } } }"
)

_LAST_CLOSED_STORY_QUERY = (
    "query($owner: String!, $name: String!, $label: String!) {"
    " repository(owner: $owner, name: $name) {"
    " issues(first: 1, labels: [$label], states: [CLOSED],"
    " orderBy: {field: UPDATED_AT, direction: DESC}) {"
    " nodes {" + _DISCOVERY_FIELDS + "} } } }"
)

_STORY_QUERY = (
    "query($owner: String!, $name: String!, $number: Int!, $storyLabel: String!, $page: Int!, $after: String) {"
    " repository(owner: $owner, name: $name) {"
    " issue(number: $number) {" + ISSUE_FIELDS + "}"
    " issues(first: $page, after: $after, labels: [$storyLabel], states: [OPEN, CLOSED],"
    " orderBy: {field: CREATED_AT, direction: ASC}) {"
    " pageInfo { hasNextPage endCursor }"
    " nodes {" + ISSUE_FIELDS + "} } } }"
)

_PULL_REQUEST_QUERY = (
    "query($owner: String!, $name: String!, $number: Int!) {"
    " repository(owner: $owner, name: $name) {"
    " pullRequest(number: $number) {" + _PULL_REQUEST_FIELDS + "} } }"
)

_LABELED_PULL_QUERY = (
    "query($owner: String!, $name: String!, $label: String!) {"
    " repository(owner: $owner, name: $name) {"
    " pullRequests(first: 1, labels: [$label], states: [OPEN, CLOSED, MERGED],"
    " orderBy: {field: CREATED_AT, direction: DESC}) {"
    " nodes {" + _PULL_REQUEST_FIELDS + "} } } }"
)

_LABELED_PULLS_QUERY = (
    "query($owner: String!, $name: String!, $labels: [String!]!, $page: Int!, $after: String) {"
    " repository(owner: $owner, name: $name) {"
    " pullRequests(first: $page, after: $after, labels: $labels, states: [OPEN, CLOSED, MERGED],"
    " orderBy: {field: CREATED_AT, direction: DESC}) {"
    f" {_PAGE_INFO}"
    " nodes {" + _PULL_REQUEST_FIELDS + f" labels(first: {_LABELS_LIMIT}) {{ nodes {{ name }} }}" + "} } } }"
)

_PULL_COMMENTS_QUERY = (
    "query($owner: String!, $name: String!, $number: Int!, $page: Int!, $after: String) {"
    " repository(owner: $owner, name: $name) {"
    " pullRequest(number: $number) {"
    " comments(first: $page, after: $after) {"
    f" {_PAGE_INFO} nodes {{ {_CONVERSATION_COMMENT_FIELDS} }}"
    " } } } }"
)

_PULL_THREADS_QUERY = (
    "query($owner: String!, $name: String!, $number: Int!, $page: Int!, $after: String) {"
    " repository(owner: $owner, name: $name) {"
    " pullRequest(number: $number) {"
    " reviewThreads(first: $page, after: $after) {"
    f" {_PAGE_INFO} nodes {{ id"
    f" comments(first: {_PAGE_SIZE}) {{ {_PAGE_INFO} nodes {{ {_REVIEW_COMMENT_FIELDS} }} }} }}"
    " } } } }"
)

_THREAD_COMMENTS_QUERY = (
    "query($id: ID!, $page: Int!, $after: String) {"
    " node(id: $id) { ... on PullRequestReviewThread {"
    " comments(first: $page, after: $after) {"
    f" {_PAGE_INFO} nodes {{ {_REVIEW_COMMENT_FIELDS} }}"
    " } } } }"
)


@dataclass(frozen=True)
class CommentNode:
    body: str
    created_at: datetime
    database_id: int | None = None
    path: str | None = None
    line: int | None = None
    reply_to_id: int | None = None
    diff_hunk: str | None = None
    author: str | None = None
    node_id: str | None = None
    viewer_reactions: frozenset[str] = frozenset()


@dataclass(frozen=True)
class PullRequestNode:
    number: int
    merged: bool
    closed: bool
    last_commit_at: datetime | None
    conversation: list[CommentNode]
    review: list[CommentNode]
    title: str
    additions: int
    deletions: int
    changed_files: int
    updated_at: datetime
    head_ref_oid: str
    mergeable: str
    checks: str | None


@dataclass(frozen=True)
class IssueNode:
    number: int
    title: str
    body: str
    labels: list[str]
    closed: bool
    pull_request: PullRequestNode | None


@dataclass(frozen=True)
class StoryNodes:
    story: IssueNode
    slices: list[IssueNode]


class GithubStoryGraph:
    def __init__(self, repo: Repository, cache: GithubReadCache) -> None:
        self._graphql = GithubGraphQL(repo.requester)
        self._cache = cache
        self._full_name = repo.full_name

    def nodes(self) -> list[IssueNode]:
        return self._cache.get_or_load(_GRAPH_KEY, self._load, _TTL_SECONDS)

    def stories(self) -> list[StoryNodes]:
        nodes = self.nodes()
        slices: dict[str, list[IssueNode]] = {}

        for node in nodes:
            story_number = story_number_of(node)
            if story_number is not None:
                slices.setdefault(story_number, []).append(node)

        return [
            StoryNodes(story=node, slices=sorted(slices.get(str(node.number), []), key=order_of))
            for node in nodes
            if story_number_of(node) is None
        ]

    def pull_request(self, number: int) -> PullRequestNode | None:
        data = self._graphql.query(_PULL_REQUEST_QUERY, {**self._repo_variables(), "number": number})
        pull = data["repository"]["pullRequest"]
        if pull is None:
            return None

        return _to_pull_request(self._completed_pull(pull))

    def with_labeled_pull(self, node: dict[str, Any]) -> dict[str, Any]:
        if not _needs_labeled_pull(node):
            return node

        variables = {**self._repo_variables(), "label": _slice_label(node)}
        pulls = self._graphql.query(_LABELED_PULL_QUERY, variables)["repository"]["pullRequests"]["nodes"]

        return {**node, "closedByPullRequestsReferences": {"nodes": pulls}}

    def _load(self) -> list[IssueNode]:
        return [node for story_number in self._live_story_numbers() for node in self._story_nodes(story_number)]

    def _live_story_numbers(self) -> list[str]:
        numbers = _story_numbers_of(self._nodes_of(_LIVE_STORIES_QUERY, _issues_page, self._labeled_variables()))

        if len(numbers) > 0:
            return numbers

        return _story_numbers_of(self._last_closed_nodes())

    def _last_closed_nodes(self) -> list[dict[str, Any]]:
        data = self._graphql.query(_LAST_CLOSED_STORY_QUERY, self._labeled_variables())
        nodes: list[dict[str, Any]] = data["repository"]["issues"]["nodes"]

        return nodes

    def _story_nodes(self, story_number: str) -> list[IssueNode]:
        variables = {
            **self._repo_variables(),
            "number": int(story_number),
            "storyLabel": f"{_STORY_LABEL_PREFIX}{story_number}",
        }
        data = self._graphql.query(_STORY_QUERY, {**variables, "page": _STORY_PAGE_SIZE, "after": None})
        slices = self._all_nodes(
            data["repository"]["issues"], _STORY_QUERY, _issues_page, variables, page=_STORY_PAGE_SIZE
        )
        nodes = [
            node for node in _marked_story(data["repository"]["issue"]) + slices if not _has_label(node, _LESSON_LABEL)
        ]
        labeled_pulls = self._labeled_pulls([_slice_label(node) for node in nodes if _needs_labeled_pull(node)])

        return [to_issue_node(self._completed_issue(_with_pull(node, labeled_pulls))) for node in nodes]

    def _labeled_pulls(self, labels: list[str]) -> dict[str, dict[str, Any]]:
        if not labels:
            return {}

        variables = {**self._repo_variables(), "labels": labels}
        pulls = self._nodes_of(_LABELED_PULLS_QUERY, _pull_requests_page, variables, page=min(len(labels), _PAGE_SIZE))
        by_label: dict[str, dict[str, Any]] = {}

        for pull in pulls:
            for label in pull["labels"]["nodes"]:
                by_label.setdefault(label["name"], pull)

        return by_label

    def _completed_issue(self, linked: dict[str, Any]) -> dict[str, Any]:
        pulls = linked["closedByPullRequestsReferences"]["nodes"]
        if not pulls:
            return linked

        return {**linked, "closedByPullRequestsReferences": {"nodes": [self._completed_pull(pulls[0])]}}

    def _completed_pull(self, pull: dict[str, Any]) -> dict[str, Any]:
        variables = {**self._repo_variables(), "number": pull["number"]}
        threads = self._all_nodes(pull["reviewThreads"], _PULL_THREADS_QUERY, _pull_threads_page, variables)

        return {
            **pull,
            "comments": {
                "nodes": self._all_nodes(pull["comments"], _PULL_COMMENTS_QUERY, _pull_comments_page, variables)
            },
            "reviewThreads": {"nodes": [self._completed_thread(thread) for thread in threads]},
        }

    def _completed_thread(self, thread: dict[str, Any]) -> dict[str, Any]:
        variables = {"id": thread["id"]}
        comments = self._all_nodes(thread["comments"], _THREAD_COMMENTS_QUERY, _thread_comments_page, variables)

        return {**thread, "comments": {"nodes": comments}}

    def _all_nodes(
        self,
        connection: dict[str, Any],
        query: str,
        page_of: Callable[[dict[str, Any]], dict[str, Any]],
        variables: dict[str, Any],
        page: int = _PAGE_SIZE,
    ) -> list[dict[str, Any]]:
        page_info = connection["pageInfo"]
        nodes: list[dict[str, Any]] = connection["nodes"]

        if not page_info["hasNextPage"]:
            return nodes

        return nodes + self._nodes_of(query, page_of, variables, after=page_info["endCursor"], page=page)

    def _nodes_of(
        self,
        query: str,
        page_of: Callable[[dict[str, Any]], dict[str, Any]],
        variables: dict[str, Any],
        after: str | None = None,
        page: int = _PAGE_SIZE,
    ) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []

        while True:
            current = page_of(self._graphql.query(query, {**variables, "page": page, "after": after}))
            nodes.extend(current["nodes"])

            if not current["pageInfo"]["hasNextPage"]:
                return nodes

            after = current["pageInfo"]["endCursor"]

    def _labeled_variables(self) -> dict[str, Any]:
        return {**self._repo_variables(), "label": _MARKER_LABEL}

    def _repo_variables(self) -> dict[str, Any]:
        owner, name = self._full_name.split("/", 1)

        return {"owner": owner, "name": name}


def to_issue_node(node: dict[str, Any]) -> IssueNode:
    return IssueNode(
        number=node["number"],
        title=node["title"],
        body=node["body"] or "",
        labels=[label["name"] for label in node["labels"]["nodes"]],
        closed=node["state"] == "CLOSED",
        pull_request=_to_pull_request_node(node),
    )


def label_suffix(node: IssueNode, prefix: str) -> str | None:
    for name in node.labels:
        if name.startswith(prefix):
            return name.removeprefix(prefix)

    return None


def label_in(node: IssueNode, values: set[str]) -> str | None:
    for name in node.labels:
        if name in values:
            return name

    return None


def story_number_of(node: IssueNode) -> str | None:
    return label_suffix(node, _STORY_LABEL_PREFIX)


def order_of(node: IssueNode) -> int:
    order = label_suffix(node, _ORDER_LABEL_PREFIX)

    return int(order) if order is not None else 0


def depends_on_of(node: IssueNode) -> list[str] | None:
    if _DEPENDS_ON_MARKER not in node.body:
        return None

    match = _DEPENDS_ON_LINE.search(node.body)
    if match is None:
        return None

    return _ISSUE_REFERENCE.findall(match.group(1))


def _marked_story(node: dict[str, Any] | None) -> list[dict[str, Any]]:
    if node is None or not _has_label(node, _MARKER_LABEL):
        return []

    return [node]


def _needs_labeled_pull(node: dict[str, Any]) -> bool:
    return not node["closedByPullRequestsReferences"]["nodes"] and _is_open_slice(node)


def _is_open_slice(node: dict[str, Any]) -> bool:
    return node["state"] == "OPEN" and _story_label_of(node) is not None


def _slice_label(node: dict[str, Any]) -> str:
    return f"{_SLICE_LABEL_PREFIX}{node['number']}"


def _with_pull(node: dict[str, Any], labeled_pulls: dict[str, dict[str, Any]]) -> dict[str, Any]:
    pull = labeled_pulls.get(_slice_label(node)) if _needs_labeled_pull(node) else None
    if pull is None:
        return node

    return {**node, "closedByPullRequestsReferences": {"nodes": [pull]}}


def _has_label(node: dict[str, Any], name: str) -> bool:
    return any(label["name"] == name for label in node["labels"]["nodes"])


def _story_numbers_of(nodes: list[dict[str, Any]]) -> list[str]:
    numbers: list[str] = []

    for node in nodes:
        number = _story_label_of(node) or str(node["number"])

        if number not in numbers:
            numbers.append(number)

    return numbers


def _story_label_of(node: dict[str, Any]) -> str | None:
    for label in node["labels"]["nodes"]:
        name: str = label["name"]

        if name.startswith(_STORY_LABEL_PREFIX):
            return name.removeprefix(_STORY_LABEL_PREFIX)

    return None


def _issues_page(data: dict[str, Any]) -> dict[str, Any]:
    page: dict[str, Any] = data["repository"]["issues"]

    return page


def _pull_requests_page(data: dict[str, Any]) -> dict[str, Any]:
    page: dict[str, Any] = data["repository"]["pullRequests"]

    return page


def _pull_comments_page(data: dict[str, Any]) -> dict[str, Any]:
    page: dict[str, Any] = data["repository"]["pullRequest"]["comments"]

    return page


def _pull_threads_page(data: dict[str, Any]) -> dict[str, Any]:
    page: dict[str, Any] = data["repository"]["pullRequest"]["reviewThreads"]

    return page


def _thread_comments_page(data: dict[str, Any]) -> dict[str, Any]:
    page: dict[str, Any] = data["node"]["comments"]

    return page


def _to_pull_request_node(node: dict[str, Any]) -> PullRequestNode | None:
    pulls = node["closedByPullRequestsReferences"]["nodes"]
    if not pulls:
        return None

    return _to_pull_request(pulls[0])


def _to_pull_request(pull: dict[str, Any]) -> PullRequestNode:
    return PullRequestNode(
        number=pull["number"],
        merged=pull["merged"],
        closed=pull["state"] == "CLOSED",
        last_commit_at=_last_commit_at_of(pull),
        conversation=[_to_conversation_comment(comment) for comment in pull["comments"]["nodes"]],
        review=[
            _to_review_comment(comment)
            for thread in pull["reviewThreads"]["nodes"]
            for comment in thread["comments"]["nodes"]
        ],
        title=pull["title"],
        additions=pull["additions"],
        deletions=pull["deletions"],
        changed_files=pull["changedFiles"],
        updated_at=datetime.fromisoformat(pull["updatedAt"]),
        head_ref_oid=pull["headRefOid"],
        mergeable=pull["mergeable"],
        checks=_checks_of(pull),
    )


def _last_commit_at_of(pull: dict[str, Any]) -> datetime | None:
    nodes = pull["commits"]["nodes"]
    if not nodes:
        return None

    return datetime.fromisoformat(nodes[0]["commit"]["committedDate"])


def _checks_of(pull: dict[str, Any]) -> str | None:
    nodes = pull["commits"]["nodes"]
    if not nodes or nodes[0]["commit"]["statusCheckRollup"] is None:
        return None

    state: str = nodes[0]["commit"]["statusCheckRollup"]["state"]

    return state


def _to_conversation_comment(comment: dict[str, Any]) -> CommentNode:
    return CommentNode(
        body=comment["body"] or "",
        created_at=datetime.fromisoformat(comment["createdAt"]),
        author=_author_of(comment),
        node_id=comment["id"],
        viewer_reactions=_viewer_reactions_of(comment),
    )


def _to_review_comment(comment: dict[str, Any]) -> CommentNode:
    reply_to = comment["replyTo"]

    return CommentNode(
        body=comment["body"] or "",
        created_at=datetime.fromisoformat(comment["createdAt"]),
        database_id=comment["databaseId"],
        path=comment["path"],
        line=comment["line"],
        reply_to_id=reply_to["databaseId"] if reply_to is not None else None,
        diff_hunk=comment["diffHunk"],
        author=_author_of(comment),
        node_id=comment["id"],
        viewer_reactions=_viewer_reactions_of(comment),
    )


def _viewer_reactions_of(comment: dict[str, Any]) -> frozenset[str]:
    return frozenset(group["content"] for group in comment["reactionGroups"] if group["viewerHasReacted"])


def _author_of(comment: dict[str, Any]) -> str | None:
    author = comment["author"]
    if author is None:
        return None

    login: str = author["login"]

    return login
