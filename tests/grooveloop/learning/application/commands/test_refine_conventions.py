from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import create_autospec

from grooveloop.learning.application.commands.refine_conventions import (
    RefineConventionsCommand,
    RefineConventionsCommandHandler,
)
from grooveloop.learning.application.tasks.refinement_task import RefinementTask
from grooveloop.learning.domain.lesson_comment_marker import LessonCommentMarker
from grooveloop.learning.domain.lesson_status import LessonStatus
from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from grooveloop.learning.domain.story_id import StoryId
from grooveloop.shared.domain.agent_profile import AgentProfile
from grooveloop.shared.domain.agent_task_type import AgentTaskType
from tests.grooveloop.learning.mothers.lesson_mother import LessonMother
from tests.playground.shared.infrastructure.clock import clock_at
from tests.playground.shared.infrastructure.fake_agent_profiles import FakeAgentProfiles
from tests.playground.shared.infrastructure.fake_agent_runner import FakeAgentRunner
from tests.playground.shared.infrastructure.fake_agent_runner_registry import FakeAgentRunnerRegistry
from tests.playground.shared.infrastructure.fake_lesson_repository import FakeLessonRepository

_NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


def _scribe(
    model: str = "opus",
    persona: str = "you are the scribe of the loop",
    engine: str = "claude",
) -> AgentProfile:
    return AgentProfile(name="scribe", engine=engine, model=model, skills=[], context_files=[], persona=persona)


def _command() -> RefineConventionsCommand:
    return RefineConventionsCommand(
        source_pull_request=42,
        story_id="277",
        comments=[
            {
                "body": "/grooveloop-learn: here we inject through the constructor, not with getters",
                "path": "src/x.py",
                "line": 10,
                "diff_hunk": "@@ -1 +1 @@\n-old\n+new",
                "id": "IC_1",
                "written_at": datetime(2026, 1, 1, tzinfo=UTC),
            },
            {
                "body": "/grooveloop-learn: also name the fake FakeThing",
                "path": "src/y.py",
                "line": 3,
                "diff_hunk": "",
                "id": "IC_2",
                "written_at": datetime(2026, 1, 2, tzinfo=UTC),
            },
        ],
        workdir="/tmp/wd",
        repo="owner/repo",
    )


class TestRefineConventionsCommandHandler:
    def test_dispatches_the_scribe_with_refine_conventions_task_type(self) -> None:
        agent_runner = FakeAgentRunner()
        handler = RefineConventionsCommandHandler(
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_scribe()]),
            lesson_repository=FakeLessonRepository(),
            refinement_task=RefinementTask(),
            clock=clock_at(_NOW),
            lesson_comment_marker=create_autospec(LessonCommentMarker, spec_set=True, instance=True),
        )

        handler(_command())

        assert agent_runner.dispatched_count == 1
        assert agent_runner.last_task_type == AgentTaskType.REFINE_CONVENTIONS
        assert agent_runner.last_workdir == "/tmp/wd"
        assert agent_runner.last_repo == "owner/repo"
        assert agent_runner.last_model == "opus"

    def test_the_task_aggregates_every_learn_comment(self) -> None:
        agent_runner = FakeAgentRunner()
        handler = RefineConventionsCommandHandler(
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_scribe()]),
            lesson_repository=FakeLessonRepository(),
            refinement_task=RefinementTask(),
            clock=clock_at(_NOW),
            lesson_comment_marker=create_autospec(LessonCommentMarker, spec_set=True, instance=True),
        )

        handler(_command())

        assert "we inject through the constructor" in agent_runner.last_instruction
        assert "name the fake FakeThing" in agent_runner.last_instruction
        assert "#42" in agent_runner.last_instruction
        assert "src/x.py:10" in agent_runner.last_instruction

    def test_the_task_carries_the_discard_marker_and_the_lesson_link(self) -> None:
        agent_runner = FakeAgentRunner()
        handler = RefineConventionsCommandHandler(
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_scribe()]),
            lesson_repository=FakeLessonRepository(),
            refinement_task=RefinementTask(),
            clock=clock_at(_NOW),
            lesson_comment_marker=create_autospec(LessonCommentMarker, spec_set=True, instance=True),
        )

        handler(_command())

        assert "<!-- grooveloop:learned discarded -->" in agent_runner.last_instruction
        assert "<!-- grooveloop:lesson pr=42 -->" in agent_runner.last_instruction

    def test_the_task_tells_the_scribe_not_to_manage_the_lesson_sub_issue_state(self) -> None:
        agent_runner = FakeAgentRunner()
        handler = RefineConventionsCommandHandler(
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_scribe()]),
            lesson_repository=FakeLessonRepository(),
            refinement_task=RefinementTask(),
            clock=clock_at(_NOW),
            lesson_comment_marker=create_autospec(LessonCommentMarker, spec_set=True, instance=True),
        )

        handler(_command())

        instruction = agent_runner.last_instruction
        assert "sub-issue" in instruction
        assert "reconciles" in instruction

    def test_the_task_instructs_the_full_git_flow(self) -> None:
        agent_runner = FakeAgentRunner()
        handler = RefineConventionsCommandHandler(
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_scribe()]),
            lesson_repository=FakeLessonRepository(),
            refinement_task=RefinementTask(),
            clock=clock_at(_NOW),
            lesson_comment_marker=create_autospec(LessonCommentMarker, spec_set=True, instance=True),
        )

        handler(_command())

        instruction = agent_runner.last_instruction
        assert "git checkout -b" in instruction
        assert "git commit" in instruction
        assert "git push" in instruction
        assert "gh pr create --label grooveloop" in instruction

    def test_saves_the_lesson_in_progress_after_dispatching(self) -> None:
        agent_runner = FakeAgentRunner()
        lesson_repository = FakeLessonRepository()
        handler = RefineConventionsCommandHandler(
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_scribe()]),
            lesson_repository=lesson_repository,
            refinement_task=RefinementTask(),
            clock=clock_at(_NOW),
            lesson_comment_marker=create_autospec(LessonCommentMarker, spec_set=True, instance=True),
        )

        handler(_command())

        assert len(lesson_repository.saved) == 1
        saved = lesson_repository.saved[0]
        assert saved.source_pull_request.value == 42
        assert saved.story_id == StoryId("277")
        assert saved.status == LessonStatus.IN_PROGRESS
        assert len(saved.comments) == 2
        assert saved.captured_at == _NOW

    def test_dispatches_with_the_runner_of_the_profile_engine(self) -> None:
        agent_runner = FakeAgentRunner()
        registry = FakeAgentRunnerRegistry(agent_runner)
        handler = RefineConventionsCommandHandler(
            agent_runner_registry=registry,
            agent_profiles=FakeAgentProfiles([_scribe(engine="opencode")]),
            lesson_repository=FakeLessonRepository(),
            refinement_task=RefinementTask(),
            clock=clock_at(_NOW),
            lesson_comment_marker=create_autospec(LessonCommentMarker, spec_set=True, instance=True),
        )

        handler(_command())

        assert registry.requested_engines == ["opencode"]
        assert agent_runner.dispatched_count == 1

    def test_does_not_dispatch_or_save_when_the_scribe_profile_is_missing(self) -> None:
        agent_runner = FakeAgentRunner()
        lesson_repository = FakeLessonRepository()
        handler = RefineConventionsCommandHandler(
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles(),
            lesson_repository=lesson_repository,
            refinement_task=RefinementTask(),
            clock=clock_at(_NOW),
            lesson_comment_marker=create_autospec(LessonCommentMarker, spec_set=True, instance=True),
        )

        handler(_command())

        assert agent_runner.dispatched_count == 0
        assert lesson_repository.saved == []

    def test_does_not_dispatch_or_save_again_while_the_pull_request_has_a_lesson_in_progress(self) -> None:
        agent_runner = FakeAgentRunner()
        lesson_repository = FakeLessonRepository()
        handler = RefineConventionsCommandHandler(
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_scribe()]),
            lesson_repository=lesson_repository,
            refinement_task=RefinementTask(),
            clock=clock_at(_NOW),
            lesson_comment_marker=create_autospec(LessonCommentMarker, spec_set=True, instance=True),
        )
        handler(_command())

        handler(_command())

        assert agent_runner.dispatched_count == 1
        assert len(lesson_repository.saved) == 1

    def test_captures_a_new_lesson_for_a_pull_request_whose_previous_lesson_is_resolved(self) -> None:
        agent_runner = FakeAgentRunner()
        previous = LessonMother.create(lesson_id="400", source_pull_request=42, status=LessonStatus.LEARNED)
        lesson_repository = FakeLessonRepository(lessons=[previous])
        handler = RefineConventionsCommandHandler(
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles([_scribe()]),
            lesson_repository=lesson_repository,
            refinement_task=RefinementTask(),
            clock=clock_at(_NOW),
            lesson_comment_marker=create_autospec(LessonCommentMarker, spec_set=True, instance=True),
        )

        handler(_command())

        assert agent_runner.dispatched_count == 1
        assert [lesson.status for lesson in lesson_repository.search(source_pull_request=SourcePullRequest(42))] == [
            LessonStatus.LEARNED,
            LessonStatus.IN_PROGRESS,
        ]

    def test_marks_as_captured_every_learn_comment_the_lesson_includes(self) -> None:
        marker = create_autospec(LessonCommentMarker, spec_set=True, instance=True)
        handler = RefineConventionsCommandHandler(
            agent_runner_registry=FakeAgentRunnerRegistry(FakeAgentRunner()),
            agent_profiles=FakeAgentProfiles([_scribe()]),
            lesson_repository=FakeLessonRepository(),
            refinement_task=RefinementTask(),
            clock=clock_at(_NOW),
            lesson_comment_marker=marker,
        )

        handler(_command())

        marker.mark_captured.assert_called_once()
        assert [comment.id for comment in marker.mark_captured.call_args.args[0]] == ["IC_1", "IC_2"]

    def test_marks_nothing_when_the_scribe_profile_is_missing(self) -> None:
        marker = create_autospec(LessonCommentMarker, spec_set=True, instance=True)
        handler = RefineConventionsCommandHandler(
            agent_runner_registry=FakeAgentRunnerRegistry(FakeAgentRunner()),
            agent_profiles=FakeAgentProfiles(),
            lesson_repository=FakeLessonRepository(),
            refinement_task=RefinementTask(),
            clock=clock_at(_NOW),
            lesson_comment_marker=marker,
        )

        handler(_command())

        marker.mark_captured.assert_not_called()
