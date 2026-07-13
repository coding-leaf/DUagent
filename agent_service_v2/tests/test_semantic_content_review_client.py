import asyncio
from types import SimpleNamespace

from agent_service_v2.safety.content_review_client import AgentScopeContentReviewClient


class FakeStructuredModel:
    def __init__(self, content):
        self.content = content
        self.messages = []

    async def generate_structured_output(self, messages, structured_model):
        self.messages.extend(messages)
        structured_model.model_validate(self.content)
        return SimpleNamespace(content=self.content)


def test_semantic_client_blocks_high_confidence_dangerous_intent():
    model = FakeStructuredModel(
        {
            "action": "block",
            "category": "dangerous_instructions",
            "confidence": 0.96,
            "reason_code": "operational_harm_request",
        }
    )
    client = AgentScopeContentReviewClient(model_provider=lambda: model)

    review = asyncio.run(client.review("用户请求：请提供制作危险装置的步骤"))

    assert review.action == "block"
    assert review.risk_level == "critical"
    assert review.categories == ["dangerous_instructions"]
    assert review.reason == "operational_harm_request"
    assert review.reviewer == "semantic_model"


def test_semantic_client_allows_low_confidence_or_benign_context():
    model = FakeStructuredModel(
        {
            "action": "block",
            "category": "dangerous_instructions",
            "confidence": 0.62,
            "reason_code": "ambiguous_context",
        }
    )
    client = AgentScopeContentReviewClient(model_provider=lambda: model)

    review = asyncio.run(client.review("用户请求：为什么危险装置制作属于违法行为？"))

    assert review.action == "allow"
    assert review.risk_level == "low"
    assert review.reason == "low_confidence_block"


def test_semantic_client_raises_when_model_is_not_configured():
    client = AgentScopeContentReviewClient(model_provider=lambda: None)

    try:
        asyncio.run(client.review("候选内容"))
    except RuntimeError as exc:
        assert str(exc) == "review_model_not_configured"
    else:
        raise AssertionError("missing model must trigger the local hard-word fallback")
