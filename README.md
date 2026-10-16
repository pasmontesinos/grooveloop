# grooveloop

A CLI orchestrator that **drives the software delivery cycle of a change by delegating each step to coding agents**. You write a GitHub Issue with the spec of a change, already cut into slices. grooveloop creates one sub-issue per slice, dispatches an agent that plans and implements each one, has another agent review the pull request before you do, addresses review comments, and moves on to the next slice when you merge.

GitHub holds the state of every Story and slice, and Claude Code is the default agent engine (opencode is the other one). Both sit behind ports, so persistence and agents can change without touching the core.

## A personal loop

grooveloop is my own way of working with coding agents, turned into a tool. I used to steer the agent in real time, in the same session where the code was being written. As models got better and the repository conventions sharpened with every correction I wrote down, it made more sense to put the weight on the spec and delegate the implementation, until it ran on autopilot up to the pull request. What was left was coordination: handing over the spec, launching, reviewing, launching the next slice, one repetitive prompt after another. grooveloop was born to replace that coordination. Correction rounds, parallel slices and lessons came later, almost on their own. I keep refining it with every change it delivers.

I use it every day, on experiments, on personal projects and on projects with a high impact in production. That is why it is not a loop to hand everything over to the agents. It is a loop with control:

- **You think the spec.** The cut into slices, the order and the dependencies are yours.
- **You decide.** Merge approves, close rejects, a comment redirects. Nothing reaches `master` without your merge unless you choose `--auto-merge`.
- **It improves continuously.** Each redirection you mark as a lesson becomes a conventions pull request that you review, so the same correction is not needed twice.

> **Status:** personal project in daily use, published as it is. No guarantees and no support. It runs on one machine, against repositories you own.

## Why "grooveloop"

I am a percussionist. In a musical ensemble, percussion holds the pulse from inside, and everyone locks into it. That steady feel is the **groove**. The word comes from the groove of a vinyl record, where the needle follows the track without skipping. Being *in the groove* is playing with no friction.

A **groove loop** is also a real thing for a producer: the rhythmic pattern that repeats in a loop and carries the song while everything else is built on top. For a developer, a loop is a reconciliation loop that observes the state and corrects it, which is exactly how grooveloop works: on each tick it reads GitHub, detects what changed and acts.

So grooveloop is the loop that keeps a change in the groove, from spec to merge, so that nothing stalls between one step and the next.

## How it works

1. **A Story.** An Issue holds the spec of a change, with a `## Slices` section: one `###` heading per slice, in delivery order, each with its dependencies.
2. **Slicing.** When the Issue has the `grooveloop` and `ready_for_implementation` labels, the loop creates one sub-issue per slice and adds the `sliced` label to the Issue.
3. **Implementation.** For every slice whose dependencies are merged, the loop dispatches the `developer` agent in an isolated git worktree. The agent opens a pull request with `Closes #<sub-issue>`.
4. **Automated review.** The `reviewer` agent reviews the pull request, leaves a summary comment on it and records its verdict as a label of the sub-issue. A blocking verdict can trigger automatic correction rounds.
5. **Human review.** You review in GitHub. **Merge approves, close rejects.** A comment with a directive asks for more changes. The loop never merges on its own unless you start it with `--auto-merge` (see below).
6. **Next slice.** The loop detects the merge and dispatches the slices it unblocks. Independent slices run in parallel.

Every step is idempotent and driven by polling: each *tick* reads GitHub, detects what changed and acts. There is no broker, no database and no webhook; the local files under `~/.grooveloop/` hold the agent runs, the Story journals and what `watch` shows.

## Quick start

1. Install the CLI and the Claude Code plugin (see [Installation](#installation)).
2. In a checkout of the target repository, ask Claude Code to prepare it with the `grooveloop:setup` skill. It creates the labels, reviews `CLAUDE.md` and proposes the agent profiles.
3. Write the spec of a change with the `grooveloop:slicing` skill. The skill creates the Story Issue with its labels.
4. Start the loop:

   ```bash
   grooveloop loop --repo <owner>/<repo> --workdir <checkout>
   ```

5. Watch it from another terminal:

   ```bash
   grooveloop watch
   ```

## Installation

**Requirements:**

- [`uv`](https://docs.astral.sh/uv/) on the `PATH`, and `~/.local/bin` on the `PATH` (`uv tool update-shell` adds it).
- [`gh`](https://cli.github.com/) authenticated (`gh auth status`). The loop uses its token.
- The agent engine on the `PATH`: [`claude`](https://docs.anthropic.com/en/docs/claude-code) by default, or `opencode`. Every agent run consumes your plan or your API credit.
- A GitHub repository with Issues and sub-issues enabled, and a local checkout of it.

**CLI:**

```bash
uv tool install grooveloop      # install the latest release from PyPI
uv tool upgrade grooveloop      # upgrade to the latest release
uv tool uninstall grooveloop    # uninstall
```

To run unreleased code from `master`, install with `uv tool install git+https://github.com/pasmontesinos/grooveloop`. A running loop keeps the code it started with: restart it after an upgrade.

**Claude Code plugin:**

```bash
claude plugin marketplace add pasmontesinos/grooveloop
claude plugin install grooveloop@grooveloop
```

| Skill | Use it to |
|---|---|
| `grooveloop:setup` | Prepare a repository for the loop, or review the configuration of one it already drives. |
| `grooveloop:slicing` | Write, slice or review the spec of a Story. |
| `grooveloop:verify` | Check that the deploy of a merged slice does not degrade the service. |
| `grooveloop:conventions` | Review, refine, create or adapt the convention files of a repository. The default `scribe` loads it. |

Upgrade with `claude plugin marketplace update grooveloop && claude plugin update grooveloop@grooveloop`. The plugin carries the same version as the package, because its skills describe the contract of that CLI version: upgrade both together.

## Using it

### The spec

The spec is the prompt: the loop copies the whole spec, and then the body of the slice, into the instruction of the agent that implements each slice. The parser reads:

- a level-1 or level-2 heading `Slices`, which opens the section;
- one `###` heading per slice, in delivery order;
- a line `- **Depends on:** none` or `- **Depends on:** slices 1, 3` per slice, which declares its dependencies by position, always on slices of the same Story;
- an `Observable verification` block per slice: the checks that prove the slice works once it is merged. With `--verify-deploy`, the `verifier` agent runs them after the merge; without it, they are for the human.

The `grooveloop:slicing` skill writes all of this for you, together with the value, the scope and the acceptance criteria of each slice.

Everything the loop parses or writes is in English. A target repository can write its specs, comments and conventions in any language, as long as it keeps in English the formats a human writes for the loop: the `Slices` heading, the `**Depends on:**` bullet, the `Observable verification` block and the directives.

### Labels

The loop keeps the state of each slice in the labels of its sub-issue:

| Label | Meaning |
|---|---|
| `pending`, `dispatched`, `under_review`, `pr_open`, `changes_requested`, `blocked`, `merged`, `failed` | Lifecycle state of the slice. |
| `review:approve`, `review:minor`, `review:blocking`, `review:blocked` | Verdict of the automated reviewer. |
| `review-round:N` | Automatic correction rounds already spent. A correction may also rebut the findings of a `review:blocking` verdict, without commits, with a reasoned pull request comment ending with `<!-- grooveloop:no-changes -->`; the reviewer then judges the rebuttal, and a new blocking verdict spends another round. |
| `retry:N`, `failure:<cause>` | Retries of the current phase, and the cause when the slice fails for good. |
| `story:N`, `order:N`, `run:<id>`, `pr:N` | Links to the Story, the position, the agent run and the pull request. |

Transient failures (an interrupted run, a network error, an agent that ends without a pull request) are retried with a cap (`--max-retries`) and an exponential wait. A run silent for 30 minutes is stopped and retried.

### Talking to the loop

Write a directive **at the start of a line** in a pull request comment, in the conversation or inline:

- `/grooveloop-implement` asks for another round of changes. It also unblocks a slice with a `review:blocked` verdict.
- `/grooveloop-learn` marks a lesson. The `scribe` agent turns it into a pull request against the repository conventions.

A directive quoted (`>`) or mentioned in the middle of a sentence does not count.

The loop marks the `/grooveloop-implement` directives it consumes with reactions on their comment: 👀 when a correction takes them and 🚀 when that correction ends with commits or with the developer's reasoned reply that nothing must change (a pull request comment ending with `<!-- grooveloop:no-changes -->`). Either way the reviewer checks the correction, and judges whether the reason for declining holds. A directive without 🚀 is still pending, so a directive written while a correction is running goes into the next round, and removing the 🚀 of a directive re-opens it. The loop reacts with the account of its `gh` token; if that is your own account, do not add 👀 or 🚀 to your directives yourself. A pull request on which the loop has not marked any directive yet keeps the previous rule: a directive is pending while no commit is newer than it.

To pause a Story, relabel its `pending` slices as `blocked`. To resume, relabel those slices back as `pending`. Do not touch a `blocked` slice that has a `review:blocked` verdict or a `pr:N` label: it waits for your decision on an open pull request, and you resolve it with a merge, a close or `/grooveloop-implement`. To retry a `failed` slice, relabel it as `pending`.

### Auto-merge

`--auto-merge` is **off by default**, and the default is deliberate. With it, the loop squash-merges into `master` every pull request that the automated reviewer approves (`approve` or `minor`) as soon as GitHub reports it as mergeable. **No human reviews that code before it lands.**

Turn it on only when that is acceptable for the repository:

- what `master` triggers: a deploy to production, a release, a package publication;
- how much you trust the checks that gate the merge: the automated reviewer, which is an agent and can be wrong, and the CI of the repository. The loop merges only when GitHub reports the pull request as `clean`, so a failing or running check stops it; but a check that has not been registered yet does not, so the merge can happen before CI starts. Required checks in branch protection close that gap;
- how cheap it is to undo: a `git revert` of a squash commit is easy, a bad deploy or a published release may not be.

A safe way to start is a repository without automatic deploys and with branch protection on `master`.

### The journal

Agents record rules, decisions and findings for the next slices of the same Story:

```bash
grooveloop note --kind decision "..."   # inside an agent run, repo and story come from run.json
grooveloop journal                      # read the entries
```

The loop injects the journal of the Story into every agent prompt (`--no-journal` turns it off).

### Cleanup

After a run finishes (and a 30-minute grace period, so that an interrupted run can resume), the loop terminates the processes left in its worktree, tears down the Docker Compose stacks started from it and removes the worktree. Without Docker, that step is skipped.

## Agent profiles

Each phase runs an agent with a profile: `developer` implements and addresses reviews, `reviewer` reviews before the human, `verifier` checks the deploy and `scribe` refines the conventions from lessons. The default profiles live in [`src/grooveloop/shared/infrastructure/agent_profiles/`](src/grooveloop/shared/infrastructure/agent_profiles/).

A target repository overrides a profile with a file of the same name in `<workdir>/.grooveloop/agents/<name>.md`: Markdown with a front matter and the persona in the body. Every field the override declares replaces the default; every field it omits is inherited. An empty body inherits the persona.

| Field | Effect, for any profile |
|---|---|
| `engine` | `claude` or `opencode`. |
| `model` | The model the engine runs. |
| `skills` | Skills the agent loads with the Skill tool before it starts. |
| `context_files` | Files of the target repository the agent reads before it starts, such as its conventions. |

`skills` and `context_files` are lists, and a list in the override replaces the default list: repeat the default entries you want to keep.

### Superpowers skills are replaceable

The default `developer` persona names three skills of the [superpowers](https://github.com/obra/superpowers) plugin for Claude Code: `test-driven-development`, `verification-before-completion` and `receiving-code-review`. Install the plugin to use them as they are.

They are not required. The loop only copies their names into the agent instruction. To use other skills with the same purpose, or none, override the `developer` profile with a persona that names yours.

### Deploy verification

With `--verify-deploy`, the loop adds the `verify-deploy` label to every new sub-issue. When one of those slices is merged, the loop dispatches the `verifier` agent, which gives two verdicts:

1. **The deploy does not degrade the service.** It follows the `grooveloop:verify` skill: the new version against the previous one, with written thresholds. The skill knows the method, not where your metrics are.
2. **The increment does what it promised.** It runs the checks of the verification section of the sub-issue.

The agent runs with no human in the loop, so it never asks about your observability. Give it through the `verifier` override, with the same `skills` and `context_files` fields as any profile: for example, a file that says where the errors, latency and traffic of each service are and how to tell one version from another, and the skills of your team that query those sources, if you have any.

```markdown
---
skills: [grooveloop:verify, my-team:metrics-queries]
context_files: [docs/observability.md]
---
```

Without that configuration, the deploy verdict is "inconclusive" and the report says why. The increment verdict does not change.

## CLI reference

| Command | Does |
|---|---|
| `grooveloop loop --repo <owner>/<repo> --workdir <checkout>` | Runs the loop, headless: ticks, heartbeat and a snapshot of the repository for `watch`. |
| `grooveloop watch` | Terminal app that lists the live loops of the machine and shows the panel of one. It only reads local state files, never GitHub. |
| `grooveloop doctor [--workdir <checkout>] [--repo <owner>/<repo>]` | Preflight: probes every adapter (GitHub auth, the agent engines the profiles use, profiles; Docker only warns; with `--repo`, the auto-merge setup). `loop` runs the same preflight before its first tick. |
| `grooveloop note` / `grooveloop journal` | Write and read the journal of a Story. |
| `grooveloop usage --repo <owner>/<repo> --slice <n>` | Cost of the agent runs of a slice, by token class and by model. |

**`loop` flags:**

| Flag | Default | Effect |
|---|---|---|
| `--repo` | — | Target repository. |
| `--workdir` | `.` | Local checkout the agent worktrees are created from. It must be a checkout of `--repo`. |
| `--story <n>` | — | Limits the loop to one Story. |
| `--once` | off | Runs a single tick and exits. |
| `--tick-interval` | `120` | Seconds between ticks. The tick is the only reader of GitHub. |
| `--interval` | `5` | Seconds between local polls (heartbeat, no GitHub). |
| `--max-parallel-slices` | `3` | Slices of one Story in progress at the same time: dispatched, in review, with changes requested, with an open pull request or blocked. |
| `--max-review-rounds` | `3` | Automatic correction rounds after a blocking review verdict. |
| `--max-retries` | `2` | Retries of a phase after a recoverable failure. `0` turns retries off. |
| `--auto-merge` | off | Squash-merges a pull request with an `approve` or `minor` verdict once GitHub reports it as mergeable. See [Auto-merge](#auto-merge). |
| `--verify-deploy` | off | Labels new sub-issues so that their deploy is verified after the merge. |
| `--journal` / `--no-journal` | on | Injects the journal of the Story into the agent prompts. |

**`watch` keys:** `tab` moves the focus, `[` and `]` change the Story, `enter` expands a detail, `esc` goes back, `o` opens the pull request in GitHub, `f` filters the journal entries by kind and `q` quits. `--stall-after` sets the seconds of silence in `agent.log` after which a run is flagged as silent. Without a TTY, `watch` exits with code `2`.

**Exit codes:** every command shares them, and its `--help` lists the ones it uses. Diagnostics (`[warn]`, `[fail]` and usage errors) go to stderr; the normal output stays on stdout. `doctor` is the exception: its report, `[fail]` lines included, is its output and goes to stdout.

| Code | Meaning | Examples |
|---|---|---|
| `0` | Success. | `loop --once` with a passing tick, a clean Ctrl-C of `loop`, `q` in `watch`. |
| `1` | The command ran and the result is a failure. | A required probe failed in `doctor`, the single tick of `loop --once` failed, `usage` found no sessions for the slice. |
| `2` | Usage error. | Unrecognized or invalid arguments, an unknown journal kind, `--repo` without `--story` in `note`/`journal`, `watch` without a TTY. |
| `3` | Preflight failed: the environment is not ready. | `loop` refuses to start because a required probe failed. |
| `4` | Missing context. | `note`/`journal` outside an agent run without `--repo` and `--story`. |

In continuous mode, a failed tick or a target repository that cannot be loaded does not stop `loop`: it writes a `[fail]` or `[warn]` line to stderr and keeps going.

**Environment variables:**

| Variable | Default | Effect |
|---|---|---|
| `GROOVELOOP_LOG_LEVEL` | `WARNING` | Level of the `grooveloop` logs written to stderr as `<time> <LEVEL> <message>`. `INFO` adds one `Executing ...` and one `Executed ... in <ms>ms` line per command and query handler. An unknown value means `WARNING`. Under `watch` the lines land on the terminal of the app, so raise it only for `loop` and the other commands. |

## Architecture

Hexagonal (ports and adapters) with a pure domain core and a CQRS application layer.

- **Bounded contexts by delivery process:** `slicing` (spec to sub-issues), `delivery` (each slice until the merge), `verification` (the deploy after the merge), `learning` (review lessons to convention changes), `journal` (the Story journal) and `shared`. Contexts talk through a `QueryBus` and through events detected from GitHub; a feature context never imports another, and a test enforces the layer rules.
- **Events without a broker:** on every tick, detectors read GitHub and the local runs and synthesize events, without writing anything; an in-process dispatcher hands them to handlers that run commands. Idempotency and state guards replace queues and cursors.
- **Ports:** one repository per aggregate (`StoryRepository`, `SliceRepository`, `SliceVerificationRepository` and `LessonRepository` on GitHub, `JournalEntryRepository` on disk), an `AgentRunner` (detached subprocess, with `ClaudeCommand` and `OpencodeCommand` engines), an `AgentLogReader` per engine and a `Clock`.
- **Hybrid state:** GitHub is the source of truth; `~/.grooveloop/` keeps the runs, their logs and the state files of `watch` as instrumentation, and the Story journals.
- **Preflight:** every external dependency has a probe that proves it can honor its contract; `doctor` and `loop` run the same probes before the loop accepts work (`wire → probe → use`).

Decisions are recorded in [docs/adr/](docs/adr/), and the coding conventions in [docs/conventions/](docs/conventions/).

## Development

Python 3.13 · `injector` · `uv` · `pytest` · `hypothesis` · `mypy` · `ruff`.

```bash
make test           # uv run pytest
make check-types    # uv run mypy
make check-style    # uv run ruff check
make check-format   # uv run ruff format --check
make fix-linting    # uv run ruff check --fix && uv run ruff format
```

From a checkout, run the CLI with `uv run grooveloop ...`. Read [CLAUDE.md](CLAUDE.md) and the conventions before you change code.

## License

[Apache-2.0](LICENSE).
