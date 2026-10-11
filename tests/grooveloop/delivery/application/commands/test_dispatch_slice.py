from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from grooveloop.delivery.application.commands.dispatch_slice import (
    DispatchSliceCommand,
    DispatchSliceCommandHandler,
)
from grooveloop.delivery.application.tasks.implementation_task import ImplementationTask
from grooveloop.delivery.application.tasks.story_journal_section import StoryJournalSection
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_labels import SliceLabels
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.shared.application.queries.get_story_spec import GetStorySpecQuery, GetStorySpecQueryResult
from grooveloop.shared.application.queries.read_journal_entries import (
    JournalEntryDTO,
    ReadJournalEntriesQuery,
    ReadJournalEntriesQueryResult,
)
from grooveloop.shared.domain.agent_profile import AgentProfile
from grooveloop.shared.domain.agent_task_type import AgentTaskType
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_agent_profiles import FakeAgentProfiles
from tests.playground.shared.infrastructure.fake_agent_runner import FakeAgentRunner
from tests.playground.shared.infrastructure.fake_agent_runner_registry import FakeAgentRunnerRegistry
from tests.playground.shared.infrastructure.fake_query_bus import FakeQueryBus
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository

if TYPE_CHECKING:
    from grooveloop.shared.application.queries.query_bus import QueryBus
    from grooveloop.shared.domain.agent_profiles import AgentProfiles

_STARTED_STATUSES = [
    SliceStatus.DISPATCHED,
    SliceStatus.UNDER_REVIEW,
    SliceStatus.PR_OPEN,
    SliceStatus.CHANGES_REQUESTED,
    SliceStatus.BLOCKED,
]


def _query_bus(spec_text: str, journal_entries: list[JournalEntryDTO] | None = None) -> FakeQueryBus:
    return FakeQueryBus(
        {
            GetStorySpecQuery: lambda _query: GetStorySpecQueryResult(spec_text=spec_text),
            ReadJournalEntriesQuery: lambda _query: ReadJournalEntriesQueryResult(entries=journal_entries or []),
        }
    )


def _developer(
    model: str = "opus",
    persona: str = "create and run a plan with superpowers",
    engine: str = "claude",
) -> AgentProfile:
    return AgentProfile(name="developer", engine=engine, model=model, skills=[], context_files=[], persona=persona)


def _handler(
    repository: FakeSliceRepository,
    agent_runner_registry: FakeAgentRunnerRegistry,
    query_bus: QueryBus,
    agent_profiles: AgentProfiles,
    slice_labels: SliceLabels | None = None,
) -> DispatchSliceCommandHandler:
    return DispatchSliceCommandHandler(
        slice_repository=repository,
        agent_runner_registry=agent_runner_registry,
        agent_profiles=agent_profiles,
        slice_labels=slice_labels or create_autospec(SliceLabels, spec_set=True, instance=True),
        implementation_task=ImplementationTask(query_bus, StoryJournalSection(query_bus)),
    )


class TestDispatchSliceCommandHandler:
    def test_should_ensure_the_slice_label_before_the_agent_starts(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10")]}
        )
        agent_runner = FakeAgentRunner()
        slice_labels: Mock = create_autospec(SliceLabels, spec_set=True, instance=True)
        dispatched_when_ensured: list[int] = []
        slice_labels.ensure.side_effect = lambda _: dispatched_when_ensured.append(agent_runner.dispatched_count)
        handler = _handler(
            repository,
            FakeAgentRunnerRegistry(agent_runner),
            _query_bus(""),
            FakeAgentProfiles([_developer()]),
            slice_labels,
        )

        handler(DispatchSliceCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        slice_labels.ensure.assert_called_once_with(SliceId("12"))
        assert dispatched_when_ensured == [0]
        assert agent_runner.dispatched_count == 1

    def test_should_ask_for_the_pull_request_with_the_slice_label(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10")]}
        )
        agent_runner = FakeAgentRunner()
        handler = _handler(
            repository, FakeAgentRunnerRegistry(agent_runner), _query_bus(""), FakeAgentProfiles([_developer()])
        )

        handler(DispatchSliceCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        assert "`gh pr create --label grooveloop --label slice:12`" in agent_runner.last_instruction

    def test_should_dispatch_the_pending_slice_with_task_and_persona(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(slice_id="11", status=SliceStatus.MERGED, story_id="10"),
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.PENDING,
                        story_id="10",
                        title="implement the SliceRepository",
                        description="use the SliceRepository port",
                    ),
                ]
            }
        )
        agent_runner = FakeAgentRunner()
        handler = _handler(
            repository,
            FakeAgentRunnerRegistry(agent_runner),
            _query_bus(spec_text="## Goal\nclose the v1 flow"),
            FakeAgentProfiles([_developer()]),
        )

        handler(DispatchSliceCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        stored = repository.find(SliceId("12"))
        assert stored is not None
        assert stored.status == SliceStatus.DISPATCHED
        assert agent_runner.dispatched_count == 1
        assert agent_runner.last_slice_id == "12"
        assert agent_runner.last_repo == "owner/repo"
        assert agent_runner.last_model == "opus"
        assert "create and run a plan with superpowers" in agent_runner.last_instruction
        assert "implement the SliceRepository" in agent_runner.last_instruction
        assert "close the v1 flow" in agent_runner.last_instruction
        assert "use the SliceRepository port" in agent_runner.last_instruction
        assert "Closes #12" in agent_runner.last_instruction
        assert "grooveloop" in agent_runner.last_instruction
        assert "autonomous mode" in agent_runner.last_instruction

    def test_should_dispatch_with_the_story_id_and_profile_of_the_slice(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10")]}
        )
        agent_runner = FakeAgentRunner()
        handler = _handler(
            repository, FakeAgentRunnerRegistry(agent_runner), _query_bus(""), FakeAgentProfiles([_developer()])
        )

        handler(DispatchSliceCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        assert agent_runner.last_story_id == "10"
        assert agent_runner.last_profile == "developer"

    def test_should_dispatch_with_the_model_from_the_resolved_profile(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10")]}
        )
        agent_runner = FakeAgentRunner()
        handler = _handler(
            repository,
            FakeAgentRunnerRegistry(agent_runner),
            _query_bus(""),
            FakeAgentProfiles([_developer(model="sonnet")]),
        )

        handler(DispatchSliceCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        assert agent_runner.last_model == "sonnet"

    def test_should_not_dispatch_when_the_developer_profile_is_missing(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10")]}
        )
        agent_runner = FakeAgentRunner()
        handler = _handler(repository, FakeAgentRunnerRegistry(agent_runner), _query_bus(""), FakeAgentProfiles())

        handler(DispatchSliceCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        assert agent_runner.dispatched_count == 0

    def test_should_persist_the_agent_run_id_on_the_dispatched_slice(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10")]}
        )
        agent_runner = FakeAgentRunner()
        handler = _handler(
            repository, FakeAgentRunnerRegistry(agent_runner), _query_bus(""), FakeAgentProfiles([_developer()])
        )

        handler(DispatchSliceCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        stored = repository.find(SliceId("12"))
        assert stored is not None
        assert stored.agent_run_id == "fake-run"

    def test_should_dispatch_with_the_implement_slice_task_type(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10")]}
        )
        agent_runner = FakeAgentRunner()
        handler = _handler(
            repository, FakeAgentRunnerRegistry(agent_runner), _query_bus(""), FakeAgentProfiles([_developer()])
        )

        handler(DispatchSliceCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        assert agent_runner.last_task_type == AgentTaskType.IMPLEMENT_SLICE

    def test_should_dispatch_with_the_runner_of_the_profile_engine(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10")]}
        )
        agent_runner = FakeAgentRunner()
        registry = FakeAgentRunnerRegistry(agent_runner)
        handler = _handler(repository, registry, _query_bus(""), FakeAgentProfiles([_developer(engine="opencode")]))

        handler(DispatchSliceCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        assert registry.requested_engines == ["opencode"]
        assert agent_runner.dispatched_count == 1

    def test_should_not_dispatch_a_slice_that_is_no_longer_pending(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.DISPATCHED, story_id="10")]}
        )
        agent_runner = FakeAgentRunner()
        handler = _handler(
            repository, FakeAgentRunnerRegistry(agent_runner), _query_bus(""), FakeAgentProfiles([_developer()])
        )

        handler(DispatchSliceCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        assert agent_runner.dispatched_count == 0

    def test_should_not_dispatch_an_unknown_slice(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10")]}
        )
        agent_runner = FakeAgentRunner()
        handler = _handler(
            repository, FakeAgentRunnerRegistry(agent_runner), _query_bus(""), FakeAgentProfiles([_developer()])
        )

        handler(DispatchSliceCommand(slice_id="99", workdir="/tmp/wd", repo="owner/repo"))

        assert agent_runner.dispatched_count == 0

    @pytest.mark.parametrize("status", _STARTED_STATUSES)
    def test_should_refuse_to_dispatch_when_a_started_slice_fills_the_parallel_limit(self, status: SliceStatus) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(slice_id="11", status=status, story_id="10"),
                    SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10"),
                ]
            }
        )
        agent_runner = FakeAgentRunner()
        handler = _handler(
            repository, FakeAgentRunnerRegistry(agent_runner), _query_bus(""), FakeAgentProfiles([_developer()])
        )

        handler(DispatchSliceCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo", max_parallel_slices=1))

        assert agent_runner.dispatched_count == 0
        stored = repository.find(SliceId("12"))
        assert stored is not None
        assert stored.status == SliceStatus.PENDING

    @pytest.mark.parametrize("status", [SliceStatus.PENDING, SliceStatus.MERGED, SliceStatus.FAILED])
    def test_should_dispatch_when_the_other_slice_has_not_started_or_has_finished(self, status: SliceStatus) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(slice_id="11", status=status, story_id="10"),
                    SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10"),
                ]
            }
        )
        agent_runner = FakeAgentRunner()
        handler = _handler(
            repository, FakeAgentRunnerRegistry(agent_runner), _query_bus(""), FakeAgentProfiles([_developer()])
        )

        handler(DispatchSliceCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo", max_parallel_slices=1))

        assert agent_runner.dispatched_count == 1
        assert agent_runner.last_slice_id == "12"

    @pytest.mark.parametrize(("max_parallel_slices", "dispatched_count"), [(5, 0), (6, 1)])
    def test_should_count_only_the_started_slices_against_the_parallel_limit(
        self, max_parallel_slices: int, dispatched_count: int
    ) -> None:
        started = [
            SliceMother.create(slice_id=str(20 + index), status=status, story_id="10")
            for index, status in enumerate(_STARTED_STATUSES)
        ]
        not_counted = [
            SliceMother.create(slice_id="30", status=SliceStatus.PENDING, story_id="10"),
            SliceMother.create(slice_id="31", status=SliceStatus.MERGED, story_id="10"),
            SliceMother.create(slice_id="32", status=SliceStatus.FAILED, story_id="10"),
        ]
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    *started,
                    *not_counted,
                    SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10"),
                ]
            }
        )
        agent_runner = FakeAgentRunner()
        handler = _handler(
            repository, FakeAgentRunnerRegistry(agent_runner), _query_bus(""), FakeAgentProfiles([_developer()])
        )

        handler(
            DispatchSliceCommand(
                slice_id="12", workdir="/tmp/wd", repo="owner/repo", max_parallel_slices=max_parallel_slices
            )
        )

        assert agent_runner.dispatched_count == dispatched_count

    def test_should_ask_to_wait_in_the_foreground_for_long_commands(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10")]}
        )
        agent_runner = FakeAgentRunner()
        handler = _handler(
            repository, FakeAgentRunnerRegistry(agent_runner), _query_bus(""), FakeAgentProfiles([_developer()])
        )

        handler(DispatchSliceCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo"))

        assert "wait in the foreground" in agent_runner.last_instruction

    def test_should_include_the_journal_entries_in_the_prompt_when_enabled(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10")]}
        )
        agent_runner = FakeAgentRunner()
        query_bus = _query_bus(
            "",
            journal_entries=[
                JournalEntryDTO(
                    kind="constraint",
                    author="human",
                    body="do not touch the legacy client",
                    written_at="2026-09-10T12:00:00+00:00",
                )
            ],
        )
        handler = _handler(
            repository,
            FakeAgentRunnerRegistry(agent_runner),
            query_bus,
            FakeAgentProfiles([_developer()]),
        )

        handler(DispatchSliceCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo", journal_enabled=True))

        assert "Story journal" in agent_runner.last_instruction
        assert "do not touch the legacy client" in agent_runner.last_instruction
        assert "2026-09-10T12:00:00+00:00" in agent_runner.last_instruction
        assert ReadJournalEntriesQuery(repo="owner/repo", story_id="10") in query_bus.asked

    def test_should_not_include_the_journal_section_when_disabled(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10")]}
        )
        agent_runner = FakeAgentRunner()
        query_bus = _query_bus(
            "",
            journal_entries=[
                JournalEntryDTO(
                    kind="constraint",
                    author="human",
                    body="do not touch the legacy client",
                    written_at="2026-09-10T12:00:00+00:00",
                )
            ],
        )
        handler = _handler(
            repository,
            FakeAgentRunnerRegistry(agent_runner),
            query_bus,
            FakeAgentProfiles([_developer()]),
        )

        handler(DispatchSliceCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo", journal_enabled=False))

        assert "## Story journal" not in agent_runner.last_instruction
        assert ReadJournalEntriesQuery(repo="owner/repo", story_id="10") not in query_bus.asked

    def test_should_not_include_an_empty_journal_section_when_the_story_has_no_entries(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10")]}
        )
        agent_runner = FakeAgentRunner()
        handler = _handler(
            repository,
            FakeAgentRunnerRegistry(agent_runner),
            _query_bus("", journal_entries=[]),
            FakeAgentProfiles([_developer()]),
        )

        handler(DispatchSliceCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo", journal_enabled=True))

        assert "## Story journal" not in agent_runner.last_instruction

    def test_should_include_the_journal_usage_instructions_when_enabled(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10")]}
        )
        agent_runner = FakeAgentRunner()
        handler = _handler(
            repository,
            FakeAgentRunnerRegistry(agent_runner),
            _query_bus(""),
            FakeAgentProfiles([_developer()]),
        )

        handler(DispatchSliceCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo", journal_enabled=True))

        assert "grooveloop note" in agent_runner.last_instruction
        assert "grooveloop journal" in agent_runner.last_instruction

    def test_should_tell_that_rereading_the_journal_only_brings_the_new_entries(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10")]}
        )
        agent_runner = FakeAgentRunner()
        handler = _handler(
            repository,
            FakeAgentRunnerRegistry(agent_runner),
            _query_bus(""),
            FakeAgentProfiles([_developer()]),
        )

        handler(DispatchSliceCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo", journal_enabled=True))

        assert "only brings the entries written after your run started" in agent_runner.last_instruction

    def test_should_not_include_the_journal_usage_instructions_when_disabled(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.PENDING, story_id="10")]}
        )
        agent_runner = FakeAgentRunner()
        handler = _handler(
            repository,
            FakeAgentRunnerRegistry(agent_runner),
            _query_bus(""),
            FakeAgentProfiles([_developer()]),
        )

        handler(DispatchSliceCommand(slice_id="12", workdir="/tmp/wd", repo="owner/repo", journal_enabled=False))

        assert "grooveloop note" not in agent_runner.last_instruction
        assert "grooveloop journal" not in agent_runner.last_instruction
