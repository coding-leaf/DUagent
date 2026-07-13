import os
import sys
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_internal_ai_chat.db",
)

from app.db.session import init_db
from app.main import app


@pytest.fixture(scope="module", autouse=True)
def _init_db():
    import asyncio

    asyncio.run(init_db())


@pytest.mark.asyncio
async def test_internal_learning_progress_requires_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/internal/ai-chat/learning-progress",
            json={"user_id": "u1", "course_id": "c1"},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_internal_learning_progress_returns_service_result():
    with patch("app.api.v1.internal_ai_chat.settings.INTERNAL_AGENT_TOKEN", "secret"):
        with patch(
            "app.api.v1.internal_ai_chat.build_learning_progress_overview",
            new_callable=AsyncMock,
        ) as mock_service:
            mock_service.return_value = {
                "status": "available",
                "course_id": "c1",
                "current_position": None,
                "summary": {"total_nodes": 0},
                "nodes": [],
                "recent_activity": [],
                "source": "backend.learning_progress",
            }
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/internal/ai-chat/learning-progress",
                    headers={"X-Internal-Agent-Token": "secret"},
                    json={"user_id": "u1", "course_id": "c1", "limit_nodes": 20},
                )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "available"
    mock_service.assert_awaited_once()


@pytest.mark.asyncio
async def test_internal_recent_answers_validates_explicit_scope_and_limit():
    with patch("app.api.v1.internal_ai_chat.settings.INTERNAL_AGENT_TOKEN", "secret"):
        with patch(
            "app.api.v1.internal_ai_chat.query_recent_answers",
            new_callable=AsyncMock,
        ) as mock_service:
            mock_service.return_value = {
                "status": "empty",
                "scope": "knowledge_point",
                "query": {"limit": 10},
                "items": [],
                "summary": {"returned_count": 0, "has_more": False},
                "warnings": [],
            }
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/internal/ai-chat/recent-answers",
                    headers={"X-Internal-Agent-Token": "secret"},
                    json={
                        "user_id": "u1",
                        "course_id": "c1",
                        "scope": "knowledge_point",
                        "knowledge_point": "AVL 树旋转",
                        "limit": 10,
                        "only_wrong": True,
                    },
                )

    assert response.status_code == 200
    kwargs = mock_service.await_args.kwargs
    assert kwargs["limit"] == 10
    assert kwargs["scope"] == "knowledge_point"


@pytest.mark.asyncio
async def test_internal_code_problem_returns_stable_validation_reason():
    from app.services.code_problem_service import CodeProblemValidationError

    with patch("app.api.v1.internal_ai_chat.settings.INTERNAL_AGENT_TOKEN", "secret"):
        with patch(
            "app.api.v1.internal_ai_chat.create_validated_personal_problem_from_ai_chat",
            new_callable=AsyncMock,
        ) as mock_service:
            mock_service.side_effect = CodeProblemValidationError(
                "conversation_ownership_check_failed"
            )
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/internal/ai-chat/code-problem-validations",
                    headers={"X-Internal-Agent-Token": "secret"},
                    json={
                        "user_id": "u1",
                        "course_id": "offering-1",
                        "conversation_id": "conv-1",
                        "run_id": "run-1",
                        "draft": {
                            "title": "回显",
                            "statement": "读取并输出输入。",
                            "language": "python",
                            "starter_code": "print(input())",
                            "reference_solution": "print(input())",
                            "test_inputs": [
                                {"stdin": "1\n", "is_public": True},
                                {"stdin": "2\n", "is_public": False},
                            ],
                        },
                    },
                )

    assert response.status_code == 400
    assert response.json()["detail"]["data"]["reason"] == "conversation_ownership_check_failed"


@pytest.mark.asyncio
async def test_internal_code_problem_returns_published_problem_id():
    from types import SimpleNamespace

    created = SimpleNamespace(
        generation=SimpleNamespace(id="generation-1", status="published"),
        problem=SimpleNamespace(id="problem-1", language="python"),
        public_case_count=1,
        hidden_case_count=1,
    )
    with patch("app.api.v1.internal_ai_chat.settings.INTERNAL_AGENT_TOKEN", "secret"):
        with patch(
            "app.api.v1.internal_ai_chat.create_validated_personal_problem_from_ai_chat",
            new_callable=AsyncMock,
            return_value=created,
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/internal/ai-chat/code-problem-validations",
                    headers={"X-Internal-Agent-Token": "secret"},
                    json={
                        "user_id": "u1",
                        "course_id": "offering-1",
                        "conversation_id": "conv-1",
                        "run_id": "run-1",
                        "draft": {
                            "title": "回显",
                            "statement": "读取并输出输入。",
                            "language": "python",
                            "starter_code": "print(input())",
                            "reference_solution": "print(input())",
                            "test_inputs": [
                                {"stdin": "1\n", "is_public": True},
                                {"stdin": "2\n", "is_public": False},
                            ],
                        },
                    },
                )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "generation_id": "generation-1",
        "status": "published",
        "problem_id": "problem-1",
        "language": "python",
        "public_case_count": 1,
        "hidden_case_count": 1,
    }


@pytest.mark.asyncio
async def test_internal_choice_quiz_rejects_unsupported_question_type():
    with patch("app.api.v1.internal_ai_chat.settings.INTERNAL_AGENT_TOKEN", "secret"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/internal/ai-chat/choice-quizzes",
                headers={"X-Internal-Agent-Token": "secret"},
                json={
                    "user_id": "u1",
                    "course_id": "offering-1",
                    "conversation_id": "conv-1",
                    "run_id": "run-1",
                    "title": "指针练习",
                    "chapter": "指针",
                    "knowledge_point": "指针基础",
                    "questions": [
                        {
                            "type": "code",
                            "content": "编写程序",
                            "options": [],
                            "answer": "",
                            "explanation": "",
                            "difficulty": "medium",
                        }
                    ],
                },
            )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_internal_choice_quiz_returns_published_question_ids():
    with patch("app.api.v1.internal_ai_chat.settings.INTERNAL_AGENT_TOKEN", "secret"):
        with patch(
            "app.api.v1.internal_ai_chat.create_personal_choice_quiz_from_ai_chat",
            new_callable=AsyncMock,
            return_value=["question-1", "question-2"],
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/internal/ai-chat/choice-quizzes",
                    headers={"X-Internal-Agent-Token": "secret"},
                    json={
                        "user_id": "u1",
                        "course_id": "offering-1",
                        "conversation_id": "conv-1",
                        "run_id": "run-1",
                        "title": "指针练习",
                        "chapter": "指针",
                        "knowledge_point": "指针基础",
                        "questions": [
                            {
                                "type": "single_choice",
                                "content": "哪个运算符用于取地址？",
                                "options": [
                                    {"key": "A", "text": "&"},
                                    {"key": "B", "text": "*"},
                                ],
                                "answer": "A",
                                "explanation": "& 是取地址运算符。",
                                "difficulty": "easy",
                            },
                            {
                                "type": "multi_choice",
                                "content": "以下哪些是合法指针操作？",
                                "options": [
                                    {"key": "A", "text": "取地址"},
                                    {"key": "B", "text": "解引用"},
                                    {"key": "C", "text": "随意访问越界地址"},
                                ],
                                "answer": ["A", "B"],
                                "explanation": "取地址和解引用是基本操作。",
                                "difficulty": "medium",
                            },
                        ],
                    },
                )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "status": "published",
        "title": "指针练习",
        "question_ids": ["question-1", "question-2"],
        "question_count": 2,
    }
