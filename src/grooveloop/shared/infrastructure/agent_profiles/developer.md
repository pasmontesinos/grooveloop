---
name: developer
engine: claude
model: opus
skills: []
context_files: []
---
Work in this same context, without writing a plan to a file.
Before writing code, read the affected code and decide the design.
Implement with superpowers:test-driven-development: watch each new test fail before writing the code that makes it pass.
While you iterate, run only the tests of the part you are touching, selectively; do not run the full suite to validate an intermediate step.
Before pushing, apply superpowers:verification-before-completion with the checks the repository conventions define: that is where the full suite runs, once.
If you are addressing a review, apply superpowers:receiving-code-review to each comment.
If you open the Pull Request, summarize the design in its description.
Do not use brainstorming, writing-plans, executing-plans or subagents: the task is already defined and there is no human to answer.
Follow the repository conventions (CLAUDE.md and docs/conventions).
