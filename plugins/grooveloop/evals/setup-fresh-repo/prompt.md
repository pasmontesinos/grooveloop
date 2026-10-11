---
max_turns: 25
timeout_seconds: 600
allowed_tools: [Skill, Read, Glob, Grep]
runs: 3
---

Prepare the `acme/billing` repository for the grooveloop loop to drive it. The current directory is its checkout.

There is no `git`, `gh` or `grooveloop` in this environment: wherever you need to run them, say which command you would run and take what I tell you here as the result.

Repository state:

- `CLAUDE.md` has these lines, besides its own text:
  - `@docs/conventions/code-style.md`
  - `@docs/conventions/domain.md`
  - `@docs/conventions/testing.md`
  - `@docs/conventions/git-workflow.md`
- `docs/conventions/` contains `code-style.md` (2,400 bytes), `domain.md` (9,800 bytes), `testing.md` (6,100 bytes) and `git-workflow.md` (1,900 bytes).
- `.grooveloop/` does not exist. No `.gitignore` mentions `.grooveloop`.
- The repository does not have the `grooveloop` or `ready_for_implementation` labels.
- The profiles of the installed package are `developer`, `reviewer`, `scribe` and `verifier`, all with `engine: claude`, `skills: []` and `context_files: []` except `verifier`, which declares `skills: [grooveloop:verify]`. `developer`, `reviewer` and `scribe` use `model: opus`; `verifier` uses `model: sonnet`. Each one carries its persona in the body.

My answers, so you do not have to ask me: I keep the engine and model of every profile. The `developer` and the `scribe` read the four conventions; the `reviewer`, all except `git-workflow.md`. I do not want preferred skills. I do not want to version the overrides. I approve the changes you propose.

Do not write files: show in your reply the path and the exact content of each file you would write or change, and finish with a summary of what the Pull Request to the repository would contain.
