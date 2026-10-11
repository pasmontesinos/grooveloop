from __future__ import annotations

from enum import StrEnum


class AgentTaskType(StrEnum):
    IMPLEMENT_SLICE = "implement_slice"
    ADDRESS_REVIEW = "address_review"
    REVIEW_SLICE = "review_slice"
    REFINE_CONVENTIONS = "refine_conventions"
    VERIFY_DEPLOY = "verify_deploy"
