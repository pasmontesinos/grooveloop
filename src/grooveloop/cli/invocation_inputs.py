from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.delivery.infrastructure.auto_merge import AutoMerge
from grooveloop.delivery.infrastructure.journal_enabled import JournalEnabled
from grooveloop.delivery.infrastructure.max_parallel_slices import MaxParallelSlices
from grooveloop.delivery.infrastructure.max_review_rounds import MaxReviewRounds
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.max_retries import MaxRetries
from grooveloop.shared.infrastructure.target_repo import TargetRepo
from grooveloop.slicing.infrastructure.verify_deploy import VerifyDeploy


def bind_invocation_inputs(
    repo_full_name: str,
    workdir: str,
    *,
    verify_deploy: bool = False,
    max_review_rounds: int = 0,
    max_parallel_slices: int = 1,
    journal_enabled: bool = False,
    max_retries: int = 0,
    auto_merge: bool = False,
) -> None:
    container.bind(TargetRepo, TargetRepo(repo_full_name))
    container.bind(AgentWorkdir, AgentWorkdir(workdir))
    container.bind(VerifyDeploy, VerifyDeploy(verify_deploy))
    container.bind(MaxReviewRounds, MaxReviewRounds(max_review_rounds))
    container.bind(MaxParallelSlices, MaxParallelSlices(max_parallel_slices))
    container.bind(JournalEnabled, JournalEnabled(journal_enabled))
    container.bind(MaxRetries, MaxRetries(max_retries))
    container.bind(AutoMerge, AutoMerge(auto_merge))
