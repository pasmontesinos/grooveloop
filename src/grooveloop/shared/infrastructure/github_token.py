from __future__ import annotations

import subprocess


class GithubTokenError(Exception): ...


def github_token() -> str:
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        raise GithubTokenError("Could not obtain a GitHub token from `gh auth token`") from error

    return result.stdout.strip()
