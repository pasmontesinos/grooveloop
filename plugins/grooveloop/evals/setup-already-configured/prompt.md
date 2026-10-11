---
max_turns: 25
timeout_seconds: 600
allowed_tools: [Skill, Read, Glob, Grep]
runs: 3
---

Check whether the `acme/billing` repository needs changes to its configuration for the grooveloop loop. The current directory is its checkout.

There is no `git`, `gh` or `grooveloop` in this environment: wherever you need to run them, say which command you would run and take what I tell you here as the result.

Repository state:

- `CLAUDE.md` has no `@import`; it names the conventions by their path.
- `docs/conventions/` contains `code-style.md`, `domain.md` and `testing.md`.
- `.grooveloop/agents/developer.md` exists and contains only this front matter, with no body:

  ```
  ---
  context_files:
    - docs/conventions/code-style.md
    - docs/conventions/domain.md
    - docs/conventions/testing.md
  ---
  ```

- `git check-ignore -q .grooveloop/agents/developer.md` exits with 0 thanks to `.git/info/exclude`, and `git ls-files .grooveloop` lists nothing.
- The repository already has the `grooveloop` and `ready_for_implementation` labels.
- `grooveloop doctor --workdir .` exits with 0.
- The profiles of the installed package are `developer`, `reviewer`, `scribe` and `verifier`, with `engine: claude` and `context_files: []`.

My answers, so you do not have to ask me: I keep the local overrides as they are, with the same engine, model and conventions, and no preferred skills.
