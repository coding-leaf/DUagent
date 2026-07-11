from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from agent_service_v2.main import app


client = TestClient(app)


def _payload() -> dict:
    return {
        "user_id": "student-1",
        "course_id": "course-1",
        "facts_version": "facts-v7",
        "learning_progress": {
            "chapter_progress": [
                {"chapter": "指针", "completion_rate": 50.0, "time_spent": 12}
            ]
        },
        "quiz_results": [
            {
                "chapter": "指针",
                "knowledge_point": "指针传参",
                "score": 37.5,
                "total_answers": 8,
                "personalized_count": 0,
                "recent_trend": 37.5,
            }
        ],
        "resource_usage": {"by_type": {"lesson": 2}},
    }


def test_evaluation_returns_structured_insight_without_changing_rule_tables():
    model_response = MagicMock()
    model_response.text = """{
      "summary_text": "指针传参仍需优先巩固。",
      "insight": {
        "strengths": [],
        "weak_points": [{
          "knowledge_point": "指针传参",
          "evidence": "最近 8 题正确率 37.5%",
          "priority": "high"
        }],
        "learning_preferences": ["lesson"],
        "next_actions": ["先复习值传递与地址传递"]
      }
    }"""
    model = AsyncMock(return_value=model_response)

    with patch(
        "agent_service_v2.api.evaluation.build_chat_model_from_settings",
        return_value=model,
    ):
        response = client.post("/agent/v2/evaluation/generations", json=_payload())

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["mastery_table"]["rows"][0]["average_score"] == 37.5
    assert data["insight"] == {
        "strengths": [],
        "weak_points": [
            {
                "knowledge_point": "指针传参",
                "evidence": "最近 8 题正确率 37.5%",
                "priority": "high",
            }
        ],
        "learning_preferences": ["lesson"],
        "next_actions": ["先复习值传递与地址传递"],
        "facts_version": "facts-v7",
    }


def test_rule_fallback_keeps_facts_version_in_empty_insight():
    with patch(
        "agent_service_v2.api.evaluation.build_chat_model_from_settings",
        return_value=None,
    ):
        response = client.post("/agent/v2/evaluation/generations", json=_payload())

    assert response.status_code == 200
    assert response.json()["data"]["insight"] == {
        "strengths": [],
        "weak_points": [],
        "learning_preferences": [],
        "next_actions": [],
        "facts_version": "facts-v7",
    }
