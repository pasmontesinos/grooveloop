---
name: slicing
description: This skill should be used when preparing a change for the grooveloop orchestrator to drive autonomously, and when writing, slicing or reviewing the Spec of a Story. It triggers on "prepare the spec for the loop", "slice this change", "write the spec of X for grooveloop", "create the issue for this feature", "the loop does not pick up the issue", "the loop does not create the sub-issues", or when starting the loop on a new repository.
---

# grooveloop slicing contract

## Overview

`grooveloop` reads the Spec of a change **from the body of a GitHub Issue** and materializes it into one sub-issue per slice. GitHub is its database: state lives in labels and work is declared in Issues.

**The artifact of this work is a GitHub Issue created with `gh`.** It is not a file in the repository, nor a plan in the chat reply, nor a document with front matter. An artifact that is not an Issue with the right labels is invisible to the loop.

The Spec is also **the prompt**: the loop copies the whole Issue body into the instruction of the agent that implements each slice.

## When to use this skill

- You are preparing a feature for the loop to run with no human in the loop.
- You are writing or reviewing the parent Issue of a Story.
- You are starting the loop on a new repository.
- The loop does not detect an Issue that should be ready, or does not create the sub-issues.

Do not use it for the work inside a slice already dispatched: the agent drives that with the repository conventions.

## Anatomy of the artifact

One Issue, with two labels and a body in three parts.

**The labels of the parent Issue:**

| Label | Effect |
|---|---|
| `grooveloop` | Marker. **Without it the loop ignores the Issue completely.** |
| `ready_for_implementation` | Triggers slicing on the next tick. |

The loop creates the state and verdict labels by itself on startup. Not these two: the `grooveloop:setup` skill creates them once per repository. If they are missing, create them with `gh label create grooveloop` and `gh label create ready_for_implementation`.

**The body, in three parts and in this order:**

1. **Context.** What the change is for and who it is for. Free text, with any headings you like except a level 1 or 2 heading named `Slices`.
2. **The `## Slices` section.** One `### {slice title}` per slice. The body of each slice runs until the next heading.
3. **Closing.** The recommended sequence, under a level 1 or 2 heading, which closes the slices section.

**Parser rules, checked against the code:**

- A level 1 or 2 heading whose text is `Slices` opens the section. Any other level 1 or 2 heading closes it.
- Each `###` inside the section is a slice. **The order of appearance is the slice number and the dispatch order.**
- Inside a slice you can use `####` freely: the parser treats them as content.
- An Issue with the label but no `###` inside `## Slices` is ignored silently.

## The summary of each slice

Under each `### {title}`, these bullets, all of them:

```
- **Value / risk reduction:** what the user or the team gets, observable.
- **Scope:** what is in (1-3 bullets).
- **Out of scope:** what is explicitly left for later.
- **Acceptance criteria:** 2-4, verifiable, in present tense.
- **Depends on:** none | slices 1, 3
- **Observable verification:** commands with an assert on the exit code or on GitHub state.
```

If the slice **replaces behavior already in production** (an adapter in use, an external provider, an observable business rule), add a risk block after the scope:

```
- **Risk:**
  - **Runtime switch / rollback:** the flag name or the expand-contract step that brings the old behavior back without a deploy.
  - **How it reaches production safely:** flag | backward compatible | expand-contract | dark launch.
```

Without that block, the slice declares that it replaces nothing in production.

The `###` title names a single thing. A title with "and" or "or" hides two slices.

**The spec is not a low-level plan.** Do not list the files, classes or functions each slice changes: the agent that implements the slice decides that with the code in front of it. Think about them while you slice (see "Parallelism and merge conflicts"), but do not write them down.

## Dependencies

The `**Depends on:**` bullet governs the dispatch order, and with it the parallelism. Syntax:

```
- **Depends on:** none
- **Depends on:** slice 1
- **Depends on:** slices 1, 3
```

Both singular and plural are valid. What counts are the numbers. `none` declares that the slice has no dependencies.

**The bullet is valid only at the start of a line.** If you mention the bullet name inside the prose of another bullet, avoid the literal with asterisks: write "the dependency declaration", not the quoted name. A lax parser would read the mention instead of the declaration.

**It is referenced by position inside `## Slices`**, not by title or by Issue number: when you write the Spec, the sub-issues do not exist yet. The loop translates those positions into real numbers when it materializes them.

**A dependency always points backwards**, to a slice with a lower position. That way the graph cannot have cycles.

**A dependency always points to a slice of the same Story.** A dependency on an issue outside the Story blocks the slice forever, without any warning.

A slice is dispatchable when **all** its dependencies are merged.

## Parallelism and merge conflicts

Two slices with no dependency between them go out at the same time (up to `--max-parallel-slices`, default `3`, slices in progress per Story, counting those in review or with an open PR). That is where the lead time gain is: while you review one PR, other agents are already working. **Design for parallelism, and design harder against merge conflicts.**

The loop does not resolve merge conflicts. Each agent starts from `master` at dispatch time; when two parallel PRs change the same code, the second one to merge conflicts, and someone rebases it by hand. A conflict costs more than the parallelism saved.

**Two slices are independent only if they do not change the same code.** Functional independence is not enough: two slices with unrelated behavior that edit the same file, the same test file or the same adapter are **not** independent.

While you slice, for each pair of slices with no dependency between them, ask: will both change the same part of the code? You answer from your knowledge of the codebase; you do not write the answer in the Spec. If the answer is yes or "probably":

1. **Move the shared change into an earlier slice** that both depend on (the new port, the new field, the wiring), so that the later slices only add code around it.
2. **Or chain them:** declare the dependency, and accept that they run one after the other.
3. **Or reshape them** so that each one owns a different part of the code.

**Hot spots** that many slices touch and that almost always conflict:

- dependency injection containers, wiring modules and composition roots;
- the CLI entry point, routers and registries of handlers, commands or events;
- shared test fixtures and fakes;
- README, conventions and changelogs;
- lockfiles and dependency manifests;
- sequentially numbered files, such as database migrations.

A change to a hot spot goes into the earliest slice that needs it, and the slices that touch the same hot spot are chained.

**Prefer parallel slices that grow in different places:** a new adapter next to an existing one, a new command next to other commands, a new detector with its own handler. Avoid parallel slices that edit the same function, the same aggregate or the same rendering code.

## Observable verification

Each slice carries its own block, with the project commands and their assert. It runs **after the merge**, on `master`, and is never a requirement to approve the PR.

```markdown
- **Observable verification:**

  After merging to `master`:

  1. `<project command>; echo "exit=$?"` → `exit=0`.
  2. `<command that reads the effect>` → `<expected value>`.

  If any fails: `git revert` the merge commit.
```

Rules: exact commands, with no unresolved variables beyond the test repo or issue; each step checks an observable effect, not an impression. With `--verify-deploy`, the `verifier` agent runs these commands after the merge; without it, they are for the human.

## How it is delivered

```bash
gh issue create \
  --title "Spec: <change title>" \
  --body-file spec.md \
  --label grooveloop \
  --label ready_for_implementation
```

If a loop is already running on the repository, wait for its next tick (`--tick-interval`, `120` s by default). Do not start a second loop on the same repository: both write the same state files. If none is running, start it with `grooveloop loop --repo <owner>/<repo> --workdir <checkout>`.

Then check that the loop has picked it up:

```bash
gh issue view <n> --json labels -q '.labels[].name'
gh issue list --label story:<n> --json number,title,labels
```

The parent Issue gets the `sliced` label and one sub-issue per slice appears, each with `story:<n>`, `order:<n>` and `pending`.

## What the loop does next

Knowing this avoids writing in the Spec things the loop already governs:

- **One sub-issue per slice**, with the slice body and the order and state labels.
- **State lives in labels:** `pending`, `dispatched`, `under_review`, `pr_open`, `changes_requested`, `blocked`, `merged`, `failed`.
- **The agent's PR** carries `Closes #<sub-issue>` and the `grooveloop` label.
- **merge = approve, close = reject.** Review happens in GitHub web.
- **Human directives in comments:** `/grooveloop-implement` asks for another round of changes, `/grooveloop-learn` marks a lesson. A directive counts only at the start of a line: a mention in the middle of prose or in a quote (`>`) does not count.

Do not write in the Spec instructions for the orchestrator, nor states, nor `status: pending`. The loop does not read them.

## Common mistakes

| Mistake | Consequence |
|---|---|
| Delivering a markdown file in the repository | The loop does not see it. It only reads Issues. |
| YAML front matter with `slices:` and `depends_on:` | It is ignored. The contract is `## Slices`, `###` and labels. |
| Forgetting the `grooveloop` label | The Issue is invisible, even with `ready_for_implementation`. |
| Slices as a numbered list instead of `###` | The section ends up empty and the Issue is ignored silently. |
| `Depends on:` with the slice title in prose | Not parseable. Use the position: `slices 1, 3`. |
| A dependency on an issue outside the Story | The slice stays blocked forever, without any warning. |
| Declaring `none` on slices that change the same code | They go out in parallel and the merge conflict is yours. |
| Two parallel slices that touch the same hot spot (DI container, CLI entry point, registry, migrations) | The second PR to merge conflicts. Move the shared change to an earlier slice or chain them. |
| Listing the files or classes each slice changes | The Spec turns into a low-level plan the agent should decide with the code in front of it. |
| A `##` heading inside a slice | It closes the section and the following slices disappear. |
| Detailing the plan of future slices | Each slice is detailed right before starting it, with what was learned from the previous one. |

## Reference

For the size limit, the validity criteria, the nine slicing heuristics, infra isolation and expand/contract, read `slicing-heuristics.md` in this same directory.

## Process

1. Read the specification. If the "what for" or the user is missing, ask before slicing.
2. Answer out loud: does this change replace something already in production? If yes, apply expand/contract or justify the exception, and give those slices the risk block.
3. Identify the walking skeleton: the thinnest vertical slice that proves the full flow in production.
4. Generate the rest of the slices as increments on that skeleton.
5. Check each slice, without writing the answers in the Spec:
   - **Type:** vertical, horizontal (infra, domain, app) or spike. Prefer vertical.
   - **Heuristic:** which one from `slicing-heuristics.md` cuts it.
   - **Size:** its diff fits in 400 lines. If not, split it.
6. Declare `Depends on:` on each slice. Then check every pair of slices with no dependency between them against "Parallelism and merge conflicts", and fix each collision.
7. Write the observable verification block of each slice, with executable commands.
8. Review each slice against the validity criteria and the common mistakes table.
9. Create the Issue with `gh` and its two labels. Check that the loop materializes it.
