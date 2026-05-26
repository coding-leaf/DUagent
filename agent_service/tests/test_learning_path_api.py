import asyncio

from agent_service.api.v1 import learning_path as learning_path_api
from agent_service.schemas.learning_path import (
    KnowledgeGraph,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    LearningPathGenerateRequest,
)


def _build_request() -> LearningPathGenerateRequest:
    return LearningPathGenerateRequest(
        user_id="user-1",
        course_id="course-1",
        evaluation={},
        profile={},
        knowledge_graph=KnowledgeGraph(
            nodes=[
                KnowledgeGraphNode(id="n1", name="函数", chapter="第一章"),
                KnowledgeGraphNode(id="n2", name="导数", chapter="第二章"),
            ],
            edges=[KnowledgeGraphEdge.model_validate({"from": "n1", "to": "n2"})],
        ),
    )


def test_learning_path_api_uses_llm_when_llm_succeeds(monkeypatch) -> None:
    from agent_service.agents.learning_path import LearningPathData

    class FakeProviders:
        chat = object()

    monkeypatch.setattr(learning_path_api, "get_ai_providers", lambda: FakeProviders())

    async def fake_llm(request, chat_provider):
        return LearningPathData(nodes=[], edges=[], current_position=None)

    monkeypatch.setattr(
        learning_path_api, "generate_learning_path_with_llm", fake_llm
    )

    response = asyncio.run(learning_path_api.generate_learning_path(_build_request()))
    assert response.code == 200
    assert response.data is not None
    assert response.data.nodes == []


def test_learning_path_api_falls_back_when_llm_returns_none(monkeypatch) -> None:
    class FakeProviders:
        chat = object()

    monkeypatch.setattr(learning_path_api, "get_ai_providers", lambda: FakeProviders())

    async def fake_llm_none(request, chat_provider):
        return None

    monkeypatch.setattr(
        learning_path_api, "generate_learning_path_with_llm", fake_llm_none
    )

    response = asyncio.run(learning_path_api.generate_learning_path(_build_request()))
    assert response.code == 200
    assert [n.id for n in response.data.nodes] == ["n1", "n2"]
