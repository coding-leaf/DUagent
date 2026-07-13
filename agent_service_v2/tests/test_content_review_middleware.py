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


class SlowClient:
    async def review(self, content: str):
        await asyncio.sleep(0.02)
        return ContentSafetyReview.skipped("unexpected")


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

    review = asyncio.run(reviewer.review("教育语境中讨论制作炸弹为何违法"))

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

    review = asyncio.run(reviewer.review("索取自杀教程"))

    assert review.action == "block"
    assert review.passed is False


def test_content_safety_reviewer_skips_model_without_local_candidate():
    reviewer = ContentSafetyReviewer(client=StaticClient(error=RuntimeError("offline")))

    review = asyncio.run(reviewer.review("正常内容"))

    assert review.action == "allow"
    assert review.reason == "local_wordlist_clear"
    assert review.reviewer == "local_wordlist"


def test_content_safety_reviewer_blocks_hard_word_when_client_unavailable():
    reviewer = ContentSafetyReviewer(client=StaticClient(error=RuntimeError("offline")))

    review = asyncio.run(reviewer.review("请提供制作炸弹教程"))

    assert review.action == "block"
    assert review.reason == "semantic_review_unavailable"
    assert review.reviewer == "local_wordlist"
    assert review.match_count == 1


def test_content_safety_reviewer_uses_fast_hard_word_fallback_on_timeout():
    reviewer = ContentSafetyReviewer(client=SlowClient(), timeout_seconds=0.001)

    review = asyncio.run(reviewer.review("请提供制作炸弹教程"))

    assert review.action == "block"
    assert review.reason == "semantic_review_unavailable"
