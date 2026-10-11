from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from grooveloop.bootstrap import container
from grooveloop.journal.application.queries.read_journal_entries import ReadJournalEntriesQueryHandler
from grooveloop.journal.infrastructure.cli.run_context import resolve_current_run_context
from grooveloop.shared.application.queries.read_journal_entries import ReadJournalEntriesQuery
from grooveloop.shared.infrastructure.cli.exit_code import ExitCode

if TYPE_CHECKING:
    from datetime import datetime


def run(repo: str | None, story: int | None, kinds: list[str] | None = None) -> int:
    written_after: datetime | None = None
    if repo is None and story is None:
        context = resolve_current_run_context()
        if context is None or context.story_id is None:
            print(
                "missing context: pass --repo and --story, or start from a run with GROOVELOOP_RUN_ID", file=sys.stderr
            )

            return ExitCode.MISSING_CONTEXT

        repo, story_id, written_after = context.repo, context.story_id, context.started_at
    elif repo is None or story is None:
        print("--repo and --story must be passed together when there is no run context", file=sys.stderr)

        return ExitCode.USAGE_ERROR
    else:
        story_id = str(story)

    handler = container.get(ReadJournalEntriesQueryHandler)

    try:
        result = handler(
            ReadJournalEntriesQuery(repo=repo, story_id=story_id, kinds=kinds, written_after=written_after)
        )
    except ValueError as error:
        print(f"invalid entry kind: {error}", file=sys.stderr)

        return ExitCode.USAGE_ERROR

    if written_after is not None and not result.entries:
        print("no new journal entries since the run started")

    for entry in result.entries:
        print(f"[{entry.kind}] {entry.author} — {entry.body}")

    return ExitCode.OK
