from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.learning.domain.lesson_comment import LessonComment


class RefinementTask:
    def build(self, pull_request: int, comments: list[LessonComment]) -> str:
        lessons = "\n\n".join(self._render_comment(index, comment) for index, comment in enumerate(comments, 1))

        return (
            f'Evaluate the lessons marked with "/grooveloop-learn" in the Pull Request #{pull_request} and decide '
            "whether they bring a convention that is not yet codified in the target repository (`docs/conventions/`, "
            "`CLAUDE.md`).\n\n"
            "You work in autonomous mode: there is no human in the loop. Do not ask questions or wait for "
            "confirmation; pick reasonable defaults.\n\n"
            "Discard the lessons when the current conventions already cover them, when they are a one-off detail "
            "with no reusable value, or when they teach no rule that generalizes.\n\n"
            "If they bring a convention to codify: edit `docs/conventions/` or `CLAUDE.md` minimally. You run in "
            "a worktree with a detached HEAD on `master`, so for the change to persist you must do the full git "
            "flow before opening the Pull Request, just like the developer with its slices: "
            "(1) create a descriptive branch with `git checkout -b docs/conventions-<topic>`, (2) commit the change "
            "with `git commit`, (3) publish the branch with `git push -u origin <branch>`, and (4) open the "
            'conventions Pull Request with the label "grooveloop" (`gh pr create --label grooveloop`) whose title '
            'starts with "docs(conventions):" and contains the word "conventions". Include in the BODY of that '
            "conventions Pull Request, on its own line, this marker that links it to the lesson (copy it "
            f"verbatim, do not change the number): `<!-- grooveloop:lesson pr={pull_request} -->`. Then reply in the "
            f"conversation of the original Pull Request with `gh pr comment {pull_request}` explaining which "
            "convention you refined.\n\n"
            "If they bring no convention to codify: do NOT open any Pull Request or edit `docs/conventions/` or "
            f"`CLAUDE.md`, and reply in the conversation of the original Pull Request with `gh pr comment "
            f"{pull_request}` explaining why you discard them; END with the marker on its own line: "
            "`<!-- grooveloop:learned discarded -->` (this is the discard signal the loop recognizes).\n\n"
            "The loop reconciles the terminal state of the lesson automatically from your result (the linked "
            "conventions Pull Request or the discard marker). Do NOT manage the state yourself: do not edit, "
            "close or label the sub-issue of the lesson; just produce the result described above.\n\n"
            "Do not merge or close any Pull Request: the review of the conventions PR belongs to the human.\n\n"
            f"## Lessons\n{lessons}"
        )

    def _render_comment(self, index: int, comment: LessonComment) -> str:
        location = f"{comment.path}:{comment.line}" if comment.path else "the PR conversation"
        diff_section = f"\n\n### Diff under review\n{comment.diff_hunk}" if comment.diff_hunk else ""

        return f"### Lesson {index} ({location})\n{comment.body}{diff_section}"
