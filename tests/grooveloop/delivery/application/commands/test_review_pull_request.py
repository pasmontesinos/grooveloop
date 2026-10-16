from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from grooveloop.delivery.application.commands.review_pull_request import (
    ReviewPullRequestCommand,
    ReviewPullRequestCommandHandler,
)
from grooveloop.delivery.application.tasks.review_task import ReviewTask
from grooveloop.delivery.application.tasks.story_journal_section import StoryJournalSection
from grooveloop.delivery.domain.directive_mark import DirectiveMark
from grooveloop.delivery.domain.pull_request import PullRequest
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.review_comment import ReviewComment
from grooveloop.delivery.domain.review_verdict import ReviewVerdict
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.shared.application.queries.read_journal_entries import (
    JournalEntryDTO,
    ReadJournalEntriesQuery,
    ReadJournalEntriesQueryResult,
)
from grooveloop.shared.domain.agent_profile import AgentProfile
from grooveloop.shared.domain.agent_task_type import AgentTaskType
from grooveloop.shared.domain.comment_directive import CommentDirective
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_agent_profiles import FakeAgentProfiles
from tests.playground.shared.infrastructure.fake_agent_runner import FakeAgentRunner
from tests.playground.shared.infrastructure.fake_agent_runner_registry import FakeAgentRunnerRegistry
from tests.playground.shared.infrastructure.fake_directive_marker import FakeDirectiveMarker
from tests.playground.shared.infrastructure.fake_query_bus import FakeQueryBus
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository

if TYPE_CHECKING:
    from grooveloop.delivery.domain.slice import Slice


def _query_bus(journal_entries: list[JournalEntryDTO] | None = None) -> FakeQueryBus:
    return FakeQueryBus(
        {ReadJournalEntriesQuery: lambda _query: ReadJournalEntriesQueryResult(entries=journal_entries or [])}
    )


def _reviewer(
    model: str = "opus",
    persona: str = "review the PR and leave a summary comment",
    engine: str = "claude",
) -> AgentProfile:
    return AgentProfile(name="reviewer", engine=engine, model=model, skills=[], context_files=[], persona=persona)


def _corrected_slice(pull_request_number: int = 99) -> Slice:
    return SliceMother.create(
        slice_id="12",
        status=SliceStatus.CHANGES_REQUESTED,
        title="implement the SliceRepository",
        description="use the port",
        pull_request=PullRequest(number=PullRequestNumber(pull_request_number), comments=[]),
        review_verdict=ReviewVerdict.BLOCKING,
        review_rounds=1,
    )


class TestReviewPullRequestCommandHandler:
    def test_anchors_the_pull_request_and_moves_a_dispatched_slice_to_under_review(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        title="implement the SliceRepository",
                        description="use the port",
                    )
                ]
            }
        )
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(FakeAgentRunner()),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(_query_bus())),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(ReviewPullRequestCommand(slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo"))

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.status == SliceStatus.UNDER_REVIEW
        assert result.pull_request is not None
        assert result.pull_request.number.value == 99

    def test_dispatches_the_reviewer_agent_with_the_review_slice_task_type(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        title="implement the SliceRepository",
                        description="use the port",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner()
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(_query_bus())),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(ReviewPullRequestCommand(slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo"))

        assert agent_runner.dispatched_count == 1
        assert agent_runner.last_task_type == AgentTaskType.REVIEW_SLICE
        assert agent_runner.last_workdir == "/tmp/wd"
        assert agent_runner.last_slice_id == "12"
        assert agent_runner.last_repo == "owner/repo"
        assert agent_runner.last_model == "opus"

    def test_composes_the_task_with_persona_context_and_the_diff_instruction(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        title="implement the SliceRepository",
                        description="use the port",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner()
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(_query_bus())),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(ReviewPullRequestCommand(slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo"))

        assert "review the PR and leave a summary comment" in agent_runner.last_instruction
        assert "implement the SliceRepository" in agent_runner.last_instruction
        assert "#99" in agent_runner.last_instruction
        assert "gh pr diff" in agent_runner.last_instruction

    def test_asks_to_wait_in_the_foreground_for_long_commands(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        title="implement the SliceRepository",
                        description="use the port",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner()
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(_query_bus())),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(ReviewPullRequestCommand(slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo"))

        assert "wait in the foreground" in agent_runner.last_instruction

    def test_task_instructs_the_single_summary_and_ends_with_the_review_marker(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        title="implement the SliceRepository",
                        description="use the port",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner()
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(_query_bus())),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(ReviewPullRequestCommand(slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo"))

        assert "<!-- grooveloop:review -->" in agent_runner.last_instruction

    def test_task_asks_for_the_verdict_label_before_the_comment_that_closes_the_review(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        title="implement the SliceRepository",
                        description="use the port",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner()
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(_query_bus())),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(ReviewPullRequestCommand(slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo"))

        instruction = agent_runner.last_instruction
        assert instruction.index("--add-label review:") < instruction.index("gh pr comment 99")
        assert instruction.index("--add-label review:") < instruction.index("<!-- grooveloop:review -->")

    def test_task_names_the_exact_label_command_and_the_four_verdicts(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        title="implement the SliceRepository",
                        description="use the port",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner()
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(_query_bus())),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(ReviewPullRequestCommand(slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo"))

        instruction = agent_runner.last_instruction
        assert "gh issue edit 12 --add-label review:" in instruction
        assert "review:approve" in instruction
        assert "review:minor" in instruction
        assert "review:blocking" in instruction
        assert "review:blocked" in instruction

    def test_task_lists_the_four_triggers_that_block_the_slice(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        title="implement the SliceRepository",
                        description="use the port",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner()
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(_query_bus())),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(ReviewPullRequestCommand(slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo"))

        instruction = agent_runner.last_instruction
        assert "two or more valid ways out" in instruction
        assert "declared scope of the slice" in instruction
        assert "contradicts an ADR" in instruction
        assert "CI, infra or dependencies shared" in instruction

    def test_records_the_dispatched_agent_run_on_the_slice(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        title="implement the SliceRepository",
                        description="use the port",
                    )
                ]
            }
        )
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(FakeAgentRunner()),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(_query_bus())),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(ReviewPullRequestCommand(slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo"))

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.agent_run_id == "fake-run"

    def test_dispatches_with_the_runner_of_the_profile_engine(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        title="implement the SliceRepository",
                        description="use the port",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner()
        registry = FakeAgentRunnerRegistry(agent_runner)
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=registry,
            agent_profiles=FakeAgentProfiles([_reviewer(engine="opencode")]),
            review_task=ReviewTask(StoryJournalSection(_query_bus())),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(ReviewPullRequestCommand(slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo"))

        assert registry.requested_engines == ["opencode"]
        assert agent_runner.dispatched_count == 1

    def test_does_not_dispatch_when_the_reviewer_profile_is_missing(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        title="implement the SliceRepository",
                        description="use the port",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner()
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles(),
            review_task=ReviewTask(StoryJournalSection(_query_bus())),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(ReviewPullRequestCommand(slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo"))

        assert agent_runner.dispatched_count == 0
        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.status == SliceStatus.DISPATCHED

    def test_is_idempotent_when_slice_is_not_reviewable(self) -> None:
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.PR_OPEN)
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        agent_runner = FakeAgentRunner()
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(_query_bus())),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(ReviewPullRequestCommand(slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo"))

        assert agent_runner.dispatched_count == 0
        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.status == SliceStatus.PR_OPEN

    def test_does_nothing_when_slice_is_missing(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): []})
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(FakeAgentRunner()),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(_query_bus())),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(ReviewPullRequestCommand(slice_id="99", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo"))

        assert repository.find(SliceId("99")) is None

    def test_reviews_a_corrected_slice_again(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_corrected_slice()]})
        agent_runner = FakeAgentRunner()
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(_query_bus())),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(ReviewPullRequestCommand(slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo"))

        assert agent_runner.dispatched_count == 1
        assert agent_runner.last_task_type == AgentTaskType.REVIEW_SLICE
        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.status == SliceStatus.UNDER_REVIEW

    def test_keeps_the_pull_request_already_anchored_and_the_rounds_spent(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_corrected_slice()]})
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(FakeAgentRunner()),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(_query_bus())),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(ReviewPullRequestCommand(slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo"))

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.pull_request is not None
        assert result.pull_request.number.value == 99
        assert result.review_rounds == 1

    def test_addresses_the_pull_request_number_anchored_on_the_slice(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_corrected_slice(pull_request_number=99)]})
        agent_runner = FakeAgentRunner()
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(_query_bus())),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(ReviewPullRequestCommand(slice_id="12", pull_request_number=42, workdir="/tmp/wd", repo="owner/repo"))

        assert "#99" in agent_runner.last_instruction
        assert "#42" not in agent_runner.last_instruction

    def test_clears_the_verdict_of_the_previous_round(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_corrected_slice()]})
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(FakeAgentRunner()),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(_query_bus())),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(ReviewPullRequestCommand(slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo"))

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.review_verdict == ReviewVerdict.EMPTY


class TestReviewPullRequestCommandHandlerJournal:
    def test_dispatches_with_the_story_id_and_profile_of_the_slice(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        story_id="10",
                        title="implement the SliceRepository",
                        description="use the port",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner()
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(_query_bus())),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(ReviewPullRequestCommand(slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo"))

        assert agent_runner.last_story_id == "10"
        assert agent_runner.last_profile == "reviewer"

    def test_dispatches_without_story_id_when_the_slice_has_no_story(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        title="implement the SliceRepository",
                        description="use the port",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner()
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(_query_bus())),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(ReviewPullRequestCommand(slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo"))

        assert agent_runner.last_story_id is None
        assert agent_runner.last_profile == "reviewer"

    def test_includes_the_journal_entries_and_instructions_when_enabled(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        story_id="10",
                        title="implement the SliceRepository",
                        description="use the port",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner()
        query_bus = _query_bus(
            journal_entries=[
                JournalEntryDTO(
                    kind="constraint",
                    author="reviewer",
                    body="do not change the SliceRepository contract",
                    written_at="2026-09-10T12:00:00+00:00",
                )
            ]
        )
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(query_bus)),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(
            ReviewPullRequestCommand(
                slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo", journal_enabled=True
            )
        )

        instruction = agent_runner.last_instruction
        assert "grooveloop note" in instruction
        assert "Story journal" in instruction
        assert "do not change the SliceRepository contract" in instruction
        assert ReadJournalEntriesQuery(repo="owner/repo", story_id="10") in query_bus.asked

    def test_journal_instructions_precede_the_verdict_steps(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        story_id="10",
                        title="implement the SliceRepository",
                        description="use the port",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner()
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(_query_bus())),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(
            ReviewPullRequestCommand(
                slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo", journal_enabled=True
            )
        )

        instruction = agent_runner.last_instruction
        assert instruction.index("grooveloop note") < instruction.index("TWO STEPS")

    def test_journal_instructions_forbid_the_directive_kind(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        story_id="10",
                        title="implement the SliceRepository",
                        description="use the port",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner()
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(_query_bus())),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(
            ReviewPullRequestCommand(
                slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo", journal_enabled=True
            )
        )

        assert "Do not use the kind `directive`" in agent_runner.last_instruction

    def test_does_not_include_journal_sections_when_disabled(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        story_id="10",
                        title="implement the SliceRepository",
                        description="use the port",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner()
        query_bus = _query_bus(
            journal_entries=[
                JournalEntryDTO(
                    kind="constraint",
                    author="reviewer",
                    body="do not change anything",
                    written_at="2026-09-10T12:00:00+00:00",
                )
            ]
        )
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(query_bus)),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(ReviewPullRequestCommand(slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo"))

        instruction = agent_runner.last_instruction
        assert "grooveloop note" not in instruction
        assert "## Story journal" not in instruction
        assert query_bus.asked == []

    def test_does_not_include_journal_sections_when_the_slice_has_no_story(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        title="implement the SliceRepository",
                        description="use the port",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner()
        query_bus = _query_bus()
        handler = ReviewPullRequestCommandHandler(
            slice_repository=repository,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(query_bus)),
            directive_marker=FakeDirectiveMarker(),
        )

        handler(
            ReviewPullRequestCommand(
                slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo", journal_enabled=True
            )
        )

        instruction = agent_runner.last_instruction
        assert "grooveloop note" not in instruction
        assert "## Story journal" not in instruction
        assert query_bus.asked == []


def _directive(day: int, marks: frozenset[DirectiveMark] = frozenset()) -> ReviewComment:
    return ReviewComment(
        body=f"/grooveloop-implement: change number {day}",
        created_at=datetime(2026, 6, day, tzinfo=UTC),
        directives=frozenset({CommentDirective.IMPLEMENT}),
        id=f"comment-{day}",
        marks=marks,
    )


class TestReviewPullRequestCommandHandlerDirectiveMarks:
    def _handler(self, a_slice: Slice, marker: FakeDirectiveMarker) -> ReviewPullRequestCommandHandler:
        return ReviewPullRequestCommandHandler(
            slice_repository=FakeSliceRepository({StoryId("10"): [a_slice]}),
            agent_runner_registry=FakeAgentRunnerRegistry(FakeAgentRunner()),
            agent_profiles=FakeAgentProfiles([_reviewer()]),
            review_task=ReviewTask(StoryJournalSection(_query_bus())),
            directive_marker=marker,
        )

    def test_marks_the_taken_directives_as_addressed_when_the_correction_goes_back_to_the_reviewer(self) -> None:
        taken = frozenset({DirectiveMark.TAKEN})
        addressed = frozenset({DirectiveMark.TAKEN, DirectiveMark.ADDRESSED})
        marker = FakeDirectiveMarker()
        a_slice = SliceMother.create(
            slice_id="12",
            status=SliceStatus.CHANGES_REQUESTED,
            pull_request=PullRequest(
                number=PullRequestNumber(99),
                comments=[_directive(2, addressed), _directive(3, taken), _directive(5)],
                last_commit_at=datetime(2026, 6, 4, tzinfo=UTC),
            ),
        )

        self._handler(a_slice, marker)(
            ReviewPullRequestCommand(slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo")
        )

        assert marker.marked[DirectiveMark.ADDRESSED] == [_directive(3, taken)]
        assert marker.marked[DirectiveMark.TAKEN] == []

    def test_marks_no_directive_on_the_first_review_of_the_pull_request(self) -> None:
        marker = FakeDirectiveMarker()
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.DISPATCHED)

        self._handler(a_slice, marker)(
            ReviewPullRequestCommand(slice_id="12", pull_request_number=99, workdir="/tmp/wd", repo="owner/repo")
        )

        assert marker.calls == []
