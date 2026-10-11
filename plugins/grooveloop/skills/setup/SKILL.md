---
name: setup
description: This skill should be used when preparing a repository for the grooveloop orchestrator to drive, or when reviewing and adjusting the configuration of one it already drives. It triggers on "configure this repo for the loop", "prepare the repo for grooveloop", "adjust the loop profiles", "which conventions does each agent read", "review the loop configuration", or when starting the loop on a new repository.
---

# Configure a repository for grooveloop

## Overview

The loop drives a repository from three pieces that live outside its code: the **profile overrides** in `<workdir>/.grooveloop/agents/`, the repository **`CLAUDE.md`** and the **labels** the loop reads and does not create. This skill takes an inventory of those pieces, proposes the configuration, asks what the human decides, applies only what changes and leaves validation to `grooveloop doctor`.

**Split rule:** what affects the repository team (`CLAUDE.md`) arrives by Pull Request. The personal loop configuration (the overrides) stays local, unless the human chooses to version it.

**If the configuration is already up to date, nothing is written:** no files, no branch, no commit, no Pull Request.

## When to use this skill

- You are about to run the loop on a repository it has never driven.
- You want to change the engine, the model, the conventions or the skills of a persona.
- You suspect the configuration of a repository already driven has fallen behind.

Do not use it to write the Spec of a Story: that is `grooveloop:slicing`.

## Process

Follow the steps in order. If the human already gave an answer in the conversation, use it and do not ask again. Ask one question at a time and always propose a default value.

### 1. Get your bearings

- The **workdir** is the local checkout of the target repository; the **repo** is its `owner/name` on GitHub (`gh repo view --json nameWithOwner`). They must correspond to the same repository: the loop gives the agent the code of `--workdir`, not that of `--repo`.
- Check that `grooveloop --help` and `gh auth status` respond. If not, stop and say what is missing.

### 2. Inventory

Collect the current state and show it in a table before proposing anything:

| Piece | How to read it |
|---|---|
| `CLAUDE.md` | Read it whole; note each `@docs/...` line (an `@import` is always loaded, in every session). |
| Conventions | `wc -c docs/conventions/*.md`. Approximate cost: bytes / 4 tokens per file, and the total. |
| Package profiles | `find "$(uv tool dir)/grooveloop" -path '*grooveloop/shared/infrastructure/agent_profiles/*.md'`. Read their front matter (`engine`, `model`, `skills`, `context_files`). They are the base the overrides are applied on. |
| Current overrides | `ls .grooveloop/agents/` and read each one. |
| Override versioning | `git ls-files .grooveloop` (versioned) and `git check-ignore -q .grooveloop/agents/<profile>.md` (ignored). |
| Labels | `gh label list --repo <repo> --search grooveloop` and `--search ready_for_implementation`. |

Read the profiles of the installed package, do not recall them: they change with every loop version.

### 3. Decide each persona

The personas are `developer` (implements the slice), `reviewer` (reviews the PR before the human), `scribe` (refines the conventions with the lessons) and `verifier` (verifies the deploy). For each one, ask:

- **Engine** (`engine`): `claude` or `opencode`.
- **Model** (`model`): one that engine accepts.
- **Conventions** (`context_files`): paths relative to the workdir that the agent will read with the Read tool before starting. Show their token cost when you propose them. Default proposal for a repo with `docs/conventions/`:
  - `developer`: all of them, including git-workflow (it creates the branch, commits and PR).
  - `reviewer`: all except git-workflow (it does not commit).
  - `scribe`: all of them (it edits the conventions and opens a PR).
  - `verifier`: none, unless the loop will run with `--verify-deploy` (ask; by default it will not). In that case, propose the file of the repository that says where the errors, latency and traffic of each service are, and how to tell one version from another. Without it, the deploy verdict is always `inconclusive`.
- **Preferred skills** (`skills`): the agent loads them with the Skill tool before starting. The `scribe` loads `grooveloop:conventions` by default. With `--verify-deploy`, propose for the `verifier` `grooveloop:verify` plus the skills of the team that query its observability sources, if the catalog has them.

**Check each skill against this session's catalog:** the list of available skills you see in your context. A skill goes in only if its name appears there exactly, with the plugin prefix (`superpowers:test-driven-development`, not `superpowers` or `test-driven-development`). If it does not appear, tell the human and do not write it.

**Check the skills the package personas name.** The default `developer` persona names `superpowers:test-driven-development`, `superpowers:verification-before-completion` and `superpowers:receiving-code-review`. If they are not in the catalog, tell the human: the agent cannot load them. Propose to install the superpowers plugin or to override the `developer` persona with one that names skills that exist. Do not write that override unless the human chooses it.

### 4. Compute the overrides

An override carries **only the fields that differ from the package profile**. It inherits the rest, and that way the repository keeps receiving the package improvements.

- **Never write a body after the front matter.** The body is the persona, and an override with a body replaces the package persona.
- Do not write `name`: the file name gives it.
- A list field (`skills`, `context_files`) **replaces the whole** package list, it does not add to it. To add a skill to the `verifier`, repeat `grooveloop:verify`; to the `scribe`, repeat `grooveloop:conventions`.
- If a persona changes nothing, it has no file.

Format, with block lists:

```markdown
---
context_files:
  - docs/conventions/code-style.md
  - docs/conventions/testing.md
---
```

Compare each computed override with the existing one. If they match, that persona is up to date.

### 5. Override versioning

Ask whether they are versioned. **By default, no:** they are personal loop configuration.

- **Local (default):** if `git check-ignore` does not ignore them, add `.grooveloop/` to `.git/info/exclude`. Do not add it to `.gitignore`: that would be a versioned change and would go into the Pull Request. If `git ls-files .grooveloop` already lists them, warn: stopping versioning them is a `git rm --cached` that the human decides.
- **Versioned:** check that git does not ignore them and add them to the Pull Request.

### 6. Propose the `CLAUDE.md`

The loop tells each persona which conventions to read with `context_files`, so `CLAUDE.md` does not import them.

- Remove each `@docs/conventions/...` line and replace it with a reference to the path in text (for example, a table "if you are going to touch X, read `docs/conventions/x.md`"), so that an interactive session still knows where they are.
- Do not touch the rest of the file or the content of the conventions.
- If `CLAUDE.md` has no convention `@import`, it does not change.

Show the diff to the human before applying it.

### 7. Plan, confirmation and application

Summarize in a list what you are going to change: overrides you write, local exclusion, `CLAUDE.md`, missing labels and the Pull Request. **If the list is empty, say the configuration is up to date and jump to step 8.**

With the human's confirmation:

1. Write the overrides to `<workdir>/.grooveloop/agents/<profile>.md`.
2. Create only the missing labels: `gh label create grooveloop --repo <repo>` and `gh label create ready_for_implementation --repo <repo>`.
3. If `CLAUDE.md` changes (or the overrides are versioned), open the Pull Request following the git workflow of the target repository: new branch from its main branch, a commit with only those files and `gh pr create`. Check with `git status --porcelain` that no local override slipped into the commit.

### 8. Validate

Run `grooveloop doctor --workdir <workdir>` and show its output. It must exit with 0; if it fails (for example, a `context_files` entry that does not exist), fix the override and repeat.

Finish with the command to start the loop: `grooveloop loop --repo <repo> --workdir <workdir>`.

## Common mistakes

| Mistake | Consequence |
|---|---|
| Copying the whole package profile into the override | The repository stops receiving the improvements of the package persona. |
| Adding `.grooveloop/` to `.gitignore` | The Pull Request carries a file the team does not need. |
| Declaring a skill by a name that is not in the catalog | The agent cannot load it and the instruction has no effect. |
| Keeping `@docs/conventions/...` in `CLAUDE.md` | Every session pays the cost of all the conventions, on top of what the profile orders. |
| Opening a Pull Request or writing files with no pending changes | Noise in a repository that was already up to date. |
