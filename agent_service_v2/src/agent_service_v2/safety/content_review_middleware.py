from __future__ import annotations

from agent_service_v2.safety.content_review_client import (
    ContentReviewClient,
)
from agent_service_v2.safety.schemas import ContentSafetyReview
from agent_service_v2.safety.local_wordlist import LocalSensitiveWordFilter


class ContentSafetyReviewer:
    def __init__(self, client: ContentReviewClient | None = None) -> None:
        self._client = client
        self._local = LocalSensitiveWordFilter()

    async def review(self, content: str) -> ContentSafetyReview:
        if not content.strip():
            return ContentSafetyReview.skipped("empty_content")
        if self._client is None:
            count = self._local.matches(content)
            return ContentSafetyReview(
                passed=count == 0,
                risk_level="high" if count else "none",
                categories=["sensitive_content"] if count else [],
                reason="sensitive_content_detected" if count else "local_wordlist_clear",
                action="flag" if count else "allow",
                confidence=1.0,
                reviewer="local_wordlist",
                match_count=count,
            ).normalized()
        try:
            review = await self._client.review(content)
        except Exception:
            return ContentSafetyReview.skipped("review_unavailable")
        return review.normalized()
