from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from grooveloop.delivery.application.commands.address_review_changes import (
    AddressReviewChangesCommand,
    AddressReviewChangesCommandHandler,
)
from grooveloop.delivery.application.tasks.addressing_task import AddressingTask
from grooveloop.delivery.domain.pull_request import PullRequest
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.review_comment import ReviewComment
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.shared.domain.agent_profile import AgentProfile
from grooveloop.shared.domain.agent_task_type import AgentTaskType
from grooveloop.shared.domain.comment_directive import CommentDirective
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_agent_profiles import FakeAgentProfiles
from tests.playground.shared.infrastructure.fake_agent_runner import FakeAgentRunner
from tests.playground.shared.infrastructure.fake_agent_runner_registry import FakeAgentRunnerRegistry
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository

if TYPE_CHECKING:
    from grooveloop.delivery.domain.slice import Slice


def _developer(
    model: str = "opus",
    persona: str = "create and run a plan with superpowers",
    engine: str = "claude",
) -> AgentProfile:
    return AgentProfile(name="developer", engine=engine, model=model, skills=[], context_files=[], persona=persona)


def _pr_open_slice() -> Slice:
    return SliceMother.create(
        slice_id="12",
        status=SliceStatus.PR_OPEN,
        title="implement the SliceRepository",
        pull_request=PullRequest(
            number=PullRequestNumber(42),
            comments=[
                ReviewComment(
                    body="use the SliceRepository port",
                    path="src/x.py",
                    line=10,
                    thread_id="555",
                    created_at=datetime(2026, 6, 2, tzinfo=UTC),
                    directives=frozenset({CommentDirective.IMPLEMENT}),
                )
            ],
        ),
    )


def _rich_pr_open_slice() -> Slice:
    return SliceMother.create(
        slice_id="12",
        status=SliceStatus.PR_OPEN,
        title="implement the SliceRepository",
        pull_request=PullRequest(
            number=PullRequestNumber(42),
            comments=[
                ReviewComment(
                    body="use the SliceRepository port",
                    path="src/x.py",
                    line=10,
                    thread_id="555",
                    created_at=datetime(2026, 6, 2, tzinfo=UTC),
                ),
                ReviewComment(
                    body="/grooveloop-implement: and rename it to repo",
                    path="src/x.py",
                    line=10,
                    thread_id="555",
                    created_at=datetime(2026, 6, 3, tzinfo=UTC),
                    directives=frozenset({CommentDirective.IMPLEMENT}),
                ),
                ReviewComment(
                    body="Reviewer verdict: check the naming.",
                    created_at=datetime(2026, 6, 1, tzinfo=UTC),
                ),
                ReviewComment(
                    body="/grooveloop-implement: apply what was said in the thread",
                    created_at=datetime(2026, 6, 4, tzinfo=UTC),
                    directives=frozenset({CommentDirective.IMPLEMENT}),
                ),
            ],
        ),
    )


def _slice_with_a_learn_only_comment() -> Slice:
    return SliceMother.create(
        slice_id="12",
        status=SliceStatus.PR_OPEN,
        title="implement the SliceRepository",
        pull_request=PullRequest(
            number=PullRequestNumber(42),
            comments=[
                ReviewComment(
                    body="/grooveloop-implement: use the SliceRepository port",
                    path="src/x.py",
                    line=10,
                    thread_id="555",
                    created_at=datetime(2026, 6, 2, tzinfo=UTC),
                    directives=frozenset({CommentDirective.IMPLEMENT}),
                ),
                ReviewComment(
                    body="Reviewer verdict: check the naming.",
                    created_at=datetime(2026, 6, 1, tzinfo=UTC),
                ),
                ReviewComment(
                    body="/grooveloop-learn: document the criterion in the conventions",
                    created_at=datetime(2026, 6, 3, tzinfo=UTC),
                    directives=frozenset({CommentDirective.LEARN}),
                ),
                ReviewComment(
                    body="/grooveloop-implement: rename the method /grooveloop-learn: and note the reason",
                    created_at=datetime(2026, 6, 4, tzinfo=UTC),
                    directives=frozenset({CommentDirective.IMPLEMENT, CommentDirective.LEARN}),
                ),
            ],
        ),
    )


def _blocked_slice() -> Slice:
    return SliceMother.create(
        slice_id="12",
        status=SliceStatus.BLOCKED,
        title="implement the SliceRepository",
        pull_request=PullRequest(
            number=PullRequestNumber(42),
            comments=[
                ReviewComment(
                    body="/grooveloop-implement: let's go with option (b)",
                    created_at=datetime(2026, 6, 2, tzinfo=UTC),
                    directives=frozenset({CommentDirective.IMPLEMENT}),
                )
            ],
        ),
    )


def _under_review_slice() -> Slice:
    return SliceMother.create(
        slice_id="12",
        status=SliceStatus.UNDER_REVIEW,
        title="implement the SliceRepository",
        pull_request=PullRequest(
            number=PullRequestNumber(42),
            comments=[
                ReviewComment(
                    body="the detector does not cover the empty case",
                    created_at=datetime(2026, 6, 2, tzinfo=UTC),
                )
            ],
        ),
    )


def _automatic_command() -> AddressReviewChangesCommand:
    return AddressReviewChangesCommand(
        slice_id="12", workdir="/tmp/wd", repo="owner/repo", automatic=True, max_review_rounds=1
    )


class TestAddressReviewChangesCommandHandler:
    def test_dispatches_the_agent_with_the_comment_text_and_location(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_pr_open_slice()]})
        agent_runner = FakeAgentRunner()
        handler = AddressReviewChangesCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_developer()]),
            addressing_task=AddressingTask(),
        )

        handler(AddressReviewChangesCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        assert agent_runner.dispatched_count == 1
        assert agent_runner.last_workdir == "/tmp/wd"
        assert agent_runner.last_slice_id == "12"
        assert agent_runner.last_repo == "owner/repo"
        assert "use the SliceRepository port" in agent_runner.last_instruction
        assert "src/x.py:10" in agent_runner.last_instruction

    def test_renders_every_comment_channel_grouped_by_thread(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_rich_pr_open_slice()]})
        agent_runner = FakeAgentRunner()
        handler = AddressReviewChangesCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_developer()]),
            addressing_task=AddressingTask(),
        )

        handler(AddressReviewChangesCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        instruction = agent_runner.last_instruction
        assert "use the SliceRepository port" in instruction
        assert "and rename it to repo" in instruction
        assert "Reviewer verdict: check the naming." in instruction
        assert "apply what was said in the thread" in instruction
        assert "src/x.py:10" in instruction

    def test_tolerates_comments_without_a_diff_anchor(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_rich_pr_open_slice()]})
        agent_runner = FakeAgentRunner()
        handler = AddressReviewChangesCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_developer()]),
            addressing_task=AddressingTask(),
        )

        handler(AddressReviewChangesCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        assert "None" not in agent_runner.last_instruction

    def test_instructs_the_agent_to_reply_per_thread_and_push(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_pr_open_slice()]})
        agent_runner = FakeAgentRunner()
        handler = AddressReviewChangesCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_developer()]),
            addressing_task=AddressingTask(),
        )

        handler(AddressReviewChangesCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        assert "reply in each review thread" in agent_runner.last_instruction
        assert "push to the PR branch" in agent_runner.last_instruction

    def test_composes_the_task_with_the_resolved_developer_persona(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_pr_open_slice()]})
        agent_runner = FakeAgentRunner()
        handler = AddressReviewChangesCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_developer()]),
            addressing_task=AddressingTask(),
        )

        handler(AddressReviewChangesCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        assert "create and run a plan with superpowers" in agent_runner.last_instruction
        assert "use the SliceRepository port" in agent_runner.last_instruction

    def test_asks_to_wait_in_the_foreground_for_long_commands(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_pr_open_slice()]})
        agent_runner = FakeAgentRunner()
        handler = AddressReviewChangesCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_developer()]),
            addressing_task=AddressingTask(),
        )

        handler(AddressReviewChangesCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        assert "wait in the foreground" in agent_runner.last_instruction

    def test_dispatches_with_the_model_from_the_resolved_profile(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_pr_open_slice()]})
        agent_runner = FakeAgentRunner()
        handler = AddressReviewChangesCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_developer(model="sonnet")]),
            addressing_task=AddressingTask(),
        )

        handler(AddressReviewChangesCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        assert agent_runner.last_model == "sonnet"

    def test_dispatches_with_the_runner_of_the_profile_engine(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_pr_open_slice()]})
        agent_runner = FakeAgentRunner()
        registry = FakeAgentRunnerRegistry(agent_runner)
        handler = AddressReviewChangesCommandHandler(
            slice_repository=repository,
            agent_runner_registry=registry,
            agent_profiles=FakeAgentProfiles([_developer(engine="opencode")]),
            addressing_task=AddressingTask(),
        )

        handler(AddressReviewChangesCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        assert registry.requested_engines == ["opencode"]
        assert agent_runner.dispatched_count == 1

    def test_does_not_dispatch_when_the_developer_profile_is_missing(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_pr_open_slice()]})
        agent_runner = FakeAgentRunner()
        handler = AddressReviewChangesCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles(),
            addressing_task=AddressingTask(),
        )

        handler(AddressReviewChangesCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        assert agent_runner.dispatched_count == 0
        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.status == SliceStatus.PR_OPEN

    def test_reflects_requested_changes_on_a_pr_open_slice(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_pr_open_slice()]})
        handler = AddressReviewChangesCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(FakeAgentRunner()),
            agent_profiles=FakeAgentProfiles([_developer()]),
            addressing_task=AddressingTask(),
        )

        handler(AddressReviewChangesCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.status == SliceStatus.CHANGES_REQUESTED

    def test_records_the_dispatched_agent_run_on_the_slice(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_pr_open_slice()]})
        handler = AddressReviewChangesCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(FakeAgentRunner()),
            agent_profiles=FakeAgentProfiles([_developer()]),
            addressing_task=AddressingTask(),
        )

        handler(AddressReviewChangesCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.agent_run_id == "fake-run"

    def test_should_dispatch_with_the_address_review_task_type(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_pr_open_slice()]})
        agent_runner = FakeAgentRunner()
        handler = AddressReviewChangesCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_developer()]),
            addressing_task=AddressingTask(),
        )

        handler(AddressReviewChangesCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        assert agent_runner.last_task_type == AgentTaskType.ADDRESS_REVIEW

    def test_omits_comments_that_only_request_learning(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_slice_with_a_learn_only_comment()]})
        agent_runner = FakeAgentRunner()
        handler = AddressReviewChangesCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_developer()]),
            addressing_task=AddressingTask(),
        )

        handler(AddressReviewChangesCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        instruction = agent_runner.last_instruction
        assert "document the criterion in the conventions" not in instruction
        assert "use the SliceRepository port" in instruction
        assert "Reviewer verdict: check the naming." in instruction

    def test_keeps_comments_that_mix_learning_with_implementation(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_slice_with_a_learn_only_comment()]})
        agent_runner = FakeAgentRunner()
        handler = AddressReviewChangesCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_developer()]),
            addressing_task=AddressingTask(),
        )

        handler(AddressReviewChangesCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        assert "rename the method" in agent_runner.last_instruction

    def test_is_idempotent_when_the_slice_is_not_addressable(self) -> None:
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.CHANGES_REQUESTED)
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        agent_runner = FakeAgentRunner()
        handler = AddressReviewChangesCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_developer()]),
            addressing_task=AddressingTask(),
        )

        handler(AddressReviewChangesCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.status == SliceStatus.CHANGES_REQUESTED
        assert agent_runner.dispatched_count == 0

    def test_dispatches_the_developer_for_a_blocked_slice(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_blocked_slice()]})
        agent_runner = FakeAgentRunner()
        handler = AddressReviewChangesCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_developer()]),
            addressing_task=AddressingTask(),
        )

        handler(AddressReviewChangesCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        assert agent_runner.dispatched_count == 1
        assert "let's go with option (b)" in agent_runner.last_instruction
        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.status == SliceStatus.CHANGES_REQUESTED

    def test_dispatches_the_developer_for_an_under_review_slice(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_under_review_slice()]})
        agent_runner = FakeAgentRunner()
        handler = AddressReviewChangesCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_developer()]),
            addressing_task=AddressingTask(),
        )

        handler(_automatic_command())

        assert agent_runner.dispatched_count == 1
        assert "the detector does not cover the empty case" in agent_runner.last_instruction
        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.status == SliceStatus.CHANGES_REQUESTED

    def test_consumes_a_review_round_when_the_correction_is_automatic(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_under_review_slice()]})
        handler = AddressReviewChangesCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(FakeAgentRunner()),
            agent_profiles=FakeAgentProfiles([_developer()]),
            addressing_task=AddressingTask(),
        )

        handler(_automatic_command())

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.review_rounds == 1

    def test_refuses_the_automatic_correction_once_the_budget_is_spent(self) -> None:
        a_slice = _under_review_slice()
        a_slice.consume_review_round()
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        agent_runner = FakeAgentRunner()
        handler = AddressReviewChangesCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_developer()]),
            addressing_task=AddressingTask(),
        )

        handler(_automatic_command())

        assert agent_runner.dispatched_count == 0
        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.status == SliceStatus.UNDER_REVIEW

    def test_asks_the_developer_to_attend_the_reviewer_when_the_correction_is_automatic(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_under_review_slice()]})
        agent_runner = FakeAgentRunner()
        handler = AddressReviewChangesCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_developer()]),
            addressing_task=AddressingTask(),
        )

        handler(_automatic_command())

        assert "automatic reviewer" in agent_runner.last_instruction
        assert "Request changes" not in agent_runner.last_instruction

    def test_consumes_no_review_round_when_the_human_asks_for_the_correction(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_blocked_slice()]})
        handler = AddressReviewChangesCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(FakeAgentRunner()),
            agent_profiles=FakeAgentProfiles([_developer()]),
            addressing_task=AddressingTask(),
        )

        handler(AddressReviewChangesCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.review_rounds == 0

    def test_clears_a_stale_automatic_round_when_the_human_takes_over(self) -> None:
        a_slice = _pr_open_slice()
        a_slice.consume_review_round()
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        handler = AddressReviewChangesCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(FakeAgentRunner()),
            agent_profiles=FakeAgentProfiles([_developer()]),
            addressing_task=AddressingTask(),
        )

        handler(AddressReviewChangesCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.review_rounds == 0
