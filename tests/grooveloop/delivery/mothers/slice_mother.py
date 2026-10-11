from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.review_verdict import ReviewVerdict
from grooveloop.delivery.domain.slice import Slice
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.shared.domain.agent_run_cause import AgentRunCause

if TYPE_CHECKING:
    from grooveloop.delivery.domain.pull_request import PullRequest


class SliceMother:
    @staticmethod
    def create(
        slice_id: str | None = None,
        status: SliceStatus = SliceStatus.PENDING,
        story_id: str | None = None,
        title: str = "",
        description: str = "",
        pull_request: PullRequest | None = None,
        pull_request_number: int | None = None,
        agent_run_id: str | None = None,
        review_verdict: ReviewVerdict = ReviewVerdict.EMPTY,
        review_rounds: int = 0,
        depends_on: list[SliceId] | None = None,
        retries: int = 0,
        failure_cause: AgentRunCause = AgentRunCause.EMPTY,
    ) -> Slice:
        return Slice(
            id=SliceId(slice_id) if slice_id is not None else SliceId.generate(),
            status=status,
            story_id=StoryId(story_id) if story_id is not None else None,
            title=title,
            description=description,
            pull_request=pull_request,
            pull_request_number=PullRequestNumber(pull_request_number) if pull_request_number is not None else None,
            agent_run_id=agent_run_id,
            review_verdict=review_verdict,
            review_rounds=review_rounds,
            depends_on=depends_on,
            retries=retries,
            failure_cause=failure_cause,
        )
