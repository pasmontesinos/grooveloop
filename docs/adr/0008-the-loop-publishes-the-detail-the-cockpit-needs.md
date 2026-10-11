# ADR-0008: The loop publishes the detail the watch cockpit needs

## Status

Accepted — 2026-09-24

## Context

[ADR-0007](0007-decoupled-execution-and-viewing-watch-in-textual.md) separates execution and viewing: the loop writes state files and the watch only reads them.

The watch becomes a **review cockpit**: the place where the human follows the runs, reads the Story's Spec and journal and reviews each slice's PR without opening the GitHub web UI. For that it needs data that does not reach the state files today:

- each slice's dependencies, to show what it needs and what it unblocks;
- the Story's Spec;
- the detail of each open PR: body, files with their changes, patches, comments, checks and whether it can be merged.

Most of it already goes through the tick: `GithubStoryGraph` brings the body of the Story and of each sub-issue, and the conversation and inline comments of each PR. Missing are the PR body and stats, the checks, `mergeable`, `updatedAt`, `headRefOid` and the patches, which GraphQL does not offer.

## Decision

- **The watch still does not read from GitHub and does not write.** Everything it shows comes from the state files. The only way out is opening a URL in the browser.
- **The loop publishes the detail for the viewer in `~/.grooveloop/repos/<repo>/`:**

  | File | Content | When it is written |
  |---|---|---|
  | `snapshot.json` | what it has today, plus each slice's dependencies and the summary of its open PR (+/−, files, checks, `mergeable`, `updatedAt`, `headRefOid`) | on every tick |
  | `stories/<n>/spec.md` | the Story body | when it changes |
  | `pulls/<n>.json` | body, files with +/− and patch, conversation and inline comments, checks | when `updatedAt` or `headRefOid` change for an open PR, of a slice or of the conventions of an unresolved lesson; it is deleted when the PR closes |

- **Only open PRs have detail.** A merged slice keeps its PR summary in the snapshot, but not its diff or its comments.
- **Detect by change.** The tick's GraphQL query asks for `updatedAt` and `headRefOid` of each open PR. The full detail and the patches (REST) are only requested when one of the two changes. A tick with no news costs the same as before.
- **A failure syncing a PR does not abort the tick.** The loop keeps the previous file and the watch shows its age.
- **Atomic and versioned writes.** Each file is written with a temporary file and `os.replace`, and carries a `version` field. The watch treats a version it does not know as unreadable, without breaking the rest of the screen.
- **The detail is instrumentation, not domain state** ([ADR-0003](0003-hybrid-state-and-log-instrumentation.md)). It is written by a publisher, like the snapshot; it is not an aggregate repository.

## Consequences

- The tick does more work only when a PR changes: one detail query and one REST call for files per changed PR.
- The watch reads each detail file only when the user focuses its element, and only if its `mtime` changed. The every-second refresh still reads only the snapshot and the runs.
- What the watch shows of a PR is up to one tick interval old. The watch says so.
- **Merging from the watch remains open.** When it comes, it will be a direct write to the GitHub API through an explicit user action, never the agent's, and it will need its own ADR.

## Alternatives considered

- **The watch reads GitHub directly:** rejected. It breaks the ADR-0007 contract, duplicates the access to GitHub and puts it in the every-second refresh.
- **All the detail inside `snapshot.json`:** rejected. The snapshot would grow with the patches, would be rewritten whole on each tick and the watch would decode it every second.
- **A sync timer separate from the tick:** rejected. It adds a second clock to the loop, and the PR could run ahead of or behind its slice's state.
- **Detail for closed PRs too:** rejected for now. A closed PR no longer changes, and reviewing its diff is a rare case.
