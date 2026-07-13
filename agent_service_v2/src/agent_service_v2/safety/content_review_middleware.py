from __future__ import annotations

import asyncio
from dataclasses import replace

from agent_service_v2.safety.content_review_client import (
    ContentReviewClient,
)
from agent_service_v2.safety.schemas import ContentSafetyReview
from agent_service_v2.safety.local_wordlist import LocalSensitiveWordFilter


class ContentSafetyReviewer:
    def __init__(
        self,
        client: ContentReviewClient | None = None,
        *,
        timeout_seconds: float = 3.0,
    ) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._local = LocalSensitiveWordFilter()

    async def review(self, content: str) -> ContentSafetyReview:
        if not content.strip():
            return ContentSafetyReview.skipped("empty_content")
        count = self._local.matches(content)
        if count == 0:
            return self._local_allow_review()
        if self._client is None:
            return self.local_block_review(count)
        try:
            review = await asyncio.wait_for(
                self._client.review(content),
                timeout=self._timeout_seconds,
            )
        except Exception:
            return self.local_block_review(
                count,
                reason="semantic_review_unavailable",
            )
        return replace(review.normalized(), match_count=count)

    @staticmethod
    def local_block_review(
        match_count: int,
        *,
        reason: str = "sensitive_content_detected",
    ) -> ContentSafetyReview:
        return ContentSafetyReview(
            passed=False,
            risk_level="critical",
            categories=["sensitive_content"],
            reason=reason,
            action="block",
            confidence=1.0,
            reviewer="local_wordlist",
            match_count=match_count,
        ).normalized()

    @staticmethod
    def _local_allow_review() -> ContentSafetyReview:
        return ContentSafetyReview(
            passed=True,
            risk_level="none",
            categories=[],
            reason="local_wordlist_clear",
            action="allow",
            confidence=1.0,
            reviewer="local_wordlist",
            match_count=0,
        ).normalized()
