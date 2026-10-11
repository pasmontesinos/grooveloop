# CLAUDE.md

`grooveloop` is a **CLI orchestrator that drives the delivery cycle of a change by delegating each step to coding agents**. Hexagonal architecture: today GitHub is the persistence adapter and Claude Code (by default) or opencode the agent engine; both sit behind ports so that tomorrow we can switch to sqlite/postgres or to other engines. See [docs/adr/](docs/adr/).

## ⚠️ CRITICAL RULE: CONVENTIONS FIRST

**BEFORE proposing ANY code change (tests included):**

1. **IDENTIFY** the affected layer in the table below
2. **READ** with the Read tool the matching conventions file in `docs/conventions/`, plus `code-style.md`. This `CLAUDE.md` does not import them: a convention you do not open is a convention you do not know
3. **APPLY** exactly what the project convention says
4. **DO NOT** assume, DO NOT improvise, DO NOT use patterns from other projects
5. **If the change replaces behavior already in production** (adapter in use, external provider, observable business rule), invoke the `grooveloop:slicing` skill and read its section "When parallel changes are mandatory" before writing or executing the plan

**Adherence to the project conventions takes PRIORITY over speed and over general best practices.**

### Hierarchy of authority

The **project conventions** (`docs/conventions/`) and the **ADRs** (`docs/adr/`) ALWAYS prevail over general best practices.

### Conventions per layer

**Always read** `docs/conventions/code-style.md` before any code change.

**Depending on what you are going to touch, add:**

| If you are going to touch... | Read                                                   |
|---|--------------------------------------------------------|
| Folder structure, file naming | `docs/conventions/architecture.md`                   |
| Entities, aggregates, value objects, ports, Slice state machine, events | `docs/conventions/domain.md` |
| Commands and queries (CQRS use cases), handlers, QueryBus, tasks, application services | `docs/conventions/application.md`         |
| CLI commands, the tick, detectors, event handlers, adapters, probes and preflight, exit codes, state files | `docs/conventions/infrastructure.md`           |
| Container, modules, providers | `docs/conventions/dependency-injection.md`          |
| Tests (structure, mocks, fakes, property-based) | `docs/conventions/testing.md`                    |
| Planning changes, cutting slices/PRs | skill `grooveloop:slicing`                              |

## Domain glossary

- **Contexts (one per delivery process):** `slicing` (Spec → sub-issues), `delivery` (each slice until the merge), `verification` (the deploy and the increment after the merge), `learning` (review lessons → convention changes), `journal` (the Story journal) and `shared` (CQRS base, `Identifier`, `Clock`, `Event`, `EventDispatcher`, `QueryBus`). They communicate through the `QueryBus` (reads) and through **events detected from GitHub**; a feature context never imports another, and `shared` imports none (`tests/grooveloop/test_architecture.py` enforces the layer rules). See [ADR-0005](docs/adr/0005-context-map.md) and [`docs/conventions/architecture.md`](docs/conventions/architecture.md).
- **Story** (aggregate, `slicing`) — the parent Issue. It holds the **`Spec`** of the change; the loop reads it and materializes one sub-issue per slice, it does not write it.
- **Slice** (aggregate, `delivery`) — the work item of each sub-issue: `SliceOrder`, dependencies (a DAG inside the Story) and, once implemented, its **`PullRequest`** with the review comments **inside the aggregate**.
- **Slice life cycle:** `PENDING → DISPATCHED → UNDER_REVIEW → PR_OPEN ⇄ CHANGES_REQUESTED → … → MERGED`, plus `BLOCKED` (the reviewer needs a human decision) and `FAILED` (terminal, after bounded retries). The transitions, review rounds, retries and auto-merge are specified in the "Slice state machine" section of [`docs/conventions/domain.md`](docs/conventions/domain.md) and in [ADR-0009](docs/adr/0009-failed-is-terminal-with-bounded-retry-first.md). Read it before touching any of them.
- **Events:** they are not persisted or published when a command finishes. On each tick, **detectors** read GitHub and the local run-dirs, and synthesize `Event`s; they never write. An in-process `EventDispatcher` delivers them to `EventHandler`s that invoke commands. Closing abandoned runs and sweeping finished worktrees are commands of their own, run before and after the detectors. Idempotency and state guards replace queues and cursors. See [ADR-0006](docs/adr/0006-events-without-broker-detected-by-polling.md).
- **Ports:** one repository per aggregate (`StoryRepository`, `SliceRepository`, `SliceVerificationRepository`, `LessonRepository` on GitHub; `JournalEntryRepository` on disk), the `AgentRunner` (a detached subprocess; the engine argv lives in an `AgentCommand`, `ClaudeCommand` or `OpencodeCommand`, chosen by the `engine` of the `AgentProfile`), the `AgentLogReader` that reads each run's `agent.log`, and the `Clock`. The `PullRequest` has no repository of its own. See [ADR-0004](docs/adr/0004-ports-and-adapters.md).
- **State:** hybrid — GitHub is the source of truth; the runs and state files under `~/.grooveloop/` are instrumentation, not state. The Story journal (`~/.grooveloop/repos/<repo>/stories/<n>/journal/`) is the one piece of domain state on disk. See [ADR-0003](docs/adr/0003-hybrid-state-and-log-instrumentation.md).

The user-facing flow (labels, directives, journal, cleanup) is described in [README.md](README.md#how-it-works).

## Brainstorming, Planning and Slicing of Changes

**MANDATORY** invoke the `grooveloop:slicing` skill (in the current session) and treat its contract as a hard constraint BEFORE generating artifacts related to planning changes.

The **result** of a brainstorming is a spec materialized as a GitHub Issue with a `## Slices` section and one `### {title}` per slice (see "Anatomy of the artifact" in the `grooveloop:slicing` skill).

The goal is to avoid deliveries that do not meet the cutting criteria, infra isolation, expand/contract and the other slicing heuristics that reduce risk and maximize value.

Do not generate detailed plans for future slices either, to avoid anticipating solutions: each slice is detailed right before starting it, incorporating what was learned from the previous slices, and plans or acceptance criteria for future slices are never written in advance.

## Environment and Commands

**Stack:** Python 3.13 · hexagonal · injector · uv · pytest · hypothesis · mypy · ruff. Local CLI entrypoint, no web framework. At runtime the loop calls `git`, `gh`, the agent engine and, only for the cleanup of finished runs and only if it is installed, `docker`. See [ADR-0001](docs/adr/0001-stack-python-hexagonal-cli.md).

| Action | Command |
|---|---|
| Tests | `make test` (`uv run pytest`) |
| Type checking | `make check-types` (`uv run mypy`) |
| Linting | `make check-style` (`uv run ruff check`) |
| Format | `make check-format` (`uv run ruff format --check`) |
| Fix linting + format | `make fix-linting` (`uv run ruff check --fix && uv run ruff format`) |
| Run the loop | `uv run grooveloop loop --repo <owner>/<repo> --workdir <checkout of that repo>` |
| Preflight (probes) | `uv run grooveloop doctor --workdir <checkout>` |
| Full validation | `make check-style && make check-format && make check-types && make test` |

`--repo` and `--workdir` are independent: the agent works on the code of `--workdir`. If it is not a checkout of `--repo`, the slice never gets its pull request.

The `grooveloop:slicing` skill this file requires belongs to the plugin of this same repository. Install it with `claude plugin marketplace add ./` and `claude plugin install grooveloop@grooveloop` from the checkout.

**Observable verification of a slice of this repository:** the loop installed with `uv tool` keeps the code it started with, and a running loop loaded its code before the merge, so reading the result from either gives false negatives. Verify with `uv run grooveloop ...` from an up-to-date `master` checkout, with `--once`, and never start or kill a long-running loop for it.

## Git Workflow

For the branch, commit and PR workflow, read and follow `docs/conventions/git-workflow.md` before creating the branch. In particular, **NEVER commit directly to `master` or `main`.**

## Language

- **English everywhere.** The whole product is English: source code, names of classes/functions/variables, tests, commits, branches, PRs, documentation, conventions, plans, implementation logs, agent instructions and the GitHub contract (spec bullets, directives, headings, labels).
- What a target repository may write in another language is a rule for the users of grooveloop, not for this repository: see [The spec](README.md#the-spec) in the README.

## Core Principles

### Priorities (in case of conflict)

1. **Safety / Tests** - Never compromise verifiability
2. **Simplicity (YAGNI)** - Implement only what is needed now
3. **Clean Architecture** - Keep layers and ports separated
4. **Style** - Follow the code conventions

### Design Principles

- **Strict TDD**: Do not anticipate future tests or methods that are not needed yet.
- **Atomic changes**: Small commits, small PRs. See the `grooveloop:slicing` skill for the cutting criteria.
- **Pure core + adapters at the edge**: domain and application without I/O; the adapters implement the ports.
- **Mandatory preflight:** every external dependency has a `Probe`, and `doctor` and `loop` run the same probes (`cli/preflight.py`) before accepting work (`wire → probe → use`).
- **Idempotency by default:** every command handler returns early when the aggregate's guard says it has nothing to do (see `application.md`).
- **`Failed` is terminal**; before reaching it, the loop retries the recoverable causes with a cap; recovery never deletes work.
- **Parallel changes** with feature flags / expand-contract (see the `grooveloop:slicing` skill).
