import asyncio
import importlib

from agent_service.schemas.learning_path import (
    KnowledgeGraph,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    LearningPathGenerateRequest,
)


def test_generate_learning_path_recommends_profile_blindspot() -> None:
    learning_path = importlib.import_module("agent_service.agents.learning_path")

    result = learning_path.generate_learning_path_data(
        _build_request(
            profile={"cognitive_blindspots": [{"name": "导数"}]},
            evaluation={},
        )
    )

    assert [(node.id, node.name, node.status, node.order) for node in result.nodes] == [
        ("n1", "函数", "pending", 1),
        ("n2", "导数", "recommended", 2),
        ("n3", "积分", "pending", 3),
    ]
    assert result.current_position is not None
    assert result.current_position.node_id == "n2"
    assert result.current_position.node_name == "导数"


def test_generate_learning_path_uses_mastery_for_completed_and_in_progress_status() -> None:
    learning_path = importlib.import_module("agent_service.agents.learning_path")

    result = learning_path.generate_learning_path_data(
        _build_request(
            profile={"knowledge_coordinates": [{"name": "函数", "mastery": 90}, {"name": "导数", "mastery": 45}]},
            evaluation={},
        )
    )

    assert [(node.name, node.status, node.mastery) for node in result.nodes] == [
        ("函数", "completed", 90.0),
        ("导数", "in_progress", 45.0),
        ("积分", "pending", None),
    ]
    assert result.current_position is not None
    assert result.current_position.node_id == "n2"


def test_generate_learning_path_preserves_graph_edges() -> None:
    learning_path = importlib.import_module("agent_service.agents.learning_path")

    result = learning_path.generate_learning_path_data(_build_request(profile={}, evaluation={}))

    assert [(edge.from_, edge.to) for edge in result.edges] == [("n1", "n2"), ("n2", "n3")]


# ── generate_learning_path_with_llm tests ──────────────────────────


class FakeChatProvider:
    def __init__(self, output: str | None = None, should_raise: bool = False, fail_structured: bool = False) -> None:
        self.calls: list[tuple[list, dict]] = []
        self._output = output
        self._should_raise = should_raise
        self._fail_structured = fail_structured

    async def complete(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if self._should_raise:
            raise RuntimeError("LLM unavailable")
        if self._fail_structured and "structured_model" in kwargs:
            raise RuntimeError("structured_model failed")
        return self._output


def test_llm_path_structured_model_succeeds() -> None:
    from agent_service.agents.learning_path import generate_learning_path_with_llm

    provider = FakeChatProvider(
        output=(
            '{"nodes":['
            '{"id":"n1","status":"completed","mastery":90,"order":1,"reason":"已掌握"}],'
            '"current_position":{"node_id":"n1"}}'
        )
    )
    result = asyncio.run(
        generate_learning_path_with_llm(_build_request({}, {}), provider)
    )
    assert result is not None
    assert "structured_model" in provider.calls[0][1]
    assert len(result.nodes) == 1
    assert result.nodes[0].id == "n1"


def test_llm_path_structured_model_fails_and_falls_back() -> None:
    from agent_service.agents.learning_path import generate_learning_path_with_llm

    provider = FakeChatProvider(
        output=(
            '```json\n'
            '{"nodes":['
            '{"id":"n1","status":"completed","mastery":90,"order":1,"reason":"已掌握"}],'
            '"current_position":{"node_id":"n1"}}'
            '\n```'
        ),
        fail_structured=True
    )
    result = asyncio.run(
        generate_learning_path_with_llm(_build_request({}, {}), provider)
    )
    assert result is not None
    assert len(provider.calls) == 2
    assert "structured_model" in provider.calls[0][1]
    assert "structured_model" not in provider.calls[1][1]
    assert len(result.nodes) == 1
    assert result.nodes[0].id == "n1"


def test_llm_path_backfills_name_and_preserves_edges() -> None:
    from agent_service.agents.learning_path import generate_learning_path_with_llm

    provider = FakeChatProvider(
        output=(
            '{"nodes":['
            '{"id":"n1","status":"completed","mastery":90,"order":1,"reason":"已掌握"},'
            '{"id":"n2","status":"recommended","mastery":40,"order":2,"reason":"薄弱点"},'
            '{"id":"n3","status":"pending","mastery":0,"order":3,"reason":"未学习"}],'
            '"current_position":{"node_id":"n2"}}'
        )
    )
    result = asyncio.run(
        generate_learning_path_with_llm(_build_request({}, {}), provider)
    )

    assert result is not None
    assert [(n.id, n.name, n.status, n.order) for n in result.nodes] == [
        ("n1", "函数", "completed", 1),
        ("n2", "导数", "recommended", 2),
        ("n3", "积分", "pending", 3),
    ]
    assert [(e.from_, e.to) for e in result.edges] == [("n1", "n2"), ("n2", "n3")]
    assert result.current_position is not None
    assert result.current_position.node_id == "n2"
    assert result.current_position.node_name == "导数"


def test_llm_path_discards_unknown_node_ids() -> None:
    from agent_service.agents.learning_path import generate_learning_path_with_llm

    provider = FakeChatProvider(
        output=(
            '{"nodes":['
            '{"id":"n1","status":"completed","mastery":90,"order":1,"reason":"ok"},'
            '{"id":"n99","status":"recommended","mastery":50,"order":2,"reason":"unknown"}],'
            '"current_position":{"node_id":"n1"}}'
        )
    )
    result = asyncio.run(
        generate_learning_path_with_llm(_build_request({}, {}), provider)
    )

    assert result is not None
    assert len(result.nodes) == 1
    assert result.nodes[0].id == "n1"


def test_llm_path_ignores_name_from_llm_output() -> None:
    from agent_service.agents.learning_path import generate_learning_path_with_llm

    provider = FakeChatProvider(
        output=(
            '{"nodes":['
            '{"id":"n1","name":"LLM编造的名称","status":"completed","mastery":90,"order":1,"reason":"ok"}],'
            '"current_position":null}'
        )
    )
    result = asyncio.run(
        generate_learning_path_with_llm(_build_request({}, {}), provider)
    )

    assert result is not None
    assert result.nodes[0].name == "函数"  # backfilled from input, not "LLM编造的名称"


def test_llm_path_current_position_falls_back_on_unknown_node() -> None:
    from agent_service.agents.learning_path import generate_learning_path_with_llm

    provider = FakeChatProvider(
        output=(
            '{"nodes":['
            '{"id":"n1","status":"pending","mastery":0,"order":1,"reason":"new"}],'
            '"current_position":{"node_id":"n99"}}'
        )
    )
    result = asyncio.run(
        generate_learning_path_with_llm(_build_request({}, {}), provider)
    )

    assert result is not None
    # n99 unknown, falls back to first node (n1, pending)
    assert result.current_position is not None
    assert result.current_position.node_id == "n1"


def test_llm_path_returns_none_on_invalid_json() -> None:
    from agent_service.agents.learning_path import generate_learning_path_with_llm

    result = asyncio.run(
        generate_learning_path_with_llm(
            _build_request({}, {}), FakeChatProvider(output="not json")
        )
    )
    assert result is None


def test_llm_path_returns_none_when_provider_is_none() -> None:
    from agent_service.agents.learning_path import generate_learning_path_with_llm

    result = asyncio.run(
        generate_learning_path_with_llm(_build_request({}, {}), None)
    )
    assert result is None


def test_llm_path_returns_none_when_llm_raises() -> None:
    from agent_service.agents.learning_path import generate_learning_path_with_llm

    result = asyncio.run(
        generate_learning_path_with_llm(
            _build_request({}, {}), FakeChatProvider(should_raise=True)
        )
    )
    assert result is None


def _build_request(profile: dict, evaluation: dict) -> LearningPathGenerateRequest:
    return LearningPathGenerateRequest(
        user_id="user-1",
        course_id="course-1",
        evaluation=evaluation,
        profile=profile,
        knowledge_graph=KnowledgeGraph(
            nodes=[
                KnowledgeGraphNode(id="n1", name="函数", chapter="第一章"),
                KnowledgeGraphNode(id="n2", name="导数", chapter="第二章"),
                KnowledgeGraphNode(id="n3", name="积分", chapter="第三章"),
            ],
            edges=[
                KnowledgeGraphEdge.model_validate({"from": "n1", "to": "n2"}),
                KnowledgeGraphEdge.model_validate({"from": "n2", "to": "n3"}),
            ],
        ),
    )
