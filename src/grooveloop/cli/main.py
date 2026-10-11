from __future__ import annotations

import argparse
import logging
import os
import sys

from grooveloop.cli import doctor_command, loop_command, watch_command
from grooveloop.cli.watch_render import DEFAULT_STALL_AFTER_SECONDS
from grooveloop.delivery.infrastructure.cli import usage_command
from grooveloop.journal.infrastructure.cli import journal_command, note_command
from grooveloop.shared.infrastructure.cli.exit_code import ExitCode, describe_exit_codes

_USAGE_ERROR = "usage error: unrecognized or invalid arguments"
_LOG_LEVEL_VARIABLE = "GROOVELOOP_LOG_LEVEL"
_LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"


def _configure_logging() -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    level_name = os.environ.get(_LOG_LEVEL_VARIABLE, "WARNING").upper()

    logger = logging.getLogger("grooveloop")
    logger.handlers = [handler]
    logger.setLevel(logging.getLevelNamesMapping().get(level_name, logging.WARNING))


def _non_negative(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError(f"expected zero or more, got {parsed}")

    return parsed


def _positive(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError(f"expected one or more, got {parsed}")

    return parsed


def main(argv: list[str] | None = None) -> int:
    _configure_logging()
    parser = argparse.ArgumentParser(prog="grooveloop")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Run preflight probes (auth, connectivity)",
        epilog=describe_exit_codes(
            {
                ExitCode.OK: "every required probe passed (an optional one may only warn)",
                ExitCode.FAILURE: "a required probe failed",
                ExitCode.USAGE_ERROR: _USAGE_ERROR,
            }
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    doctor_parser.add_argument(
        "--workdir", default=".", help="Base checkout (with .git) the agent profiles are read from"
    )
    doctor_parser.add_argument(
        "--repo", default=None, help="Target repository (owner/repo) whose auto-merge setup is checked"
    )

    loop_parser = subparsers.add_parser(
        "loop",
        help="Drive the repo as a headless daemon; watch shows what it does",
        epilog=(
            "Clocks:\n"
            "  --interval       local poll: the heartbeat and the check for a due tick (no GitHub)\n"
            "  --tick-interval  the tick, the only reader of GitHub\n"
            "                   the snapshot it publishes carries it, so watch flags it stale after two of them\n"
            "\n"
            + describe_exit_codes(
                {
                    ExitCode.OK: "the single tick of --once passed, or a clean Ctrl-C exit in continuous mode",
                    ExitCode.FAILURE: "the single tick of --once failed (in continuous mode a failed tick only warns)",
                    ExitCode.USAGE_ERROR: _USAGE_ERROR,
                    ExitCode.PREFLIGHT_FAILED: "preflight failed: the environment is not ready, the loop did not start",
                }
            )
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    loop_parser.add_argument("--repo", required=True, help="Target repository (owner/repo)")
    loop_parser.add_argument("--interval", type=int, default=5, help="Seconds between local polls")
    loop_parser.add_argument("--tick-interval", type=int, default=120, help="Seconds between autonomous ticks")
    loop_parser.add_argument(
        "--workdir", default=".", help="Base checkout (with .git) the agent worktrees are created from"
    )
    loop_parser.add_argument("--once", action="store_true", help="Run a single pass and exit")
    loop_parser.add_argument("--story", type=int, default=None, help="Scope the tick to a single parent story")
    loop_parser.add_argument(
        "--verify-deploy",
        action="store_true",
        help="Label every new sub-issue so its deploy gets verified after the merge",
    )
    loop_parser.add_argument(
        "--max-review-rounds",
        type=_non_negative,
        default=3,
        help="Automatic corrections the loop may ask for on a blocking review verdict",
    )
    loop_parser.add_argument(
        "--max-parallel-slices",
        type=_positive,
        default=3,
        help="Slices a single Story may have dispatched at once",
    )
    loop_parser.add_argument(
        "--max-retries",
        type=_non_negative,
        default=2,
        help="Times the loop redispatches a phase whose run was interrupted (0 fails it as before)",
    )
    loop_parser.add_argument(
        "--auto-merge",
        action="store_true",
        help="Squash-merge every PR the reviewer approves once GitHub reports it clean",
    )
    loop_parser.add_argument(
        "--journal",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Inject the Story's journal into the dispatched agent's prompt",
    )

    watch_parser = subparsers.add_parser(
        "watch",
        help="Open the Textual app that watches every loop running on this machine, without touching GitHub",
        epilog=(
            "Keys:\n"
            "  [tab]      switch the focus\n"
            "  [↑/↓]      move through the focused list\n"
            "  [ / ]      previous / next Story\n"
            "  [enter]    expand the detail to full screen\n"
            "  [esc]      back to the three columns\n"
            "  [o]        open the pull request on GitHub\n"
            "  [f]        filter the journal entries by kind (Journal tab)\n"
            "  [q]        quit\n"
            "\n"
            "Clocks:\n"
            "  --interval     local runner poll: run.json and the tail of agent.log (no GitHub)\n"
            "  --stall-after  silence warning for a running agent, from the mtime of agent.log\n"
            "\n"
            "Screenshot:\n"
            "  --screenshot FILE.svg  paint one frame of a fixed-size screen without a terminal, save it and exit\n"
            "\n"
            + describe_exit_codes(
                {
                    ExitCode.OK: "quit with [q], or screenshot saved",
                    ExitCode.USAGE_ERROR: "usage error: no interactive terminal, or unrecognized arguments",
                }
            )
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    watch_parser.add_argument("--interval", type=int, default=1, help="Seconds between repaints")
    watch_parser.add_argument(
        "--stall-after",
        type=int,
        default=DEFAULT_STALL_AFTER_SECONDS,
        help="Seconds without agent log activity before the panel flags a run as silent",
    )
    watch_parser.add_argument(
        "--screenshot", default=None, metavar="FILE.svg", help="Save an SVG screenshot of the first frame and exit"
    )

    usage_parser = subparsers.add_parser(
        "usage",
        help="Show the cost breakdown by token class and by model for a slice",
        epilog=describe_exit_codes(
            {
                ExitCode.OK: "the sessions of the slice were shown",
                ExitCode.FAILURE: "no sessions for the slice",
                ExitCode.USAGE_ERROR: _USAGE_ERROR,
            }
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    usage_parser.add_argument("--repo", required=True, help="Target repository (owner/repo)")
    usage_parser.add_argument("--slice", type=int, required=True, help="Sub-issue number of the slice")

    note_parser = subparsers.add_parser(
        "note",
        help="Append an entry to a Story's journal",
        epilog=describe_exit_codes(
            {
                ExitCode.OK: "the entry was appended",
                ExitCode.USAGE_ERROR: "usage error: an unknown entry kind, --repo without --story or the reverse",
                ExitCode.MISSING_CONTEXT: "missing context: no --repo/--story and no agent run in GROOVELOOP_RUN_ID",
            }
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    note_parser.add_argument("--repo", default=None, help="Target repository (owner/repo); default: from run.json")
    note_parser.add_argument(
        "--story", type=int, default=None, help="Parent Story issue number; default: from run.json"
    )
    note_parser.add_argument("--kind", required=True, help="Entry kind (constraint, directive, decision, finding)")
    note_parser.add_argument("body", help="Entry body")

    journal_parser = subparsers.add_parser(
        "journal",
        help="Show a Story's journal",
        epilog=describe_exit_codes(
            {
                ExitCode.OK: "the journal was shown, even when it has no entries",
                ExitCode.USAGE_ERROR: "usage error: an unknown entry kind, --repo without --story or the reverse",
                ExitCode.MISSING_CONTEXT: "missing context: no --repo/--story and no agent run in GROOVELOOP_RUN_ID",
            }
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    journal_parser.add_argument("--repo", default=None, help="Target repository (owner/repo); default: from run.json")
    journal_parser.add_argument(
        "--story", type=int, default=None, help="Parent Story issue number; default: from run.json"
    )
    journal_parser.add_argument("--kind", action="append", default=None, help="Filter by entry kind (repeatable)")

    args = parser.parse_args(argv)

    if args.command == "doctor":
        return doctor_command.run(workdir=args.workdir, repo=args.repo)

    if args.command == "usage":
        return usage_command.run(repo=args.repo, slice_number=args.slice)

    if args.command == "note":
        return note_command.run(repo=args.repo, story=args.story, kind=args.kind, body=args.body)

    if args.command == "journal":
        return journal_command.run(repo=args.repo, story=args.story, kinds=args.kind)

    if args.command == "watch":
        return watch_command.run(interval=args.interval, stall_after=args.stall_after, screenshot=args.screenshot)

    if args.command == "loop":
        return loop_command.run(
            args.repo,
            interval=args.interval,
            tick_interval=args.tick_interval,
            workdir=args.workdir,
            once=args.once,
            story=args.story,
            verify_deploy=args.verify_deploy,
            max_review_rounds=args.max_review_rounds,
            max_parallel_slices=args.max_parallel_slices,
            journal_enabled=args.journal,
            max_retries=args.max_retries,
            auto_merge=args.auto_merge,
        )

    return ExitCode.USAGE_ERROR
