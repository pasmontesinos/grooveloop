from __future__ import annotations

import sys

from grooveloop.bootstrap import container
from grooveloop.journal.application.commands.append_journal_entry import (
    AppendJournalEntryCommand,
    AppendJournalEntryCommandHandler,
)
from grooveloop.journal.infrastructure.cli.run_context import resolve_current_run_context
from grooveloop.shared.infrastructure.cli.exit_code import ExitCode

_HUMAN_AUTHOR = "human"


def run(repo: str | None, story: int | None, kind: str, body: str) -> int:
    if repo is None and story is None:
        context = resolve_current_run_context()
        if context is None or context.story_id is None:
            print(
                "missing context: pass --repo and --story, or start from a run with GROOVELOOP_RUN_ID", file=sys.stderr
            )

            return ExitCode.MISSING_CONTEXT

        repo, story_id, author = context.repo, context.story_id, context.profile
    elif repo is None or story is None:
        print("--repo and --story must be passed together when there is no run context", file=sys.stderr)

        return ExitCode.USAGE_ERROR
    else:
        story_id = str(story)
        author = _HUMAN_AUTHOR

    handler = container.get(AppendJournalEntryCommandHandler)

    try:
        handler(AppendJournalEntryCommand(repo=repo, story_id=story_id, kind=kind, author=author, body=body))
    except ValueError as error:
        print(f"invalid entry kind: {error}", file=sys.stderr)

        return ExitCode.USAGE_ERROR

    return ExitCode.OK
