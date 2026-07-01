from __future__ import annotations

from agent_service_v2.safety.content_review_client import (
    ContentReviewClient,
    SkippedContentReviewClient,
)
from agent_service_v2.safety.schemas import ContentSafetyReview


class ContentSafetyReviewer:
    def __init__(self, client: ContentReviewClient | None = None) -> None:
        self._client = client or SkippedContentReviewClient()

    async def review(self, content: str) -> ContentSafetyReview:
        if not content.strip():
            return ContentSafetyReview.skipped("empty_content")
        try:
            review = await self._client.review(content)
        except Exception:
            return ContentSafetyReview.skipped("review_unavailable")
        return review.normalized()
