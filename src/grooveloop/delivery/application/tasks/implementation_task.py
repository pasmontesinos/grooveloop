from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.application.queries.get_story_spec import GetStorySpecQuery

if TYPE_CHECKING:
    from grooveloop.delivery.application.tasks.story_journal_section import StoryJournalSection
    from grooveloop.delivery.domain.slice import Slice
    from grooveloop.shared.application.queries.query_bus import QueryBus


class ImplementationTask:
    def __init__(self, query_bus: QueryBus, story_journal_section: StoryJournalSection) -> None:
        self._query_bus = query_bus
        self._story_journal_section = story_journal_section

    def build(self, a_slice: Slice, repo: str, journal_enabled: bool, previous_branch: str | None = None) -> str:
        assert a_slice.story_id is not None
        story_id = a_slice.story_id.value
        spec = self._query_bus.ask(GetStorySpecQuery(story_id=story_id))
        spec_text = spec.spec_text if spec is not None else ""

        return (
            f'Implement the slice "{a_slice.title}" of spec #{story_id} and open a Pull Request '
            f'when you finish, including "Closes #{a_slice.id.value}" in its description. '
            f'Create the Pull Request with the labels "grooveloop" and "slice:{a_slice.id.value}" '
            f"(`gh pr create --label grooveloop --label slice:{a_slice.id.value}`).\n\n"
            "You work in autonomous mode: there is no human in the loop. Do not ask questions or wait for "
            "confirmation; pick reasonable defaults and finish when you open the Pull Request.\n\n"
            f"{self._previous_attempt_section(previous_branch)}"
            f"{self._journal_instructions_section(journal_enabled)}"
            f"{self._journal_entries_section(journal_enabled, repo, story_id)}"
            f"## Change specification\n{spec_text}\n\n"
            f"## Slice to implement: {a_slice.title}\n{a_slice.description}"
        )

    def resumption(self, a_slice: Slice) -> str:
        return (
            f'Your previous turn ended without opening the Pull Request of the slice "{a_slice.title}". '
            "Continue in this same worktree from where you left off: finish the work, push the branch and open "
            f'the Pull Request including "Closes #{a_slice.id.value}" in its description '
            f"(`gh pr create --label grooveloop --label slice:{a_slice.id.value}`). "
            "If the Pull Request already exists, do not open another one. Do not run commands in the background or "
            "end your turn waiting for a task: wait in the foreground for long commands. You work in autonomous "
            "mode: do not ask questions and finish when you open the Pull Request."
        )

    def _previous_attempt_section(self, previous_branch: str | None) -> str:
        if previous_branch is None:
            return ""

        return (
            "## Previous attempt\n"
            f"A previous attempt at this slice was interrupted and left its work on the branch `{previous_branch}` "
            f"of `origin`. Start from that branch (`git fetch origin {previous_branch}`) instead of starting from "
            "scratch, review what it already did and finish the work.\n\n"
        )

    def _journal_instructions_section(self, journal_enabled: bool) -> str:
        if not journal_enabled:
            return ""

        return (
            'Use `grooveloop note --kind <constraint|directive|decision|finding> "..."` to record in the '
            "Story journal the rules the following slices must respect, the decisions you make when facing an "
            "ambiguity and the findings about the system that the Spec did not mention. You do not need to pass "
            "`--repo` or `--story`: the command resolves them from your run.\n\n"
            "Reread the journal with `grooveloop journal` (it does not need `--repo` or `--story` either: it "
            "resolves them like `note`) at these three checkpoints: before planning, before implementing, and "
            "before opening the Pull Request. The reread only brings the entries written after your run started: "
            "the earlier ones are already in this prompt. An entry of kind `directive` whose timestamp is later "
            "than the start of your run overrides the plan in progress: adjust your work to it before "
            "continuing.\n\n"
        )

    def _journal_entries_section(self, journal_enabled: bool, repo: str, story_id: str) -> str:
        if not journal_enabled:
            return ""

        return self._story_journal_section.build(repo, story_id)
