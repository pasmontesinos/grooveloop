from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.delivery.application.tasks.story_journal_section import StoryJournalSection
    from grooveloop.delivery.domain.slice import Slice


class ReviewTask:
    def __init__(self, story_journal_section: StoryJournalSection) -> None:
        self._story_journal_section = story_journal_section

    def build(self, a_slice: Slice, pull_request_number: int, repo: str, journal_enabled: bool) -> str:
        return (
            f'Review the Pull Request #{pull_request_number} of the slice "{a_slice.title}". '
            "Get the diff with `gh pr diff` and compare it with the title and the description of the slice.\n\n"
            "You work in autonomous mode: there is no human in the loop. Do not ask questions or wait for "
            "confirmation.\n\n"
            "You only annotate: do not fix code, do not push, do not approve, do not merge or close the Pull "
            "Request; the decision belongs to the human.\n\n"
            f"{self._journal_instructions_section(a_slice, journal_enabled)}"
            f"{self._journal_entries_section(a_slice, repo, journal_enabled)}"
            "Close the review in TWO STEPS AND IN THIS ORDER.\n\n"
            "STEP 1, the label. Declare your verdict in a label on the sub-issue of the slice, with "
            f"`gh issue edit {a_slice.id.value} --add-label review:<verdict>`. Write EXACTLY ONE, with one "
            "of these four values:\n\n"
            "- `review:approve`: there are no findings to fix.\n"
            "- `review:minor`: there are only minor findings that do not require touching the code.\n"
            "- `review:blocking`: there is at least one serious finding and fixing it requires no human decision.\n"
            "- `review:blocked`: there is at least one finding that requires a human decision.\n\n"
            "A finding requires a human decision only if it meets one of these four triggers:\n\n"
            "1. There are two or more valid ways out and choosing one fixes a design decision.\n"
            "2. The fix goes beyond the declared scope of the slice.\n"
            "3. The fix contradicts an ADR or the spec itself.\n"
            "4. The fix touches CI, infra or dependencies shared by the whole repo.\n\n"
            "Outside that list the verdict is `review:blocking`. Blocked wins: if the same review brings "
            "fixable findings and one that requires a decision, the verdict is `review:blocked`.\n\n"
            "STEP 2, the comment. Only when the label is already written, leave EXACTLY ONE summary comment "
            f"in the conversation of the Pull Request (`gh pr comment {pull_request_number}`) with your verdict "
            "(you would approve / you would request changes) and the main findings, and END it with the marker on "
            "its own line: `<!-- grooveloop:review -->`.\n\n"
            "The order matters: the signal that closes the review for the loop is the label, and the marker only "
            "stands in for it when the label is missing. That is why the label goes first: if you post the comment "
            "before, the loop may close the review without a verdict. Leave the comment in the same turn, right "
            "after the label.\n\n"
            f"## Slice under review: {a_slice.title}\n{a_slice.description}"
        )

    def resumption(self, a_slice: Slice, pull_request_number: int) -> str:
        return (
            f"Your previous turn ended without declaring the verdict of the review of the Pull Request "
            f'#{pull_request_number} of the slice "{a_slice.title}". Continue from where you left off and close the '
            "review in TWO STEPS AND IN THIS ORDER: first the verdict label on the sub-issue with "
            f"`gh issue edit {a_slice.id.value} --add-label review:<verdict>` (approve, minor, blocking or blocked), "
            f"and then EXACTLY ONE summary comment on the Pull Request (`gh pr comment {pull_request_number}`) "
            "that ENDS with the marker on its own line: `<!-- grooveloop:review -->`. If you already wrote one of "
            "the two, do not repeat it. You only annotate: do not fix code or push. Do not run commands in the "
            "background or end your turn waiting for a task. You work in autonomous mode: do not ask questions."
        )

    def _journal_instructions_section(self, a_slice: Slice, journal_enabled: bool) -> str:
        if not journal_enabled or a_slice.story_id is None:
            return ""

        return (
            "Before declaring your verdict, record in the Story journal with "
            '`grooveloop note --kind <constraint|finding> "..."` only what goes beyond this Pull Request: '
            "the rules the following slices must respect (`constraint`) and the findings about the system "
            "that the Spec did not mention (`finding`). The findings you would fix in this same PR go to the "
            "summary comment, not to the journal. Do not use the kind `directive`: it is reserved for the human. "
            "You do not need to pass `--repo` or `--story`: the command resolves them from your run.\n\n"
        )

    def _journal_entries_section(self, a_slice: Slice, repo: str, journal_enabled: bool) -> str:
        if not journal_enabled or a_slice.story_id is None:
            return ""

        return self._story_journal_section.build(repo, a_slice.story_id.value)
