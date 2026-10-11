from __future__ import annotations

from typing import TYPE_CHECKING, Any

from grooveloop.delivery.domain.pull_request import PullRequest
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.review_comment import ReviewComment
from grooveloop.delivery.domain.review_verdict import ReviewVerdict
from grooveloop.delivery.domain.slice import Slice
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_repository import SliceRepository
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.delivery.infrastructure.github_review_round_labels import (
    REVIEW_ROUND_LABEL_PREFIX,
    review_rounds_of,
)
from grooveloop.delivery.infrastructure.github_review_verdict_labels import (
    REVIEW_LABEL_PREFIX,
    review_verdict_of,
)
from grooveloop.shared.domain.agent_run_cause import AgentRunCause
from grooveloop.shared.domain.comment_directive import parse_comment_directives
from grooveloop.shared.infrastructure.cached_github_repo import CachedGithubRepo
from grooveloop.shared.infrastructure.github_graphql import GithubGraphQL
from grooveloop.shared.infrastructure.github_story_graph import (
    ISSUE_FIELDS,
    GithubStoryGraph,
    depends_on_of,
    label_in,
    label_suffix,
    order_of,
    story_number_of,
    to_issue_node,
)

if TYPE_CHECKING:
    from datetime import datetime

    from github.Repository import Repository

    from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
    from grooveloop.shared.infrastructure.github_story_graph import CommentNode, IssueNode, PullRequestNode

_PR_LABEL_PREFIX = "pr:"
_RUN_LABEL_PREFIX = "run:"
_RETRY_LABEL_PREFIX = "retry:"
_FAILURE_LABEL_PREFIX = "failure:"
_STATUS_VALUES = {status.value for status in SliceStatus}
_REVIEW_SUMMARY_MARKER = "<!-- grooveloop:review -->"
_TTL_SECONDS = 300
_ISSUE_KEY_PREFIX = "issues:slice-graph:issue:"

_ISSUE_QUERY = (
    "query($owner: String!, $name: String!, $number: Int!) {"
    " repository(owner: $owner, name: $name) { issue(number: $number) {" + ISSUE_FIELDS + "} } }"
)


class GithubSliceRepository(SliceRepository):
    def __init__(self, repo: Repository, cache: GithubReadCache) -> None:
        self._repo = CachedGithubRepo(repo, cache)
        self._cache = cache
        self._graphql = GithubGraphQL(repo.requester)
        self._graph = GithubStoryGraph(repo, cache)
        self._full_name = repo.full_name

    def find(self, id: SliceId) -> Slice | None:
        node = self._issue_node(int(id.value))
        if node is None:
            return None

        return self._to_slice(to_issue_node(node))

    def save(self, a_slice: Slice) -> None:
        issue = self._repo.issue(int(a_slice.id.value))
        kept = [
            label.name
            for label in issue.labels
            if label.name not in _STATUS_VALUES
            and not label.name.startswith(_RUN_LABEL_PREFIX)
            and not label.name.startswith(_PR_LABEL_PREFIX)
            and not label.name.startswith(REVIEW_ROUND_LABEL_PREFIX)
            and not label.name.startswith(REVIEW_LABEL_PREFIX)
            and not label.name.startswith(_RETRY_LABEL_PREFIX)
            and not label.name.startswith(_FAILURE_LABEL_PREFIX)
        ]
        run_labels = [f"{_RUN_LABEL_PREFIX}{a_slice.agent_run_id}"] if a_slice.agent_run_id is not None else []
        pr_labels = (
            [f"{_PR_LABEL_PREFIX}{a_slice.pull_request.number.value}"] if a_slice.pull_request is not None else []
        )

        round_labels = [f"{REVIEW_ROUND_LABEL_PREFIX}{a_slice.review_rounds}"] if a_slice.review_rounds > 0 else []
        verdict_labels = (
            [f"{REVIEW_LABEL_PREFIX}{a_slice.review_verdict.value}"]
            if a_slice.review_verdict is not ReviewVerdict.EMPTY
            else []
        )

        retry_labels = [f"{_RETRY_LABEL_PREFIX}{a_slice.retries}"] if a_slice.retries > 0 else []
        failure_labels = (
            [f"{_FAILURE_LABEL_PREFIX}{a_slice.failure_cause.value}"]
            if a_slice.failure_cause is not AgentRunCause.EMPTY
            else []
        )

        self._repo.set_issue_labels(
            int(a_slice.id.value),
            [
                *kept,
                a_slice.status.value,
                *run_labels,
                *pr_labels,
                *round_labels,
                *verdict_labels,
                *retry_labels,
                *failure_labels,
            ],
        )

    def search(
        self, story_id: StoryId | None = None, status: SliceStatus | None = None, open: bool | None = None
    ) -> list[Slice]:
        nodes = self._slice_nodes(story_id, open)
        matching = [node for node in nodes if status is None or self._status_from(node) == status]
        matching.sort(key=order_of)

        return [self._to_slice(node) for node in matching]

    def _slice_nodes(self, story_id: StoryId | None, open: bool | None) -> list[IssueNode]:
        nodes = self._graph.nodes()
        slices = [node for node in nodes if self._story_id_from(node) is not None]

        if story_id is not None:
            slices = [node for node in slices if self._story_id_from(node) == story_id]
        else:
            active = self._active_story_numbers(nodes)
            slices = [node for node in slices if story_number_of(node) in active]

        if open is None:
            return slices

        return [node for node in slices if node.closed is not open]

    def _active_story_numbers(self, nodes: list[IssueNode]) -> set[str]:
        return {story_number_of(node) or str(node.number) for node in nodes if not node.closed}

    def _issue_node(self, number: int) -> dict[str, Any] | None:
        owner, name = self._full_name.split("/", 1)

        def load() -> dict[str, Any] | None:
            data = self._graphql.query(_ISSUE_QUERY, {"owner": owner, "name": name, "number": number})
            issue: dict[str, Any] | None = data["repository"]["issue"]
            if issue is None:
                return None

            return self._graph.with_labeled_pull(issue)

        return self._cache.get_or_load(f"{_ISSUE_KEY_PREFIX}{number}", load, _TTL_SECONDS)

    def _to_slice(self, node: IssueNode) -> Slice:
        status = self._status_from(node)
        number = self._pull_request_number_from(node)

        return Slice(
            id=SliceId(str(node.number)),
            status=status,
            story_id=self._story_id_from(node),
            title=node.title,
            description=node.body,
            pull_request=self._pull_request_from(node) if Slice.tracks_pull_request_in(status) else None,
            pull_request_number=PullRequestNumber(number) if number is not None else None,
            agent_run_id=self._agent_run_id_from(node),
            review_verdict=review_verdict_of(node),
            review_rounds=review_rounds_of(node),
            depends_on=self._depends_on_from(node),
            retries=self._retries_from(node),
            failure_cause=AgentRunCause(label_suffix(node, _FAILURE_LABEL_PREFIX)),
        )

    def _pull_request_from(self, node: IssueNode) -> PullRequest | None:
        pull = node.pull_request
        if pull is None:
            return None

        return PullRequest(
            number=PullRequestNumber(pull.number),
            comments=self._comments_from(pull),
            last_commit_at=pull.last_commit_at,
            merged=pull.merged,
            closed=pull.closed,
            review_summary_at=self._review_summary_at(pull),
        )

    def _review_summary_at(self, pull: PullRequestNode) -> datetime | None:
        return max(
            (comment.created_at for comment in pull.conversation if _REVIEW_SUMMARY_MARKER in comment.body),
            default=None,
        )

    def _comments_from(self, pull: PullRequestNode) -> list[ReviewComment]:
        inline = [self._inline_comment(comment) for comment in pull.review]
        conversation = [self._conversation_comment(comment) for comment in pull.conversation]

        return inline + conversation

    def _inline_comment(self, comment: CommentNode) -> ReviewComment:
        root_id = comment.reply_to_id if comment.reply_to_id is not None else comment.database_id

        return ReviewComment(
            body=comment.body,
            created_at=comment.created_at,
            path=comment.path,
            line=comment.line,
            thread_id=str(root_id),
            directives=parse_comment_directives(comment.body),
        )

    def _conversation_comment(self, comment: CommentNode) -> ReviewComment:
        return ReviewComment(
            body=comment.body, created_at=comment.created_at, directives=parse_comment_directives(comment.body)
        )

    def _status_from(self, node: IssueNode) -> SliceStatus:
        status = label_in(node, _STATUS_VALUES)

        return SliceStatus(status) if status is not None else SliceStatus.PENDING

    def _story_id_from(self, node: IssueNode) -> StoryId | None:
        number = story_number_of(node)

        return StoryId(number) if number is not None else None

    def _agent_run_id_from(self, node: IssueNode) -> str | None:
        return label_suffix(node, _RUN_LABEL_PREFIX)

    def _retries_from(self, node: IssueNode) -> int:
        retries = label_suffix(node, _RETRY_LABEL_PREFIX)

        return int(retries) if retries is not None else 0

    def _pull_request_number_from(self, node: IssueNode) -> int | None:
        number = label_suffix(node, _PR_LABEL_PREFIX)

        return int(number) if number is not None else None

    def _depends_on_from(self, node: IssueNode) -> list[SliceId] | None:
        numbers = depends_on_of(node)
        if numbers is None:
            return None

        return [SliceId(number) for number in numbers]
