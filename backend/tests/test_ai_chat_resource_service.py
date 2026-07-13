from types import SimpleNamespace

from app.services.ai_chat_resource_service import (
    build_ai_chat_resource_task_id,
    score_personalized_resource,
)


def test_resource_task_id_is_stable_and_goal_sensitive():
    first = build_ai_chat_resource_task_id(
        user_id="u1", course_id="c1", conversation_id="conv1", run_id="run1",
        goal="复习 AVL 树", resource_type="diagram",
    )
    assert first == build_ai_chat_resource_task_id(
        user_id="u1", course_id="c1", conversation_id="conv1", run_id="run1",
        goal="复习 AVL 树", resource_type="diagram",
    )
    assert first != build_ai_chat_resource_task_id(
        user_id="u1", course_id="c1", conversation_id="conv1", run_id="run1",
        goal="复习 AVL 树", resource_type="reading",
    )
    assert len(first) == 32


def test_resource_ranking_combines_goal_weak_point_and_preference():
    diagram = SimpleNamespace(
        id="r1", title="AVL 树旋转图", description="平衡树", type="diagram",
        chapter="树", knowledge_point="AVL 树", tags=["旋转"],
    )
    unrelated = SimpleNamespace(
        id="r2", title="数组入门", description="数组", type="reading",
        chapter="数组", knowledge_point="数组", tags=[],
    )
    context = {
        "target": "复习 AVL 树旋转",
        "knowledge_point": "AVL 树",
        "preferred_types": {"diagram"},
        "weak_points": {"AVL 树"},
        "recent_types": {"diagram": 2},
    }
    diagram_score, reasons = score_personalized_resource(diagram, context)
    unrelated_score, _ = score_personalized_resource(unrelated, context)

    assert diagram_score > unrelated_score
    assert "匹配当前知识点" in reasons
    assert "符合资源偏好" in reasons

