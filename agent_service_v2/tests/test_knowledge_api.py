from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from agent_service_v2.main import app

client = TestClient(app)


def test_knowledge_ingestion_api_bad_request_path_traversal() -> None:
    # 模拟目录遍历攻击输入
    payload = {
        "catalog_id": "c1",
        "materials": [
            {"storage_uri": "local://../../etc/passwd"}
        ]
    }

    response = client.post("/agent/v2/knowledge/ingestions", json=payload)

    assert response.status_code == 400
    assert "safe relative path" in response.json()["message"]


def test_knowledge_ingestion_api_unsupported_file_type() -> None:
    payload = {
        "catalog_id": "c1",
        "materials": [
            {"storage_uri": "local://python-intro.xlsx"}
        ]
    }

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_file", return_value=True),
    ):
        response = client.post("/agent/v2/knowledge/ingestions", json=payload)

        assert response.status_code == 202
        data = response.json()["data"]
        assert data["chunk_count"] == 0
        assert data["materials"][0]["status"] == "failed"
        assert "unsupported file type" in data["materials"][0]["error"]


def test_knowledge_ingestion_api_normal_flow_success() -> None:
    payload = {
        "catalog_id": "c1",
        "materials": [
            {"storage_uri": "local://python-intro.pdf"}
        ]
    }

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_file", return_value=True),
        patch("agent_service_v2.api.knowledge.ingest_course_material", new_callable=AsyncMock, return_value=15) as mock_ingest,
    ):
        response = client.post("/agent/v2/knowledge/ingestions", json=payload)

        assert response.status_code == 202
        data = response.json()["data"]
        assert data["chunk_count"] == 15
        assert data["materials"][0]["status"] == "ingested"
        assert data["materials"][0]["chunk_count"] == 15
        assert data["materials"][0]["error"] is None
        mock_ingest.assert_called_once()


def test_quiz_generation_api_success() -> None:
    payload = {
        "task_id": "task_123",
        "course_id": "c1",
        "chapter": "chapter 1",
        "knowledge_point": "pointers",
        "question_types": ["single_choice"],
        "count": 2,
    }
    mock_questions = {
        "questions": [
            {
                "title": "What is a pointer?",
                "content": "What is a pointer?",
                "type": "single_choice",
                "options": [{"key": "A", "text": "address"}],
                "answer": "A",
                "explanation": "Holds memory address.",
                "chapter": "chapter 1",
                "knowledge_point": "pointers",
                "difficulty": "medium"
            }
        ]
    }
    with patch("agent_service_v2.agents.leader_team.ResourceWorkerAgent.generate_asset", new_callable=AsyncMock, return_value=mock_questions) as mock_gen:
        response = client.post("/agent/v2/knowledge/quiz/generations", json=payload)
        assert response.status_code == 200
        assert response.json()["code"] == 200
        assert response.json()["data"] == mock_questions
        mock_gen.assert_called_once()


def test_quiz_generation_api_personalized_success() -> None:
    payload = {
        "task_id": "task_123",
        "course_id": "c1",
        "chapter": "chapter 1",
        "knowledge_point": "pointers",
        "question_types": ["single_choice"],
        "count": 1,
        "personalized": True,
        "personalization_context": {
            "evaluation": {"summary": "needs help"},
            "profile": {"guidance_level": "beginner", "blindspots": "addressing"},
            "wrong_points": [{"name": "pointer arithmetic"}]
        }
    }
    mock_questions = {
        "questions": [
            {
                "title": "Pointer arithmetic question",
                "content": "Pointer arithmetic question",
                "type": "single_choice",
                "options": [{"key": "A", "text": "address"}],
                "answer": "A",
                "explanation": "Encouraging explanation.",
                "chapter": "chapter 1",
                "knowledge_point": "pointers",
                "difficulty": "medium"
            }
        ]
    }
    with patch("agent_service_v2.agents.leader_team.ResourceWorkerAgent.generate_asset", new_callable=AsyncMock, return_value=mock_questions) as mock_gen:
        response = client.post("/agent/v2/knowledge/quiz/generations", json=payload)
        assert response.status_code == 200
        assert response.json()["code"] == 200
        assert response.json()["data"] == mock_questions
        mock_gen.assert_called_once_with(
            "quiz",
            "chapter 1",
            "pointers",
            course_id="c1",
            course_title=None,
            count=1,
            question_types=["single_choice"],
            difficulty=None,
            personalized=True,
            personalization_context={
                "evaluation": {"summary": "needs help"},
                "profile": {"guidance_level": "beginner", "blindspots": "addressing"},
                "wrong_points": [{"name": "pointer arithmetic"}]
            }
        )


def test_resource_generation_api_success() -> None:
    payload = {
        "task_id": "res_task_123",
        "course_id": "c1",
        "chapter": "chapter 1",
        "knowledge_point": "pointers",
        "resource_types": ["lesson"],
        "webhook_url": "http://test-webhook.local"
    }
    with patch("agent_service_v2.api.knowledge.run_public_resource_generation", new_callable=AsyncMock) as mock_run:
        response = client.post("/agent/v2/knowledge/resources/generations", json=payload)
        assert response.status_code == 202
        assert response.json()["code"] == 202
        assert response.json()["data"]["task_id"] == "res_task_123"


def test_kg_generation_api_builds_context_from_catalog_chunks() -> None:
    payload = {
        "source_type": "catalog_chunks",
        "catalog_id": "catalog-1",
    }
    mock_graph = {
        "nodes": [{"id": "pointer", "name": "指针", "chapter": "第 5 章"}],
        "edges": [],
    }
    with (
        patch(
            "agent_service_v2.api.knowledge.build_catalog_kg_context",
            new_callable=AsyncMock,
            return_value="指针保存变量地址。",
        ) as mock_context,
        patch(
            "agent_service_v2.api.knowledge.run_leader_team_kg_generation",
            new_callable=AsyncMock,
            return_value=mock_graph,
        ) as mock_generate,
    ):
        response = client.post("/agent/v2/knowledge/knowledge-graphs/generations", json=payload)

    assert response.status_code == 200
    assert response.json()["data"] == mock_graph
    mock_context.assert_called_once()
    assert mock_context.await_args.args == ("catalog-1",)
    mock_generate.assert_called_once()
    assert mock_generate.await_args.args[1] == "指针保存变量地址。"
