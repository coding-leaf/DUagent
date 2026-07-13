from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from agent_service_v2.main import app

client = TestClient(app)


def test_evaluation_generate_rule_baseline() -> None:
    # 构造请求数据
    payload = {
        "user_id": "student123",
        "course_id": "course456",
        "learning_progress": {
            "chapter_progress": [
                {"chapter": "第1章：C语言概述", "completion_rate": 80.0, "time_spent": 120},
                {"chapter": "第2章：数据类型", "completion_rate": 40.0, "time_spent": 60}
            ]
        },
        "quiz_results": [
            {
                "chapter": "第1章：C语言概述",
                "score": 90.0,
                "knowledge_point": "指针基本概念",
                "total_answers": 10,
                "personalized_count": 2,
                "recent_trend": 85.0
            }
        ],
        "resource_usage": {
            "by_type": {"document": 5, "video": 3}
        }
    }

    # 禁用 LLM 增强（模拟 model_provider 返回 None，自动降级为规则版）
    with patch("agent_service_v2.api.evaluation.build_chat_model_from_settings", return_value=None):
        response = client.post("/agent/v2/evaluation/generations", json=payload)

        assert response.status_code == 200
        res_json = response.json()
        assert res_json["code"] == 200
        assert res_json["message"] == "success"

        data = res_json["data"]
        # 验证进度表
        assert data["progress_table"] is not None
        assert len(data["progress_table"]["rows"]) == 2
        assert data["progress_table"]["rows"][0]["chapter"] == "第1章：C语言概述"
        assert data["progress_table"]["rows"][0]["completion_rate"] == 80.0

        # 验证掌握度表
        assert data["mastery_table"] is not None
        assert data["mastery_table"]["rows"][0]["knowledge_point"] == "指针基本概念"
        assert data["mastery_table"]["rows"][0]["average_score"] == 90.0
        assert data["mastery_table"]["rows"][0]["mastery_level"] == "strong"

        # 验证总结文本
        assert "平均完成率 60.0%" in data["summary_text"]
        assert "平均练习正确率 90.0%" in data["summary_text"]
        assert "已进行 2 次个性化强化练习" in data["summary_text"]


def test_evaluation_generate_llm_enrichment_success() -> None:
    payload = {
        "user_id": "student123",
        "course_id": "course456",
        "learning_progress": {
            "chapter_progress": [
                {"chapter": "第1章：C语言概述", "completion_rate": 80.0, "time_spent": 120}
            ]
        },
        "quiz_results": [
            {
                "chapter": "第1章：C语言概述",
                "score": 90.0,
                "knowledge_point": "指针基本概念",
                "total_answers": 10,
                "personalized_count": 2,
                "recent_trend": 85.0
            }
        ],
        "resource_usage": {
            "by_type": {"document": 5}
        }
    }

    # 模拟大模型返回增强的 JSON 对象
    mock_response = MagicMock()
    mock_response.text = '{"summary_text": "LLM 增强版的总结文字：学习范围广；当前掌握强；学习行为好；下一步继续。"}'

    mock_model = AsyncMock()
    mock_model.return_value = mock_response

    with patch("agent_service_v2.api.evaluation.build_chat_model_from_settings", return_value=mock_model):
        response = client.post("/agent/v2/evaluation/generations", json=payload)

        assert response.status_code == 200
        res_json = response.json()
        assert res_json["code"] == 200

        data = res_json["data"]
        # summary_text 应该已被 LLM 增强替换
        assert "LLM 增强版的总结文字" in data["summary_text"]
        # 表格应该完整保留
        assert data["progress_table"] is not None
        assert data["progress_table"]["rows"][0]["chapter"] == "第1章：C语言概述"


def test_quiz_diagnose_api_success() -> None:
    payload = {
        "user_id": "student123",
        "course_id": "course456",
        "quiz_id": "quiz789",
        "questions": [
            {
                "id": "q1",
                "type": "single_choice",
                "content": "What is 1+1?",
                "options": [{"key": "A", "text": "2"}, {"key": "B", "text": "3"}],
                "correct_answer": "A",
                "knowledge_point": "addition"
            }
        ],
        "answers": [
            {"question_id": "q1", "answer": "B"}
        ]
    }

    mock_response = MagicMock()
    mock_response.text = (
        '{"diagnosis": {'
        '"summary": "The student made some mistakes.",'
        '"score_analysis": "Scored 0/100.",'
        '"wrong_points_analysis": "Missed simple addition.",'
        '"suggestions": ["Do more math practice."]'
        '}}'
    )

    mock_model = AsyncMock()
    mock_model.return_value = mock_response

    with patch("agent_service_v2.api.evaluation.build_chat_model_from_settings", return_value=mock_model):
        response = client.post("/agent/v2/evaluation/quiz/diagnose", json=payload)

        assert response.status_code == 200
        res_json = response.json()
        assert res_json["code"] == 200
        assert res_json["message"] == "success"

        data = res_json["data"]
        assert "diagnosis" in data
        assert data["diagnosis"]["summary"] == "The student made some mistakes."
        assert data["diagnosis"]["suggestions"] == ["Do more math practice."]


def test_quiz_diagnose_api_fallback() -> None:
    payload = {
        "user_id": "student123",
        "course_id": "course456",
        "quiz_id": "quiz789",
        "questions": [
            {
                "id": "q1",
                "type": "single_choice",
                "content": "What is 1+1?",
                "options": [{"key": "A", "text": "2"}, {"key": "B", "text": "3"}],
                "correct_answer": "A",
                "knowledge_point": "addition"
            }
        ],
        "answers": [
            {"question_id": "q1", "answer": "B"}
        ]
    }

    with patch("agent_service_v2.api.evaluation.build_chat_model_from_settings", return_value=None):
        response = client.post("/agent/v2/evaluation/quiz/diagnose", json=payload)

        assert response.status_code == 200
        res_json = response.json()
        assert res_json["code"] == 200
        assert res_json["message"] == "success"

        data = res_json["data"]
        assert "diagnosis" in data
        assert "温习答错题目的解析" in data["diagnosis"]["summary"]
        assert "共完成 1 道习题。" in data["diagnosis"]["score_analysis"]
