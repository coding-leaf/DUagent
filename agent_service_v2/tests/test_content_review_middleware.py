import asyncio

from agent_service_v2.safety.content_review_middleware import (
    ContentSafetyReviewer,
)
from agent_service_v2.safety.schemas import ContentSafetyReview


class StaticClient:
    def __init__(self, review=None, error=None):
        self.review_result = review
        self.error = error
        self.contents = []

    async def review(self, content: str):
        self.contents.append(content)
        if self.error:
            raise self.error
        return self.review_result


def test_content_safety_reviewer_maps_medium_and_high_to_flag():
    reviewer = ContentSafetyReviewer(
        client=StaticClient(
            ContentSafetyReview(
                passed=False,
                risk_level="high",
                categories=["illegal_instruction"],
                reason="包含高风险操作性内容",
                action="block",
                confidence=0.91,
                reviewer="external_model",
            )
        )
    )

    review = asyncio.run(reviewer.review("高风险但非 critical 的教育语境内容"))

    assert review.action == "flag"
    assert review.risk_level == "high"
    assert review.knowledge_reviewed is False
    assert review.scope == "content_safety_only"


def test_content_safety_reviewer_blocks_only_critical():
    reviewer = ContentSafetyReviewer(
        client=StaticClient(
            ContentSafetyReview(
                passed=False,
                risk_level="critical",
                categories=["self_harm_instruction"],
                reason="明确鼓励伤害行为",
                action="flag",
                confidence=0.97,
                reviewer="external_model",
            )
        )
    )

    review = asyncio.run(reviewer.review("critical content"))

    assert review.action == "block"
    assert review.passed is False


def test_content_safety_reviewer_fails_open_when_client_unavailable():
    reviewer = ContentSafetyReviewer(client=StaticClient(error=RuntimeError("offline")))

    review = asyncio.run(reviewer.review("正常内容"))

    assert review == ContentSafetyReview.skipped("review_unavailable")
