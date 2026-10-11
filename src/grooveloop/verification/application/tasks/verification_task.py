from __future__ import annotations

from grooveloop.verification.domain.verification_section import VerificationSection


class VerificationTask:
    def build(self, pull_request: int, title: str, description: str, repo: str) -> str:
        section = VerificationSection.parse(description)

        return (
            f'The slice "{title}" of `{repo}` is merged in the Pull Request #{pull_request}. '
            "Verify that its deployment to production does not degrade the service and that the increment does "
            "what it promised.\n\n"
            "The merge is not the deployment. Wait for the change to reach production by polling periodically "
            "until you see the new version deployed. There is no time limit: if the deployment does not arrive, "
            "keep waiting; a human will unblock you by removing the label if needed.\n\n"
            "Poll **within this same turn**, alternating waits and checks until you see the new revision. "
            "Do not delegate the wait: do not set up background monitors, do not schedule wakeups or deferred "
            "tasks, and do not end the session announcing that you will wait. You run in a headless process: when "
            "you end your turn **the process dies**, any monitor dies with it and nobody wakes you up. If you "
            "finish without publishing the report, the verification hangs forever and the deployment stays "
            "unverified.\n\n"
            "You work in autonomous mode: there is no human in the loop. Do not ask questions or wait for "
            "confirmation; pick reasonable defaults.\n\n"
            "## Verification 1: the deployment does not degrade the service\n\n"
            "Compare the metrics of the new version against the previous one: errors, latency and traffic. If "
            "you cannot get evidence either way, for example because the repository has no observability "
            "configured, the verdict is inconclusive: say what you could not check.\n\n"
            "## Verification 2: the increment does what it promised\n\n"
            f"{self._increment_task(section, repo, pull_request)}\n\n"
            "## Report\n\n"
            "You only report: do not touch the Pull Request (do not edit it, do not push, do not reopen it, do not "
            "close it) or the sub-issue of the slice. Leave EXACTLY ONE comment with your report in the "
            f"conversation of the Pull Request (`gh pr comment {pull_request}`), with the two verdicts in separate "
            'sections: "## Deploy verdict" (degrades / does not degrade / inconclusive) with the metrics that '
            'support it, and "## Increment verdict" with the checks that support it. END it with the marker on '
            "its own line: `<!-- grooveloop:verify-deploy -->`.\n\n"
            "The loop recognizes that marker to consider the verification concluded. Without it, the verification "
            "stays in progress."
        )

    def resumption(self, pull_request: int) -> str:
        return (
            f"Your previous turn ended without publishing the verification report of the Pull Request "
            f"#{pull_request}. Continue from where you left off: if the deployment has not arrived yet, keep polling "
            "within this same turn, without background monitors or wakeups. When you have the two verdicts, leave "
            "EXACTLY ONE comment with your report in the conversation of the Pull Request "
            f'(`gh pr comment {pull_request}`), with "## Deploy verdict" and "## Increment verdict", '
            "that ENDS with the marker on its own line: `<!-- grooveloop:verify-deploy -->`. You only report: "
            "do not touch the Pull Request or the sub-issue. You work in autonomous mode: do not ask questions."
        )

    def _increment_task(self, section: VerificationSection | None, repo: str, pull_request: int) -> str:
        if section is None:
            return (
                "The sub-issue of the slice does not describe what the increment must demonstrate. Do not make it "
                'up: write "no verification section in the sub-issue" as "## Increment verdict" and do not judge '
                "the increment. The deploy verdict does not change because of that."
            )

        return (
            "The sub-issue of the slice describes what the increment must demonstrate as follows. Run the read-only "
            "checks, give a verdict (passes / fails / inconclusive) and declare in the report the ones you cannot "
            "do without mutating state. The steps may come with unresolved placeholders (`<owner>/<repo>`, `<pr>`, "
            f"`<n>`, `<sub-issue>`): replace them with `{repo}` and with the Pull Request #{pull_request} before "
            f"running them.\n\n{section.text}"
        )
