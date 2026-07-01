from __future__ import annotations

from typing import Protocol

from agent_service_v2.safety.schemas import ContentSafetyReview


class ContentReviewClient(Protocol):
    async def review(self, content: str) -> ContentSafetyReview:
        ...


class SkippedContentReviewClient:
    async def review(self, content: str) -> ContentSafetyReview:
        return ContentSafetyReview.skipped("review_model_not_configured")
