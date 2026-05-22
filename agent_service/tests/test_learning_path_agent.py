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
