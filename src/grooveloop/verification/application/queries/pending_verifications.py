from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.application.queries.pending_verifications import (
    PendingVerificationsQuery,
    PendingVerificationsQueryResult,
)
from grooveloop.shared.application.queries.query_handler import QueryHandler
from grooveloop.verification.domain.story_id import StoryId

if TYPE_CHECKING:
    from grooveloop.verification.domain.slice_verification_repository import SliceVerificationRepository


class PendingVerificationsQueryHandler(QueryHandler[PendingVerificationsQuery, PendingVerificationsQueryResult]):
    def __init__(self, slice_verification_repository: SliceVerificationRepository) -> None:
        self._slice_verification_repository = slice_verification_repository

    def __call__(self, query: PendingVerificationsQuery) -> PendingVerificationsQueryResult:
        verifications = self._slice_verification_repository.search(story_id=StoryId(query.story_id))

        return PendingVerificationsQueryResult(
            slice_ids=[verification.slice_id.value for verification in verifications if verification.is_pending()]
        )
