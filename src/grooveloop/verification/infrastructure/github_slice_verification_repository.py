from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.domain.agent_run_cause import AgentRunCause
from grooveloop.shared.infrastructure.cached_github_repo import CachedGithubRepo
from grooveloop.shared.infrastructure.github_story_graph import GithubStoryGraph, label_suffix, story_number_of
from grooveloop.verification.domain.slice_id import SliceId
from grooveloop.verification.domain.slice_verification import SliceVerification
from grooveloop.verification.domain.slice_verification_repository import SliceVerificationRepository
from grooveloop.verification.domain.story_id import StoryId
from grooveloop.verification.domain.verification_status import VerificationStatus

if TYPE_CHECKING:
    from github.Repository import Repository

    from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
    from grooveloop.shared.infrastructure.github_story_graph import IssueNode

_VERIFY_DEPLOY_LABEL = "verify-deploy"
_STATUS_LABEL_PREFIX = "verification:"
_RUN_LABEL_PREFIX = "verif-run:"
_RETRY_LABEL_PREFIX = "verif-retry:"
_FAILURE_LABEL_PREFIX = "failure:"
_OWNED_LABEL_PREFIXES = (_STATUS_LABEL_PREFIX, _RUN_LABEL_PREFIX, _RETRY_LABEL_PREFIX, _FAILURE_LABEL_PREFIX)


class GithubSliceVerificationRepository(SliceVerificationRepository):
    def __init__(self, repo: Repository, cache: GithubReadCache) -> None:
        self._repo = CachedGithubRepo(repo, cache)
        self._graph = GithubStoryGraph(repo, cache)

    def find(self, id: SliceId) -> SliceVerification | None:
        for node in self._marked_nodes():
            if str(node.number) == id.value:
                return self._to_verification(node)

        return None

    def save(self, verification: SliceVerification) -> None:
        number = int(verification.slice_id.value)
        issue = self._repo.issue(number)
        kept = [label.name for label in issue.labels if not label.name.startswith(_OWNED_LABEL_PREFIXES)]

        self._repo.set_issue_labels(
            number,
            [
                *kept,
                *self._run_labels(verification),
                *self._status_labels(verification.status),
                *self._retry_labels(verification),
                *self._failure_labels(verification),
            ],
        )

    def search(
        self, story_id: StoryId | None = None, status: VerificationStatus | None = None
    ) -> list[SliceVerification]:
        verifications = [self._to_verification(node) for node in self._marked_nodes()]

        if story_id is not None:
            verifications = [verification for verification in verifications if verification.story_id == story_id]

        if status is not None:
            verifications = [verification for verification in verifications if verification.status == status]

        return verifications

    def _marked_nodes(self) -> list[IssueNode]:
        return [node for node in self._graph.nodes() if _VERIFY_DEPLOY_LABEL in node.labels]

    def _run_labels(self, verification: SliceVerification) -> list[str]:
        if verification.agent_run_id is None:
            return []

        return [f"{_RUN_LABEL_PREFIX}{verification.agent_run_id}"]

    def _retry_labels(self, verification: SliceVerification) -> list[str]:
        if verification.retries == 0:
            return []

        return [f"{_RETRY_LABEL_PREFIX}{verification.retries}"]

    def _failure_labels(self, verification: SliceVerification) -> list[str]:
        if verification.failure_cause is AgentRunCause.EMPTY:
            return []

        return [f"{_FAILURE_LABEL_PREFIX}{verification.failure_cause.value}"]

    def _status_labels(self, status: VerificationStatus) -> list[str]:
        if status.value is None:
            return []

        return [f"{_STATUS_LABEL_PREFIX}{status.value}"]

    def _to_verification(self, node: IssueNode) -> SliceVerification:
        return SliceVerification(
            slice_id=SliceId(str(node.number)),
            story_id=self._story_id_from(node),
            status=VerificationStatus(label_suffix(node, _STATUS_LABEL_PREFIX)),
            agent_run_id=label_suffix(node, _RUN_LABEL_PREFIX),
            retries=self._retries_from(node),
            failure_cause=AgentRunCause(label_suffix(node, _FAILURE_LABEL_PREFIX)),
        )

    def _retries_from(self, node: IssueNode) -> int:
        retries = label_suffix(node, _RETRY_LABEL_PREFIX)

        return int(retries) if retries is not None else 0

    def _story_id_from(self, node: IssueNode) -> StoryId | None:
        number = story_number_of(node)

        return StoryId(number) if number is not None else None
