import os
import sys
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:////tmp/admin_catalog_resource_generation.db",
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import Base
from app.db.session import async_session_factory, engine
from app.main import app
from app.models.catalog import CourseCatalog, CourseCatalogMaterial, CourseOffering
from app.models.course import Course
from app.models.others import AsyncTask, CourseKnowledgeGraph, Resource
from app.models.quiz import QuizQuestion
from app.models.user import User


@pytest_asyncio.fixture(autouse=True)
async def _dispose_db_engine_after_test():
    yield
    await engine.dispose()


async def _reset_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


def _auth_headers(user_id: str, role: str) -> dict:
    from app.core.security import create_token

    token = create_token(user_id, role)
    return {"Authorization": f"Bearer {token}"}


async def _seed_user(user_id: str, role: str) -> None:
    async with async_session_factory() as db:
        db.add(
            User(
                id=user_id,
                email=f"{user_id}@example.com",
                username=user_id,
                password_hash="x",
                role=role,
            )
        )
        await db.commit()


async def _seed_ready_catalog(
    *,
    catalog_id: str = "catalog-admin-gen",
    status: str = "ready",
    knowledge_status: str = "ready",
    chunk_count: int = 5,
) -> str:
    async with async_session_factory() as db:
        db.add(
            CourseCatalog(
                id=catalog_id,
                title="Admin Generation Catalog",
                status=status,
                knowledge_status=knowledge_status,
                material_count=1,
                chunk_count=chunk_count,
            )
        )
        db.add(
            CourseCatalogMaterial(
                id="material-admin-gen",
                catalog_id=catalog_id,
                filename="lesson.md",
                source_type="file",
                storage_uri="course_catalogs/catalog-admin-gen/material-admin-gen/lesson.md",
                status="ingested",
                chunk_count=chunk_count,
            )
        )
        await db.commit()
    return catalog_id


async def _seed_bound_class(
    *,
    catalog_id: str,
    class_id: str,
    teacher_id: str = "teacher-admin-gen",
) -> str:
    async with async_session_factory() as db:
        db.add(
            Course(
                id=class_id,
                name=f"Class {class_id}",
                course_code=f"C{class_id[-6:]}",
                teacher_id=teacher_id,
            )
        )
        db.add(
            CourseOffering(
                id=class_id,
                name=f"Class {class_id}",
                catalog_id=catalog_id,
                teacher_id=teacher_id,
                class_code=f"C{class_id[-6:]}",
            )
        )
        await db.commit()
    return class_id


async def _seed_active_kg(
    course_id: str,
    nodes: list[dict],
    edges: list[dict] | None = None,
) -> str:
    async with async_session_factory() as db:
        graph = CourseKnowledgeGraph(
            id=f"kg-{course_id}",
            course_id=course_id,
            version=1,
            is_active=True,
            source_type="route_a_body_grounded",
            generation_strategy="route_a_prune_usable_060",
            nodes=nodes,
            edges=edges or [],
            metrics={
                "support_band_counts": {
                    "strong": 1,
                    "good": 1,
                    "weak_but_usable": 0,
                    "unsupported": 0,
                }
            },
        )
        db.add(graph)
        await db.commit()
        return graph.id


async def _seed_catalog_host_with_active_kg(
    *,
    catalog_id: str,
    host_course_id: str,
    nodes: list[dict] | None = None,
) -> str:
    async with async_session_factory() as db:
        db.add(
            Course(
                id=host_course_id,
                name=f"Host {host_course_id}",
                course_code=f"H{host_course_id[-6:]}",
                teacher_id="teacher-admin-gen",
            )
        )
        catalog = await db.get(CourseCatalog, catalog_id)
        catalog.kg_host_course_id = host_course_id
        await db.commit()
    return await _seed_active_kg(
        host_course_id,
        nodes
        or [
            {
                "id": "node-quiz-1",
                "name": "输入输出函数",
                "chapter": "第7章 输入输出",
                "support_band": "strong",
                "body_top1_score": 0.88,
            }
        ],
    )


async def _count_tasks(catalog_id: str) -> int:
    async with async_session_factory() as db:
        result = await db.execute(
            select(AsyncTask).where(AsyncTask.task_type == "resource_generation")
        )
        tasks = result.scalars().all()
        return sum(
            1
            for task in tasks
            if isinstance(task.result, dict) and task.result.get("catalog_id") == catalog_id
        )


@pytest.mark.asyncio
async def test_admin_catalog_quiz_generation_does_not_delete_existing_baseline_before_background_success():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    class_id = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")
    await _seed_catalog_host_with_active_kg(
        catalog_id=catalog_id,
        host_course_id="host-admin-gen-a",
    )
    async with async_session_factory() as db:
        db.add(
            QuizQuestion(
                id="old-baseline-question",
                course_id=class_id,
                chapter="第7章 输入输出",
                knowledge_point="输入输出函数",
                type="single_choice",
                source="baseline",
                personalized=False,
                difficulty="medium",
                content="printf 的格式字符串用于控制输出格式。",
                options=[{"key": "A", "text": "正确"}],
                correct_answer="A",
                explanation="旧题应在新题成功前保持可见。",
                is_deleted=False,
            )
        )
        await db.commit()

    with patch("app.services.catalog_quiz_generation_service.run_quiz_generation_background", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/quiz/generations",
                headers=_auth_headers("admin-admin-gen", "admin"),
            )

    assert response.status_code == 202, response.text
    async with async_session_factory() as db:
        question = await db.get(QuizQuestion, "old-baseline-question")
        assert question is not None
        assert question.is_deleted is False


@pytest.mark.asyncio
async def test_quiz_generation_background_marks_parent_partial_when_one_child_raises():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    parent_id = "quiz-parent-partial"
    completed_child_id = "quiz-child-completed"
    failed_child_id = "quiz-child-raised"
    async with async_session_factory() as db:
        db.add(
            AsyncTask(
                id=parent_id,
                task_type="quiz_generation",
                status="processing",
                progress=10,
                user_id="admin-admin-gen",
                course_id=None,
                result={
                    "catalog_id": "catalog-admin-gen",
                    "total_node_count": 2,
                    "completed_node_count": 0,
                    "failed_node_count": 0,
                    "total_question_count": 0,
                },
            )
        )
        db.add_all(
            [
                AsyncTask(
                    id=completed_child_id,
                    task_type="quiz_generation",
                    status="processing",
                    progress=10,
                    user_id="admin-admin-gen",
                    result={"parent_task_id": parent_id},
                ),
                AsyncTask(
                    id=failed_child_id,
                    task_type="quiz_generation",
                    status="processing",
                    progress=10,
                    user_id="admin-admin-gen",
                    result={"parent_task_id": parent_id},
                ),
            ]
        )
        await db.commit()

    async def _child_result(db, child_id, fanout_course_ids):
        if child_id == completed_child_id:
            return {
                "status": "completed",
                "question_count": 2,
                "inserted_question_ids": ["q1", "q2"],
            }
        raise RuntimeError("child failed")

    with patch(
        "app.services.catalog_quiz_generation_service.generate_quiz_for_child",
        new_callable=AsyncMock,
    ) as mock_child:
        mock_child.side_effect = _child_result
        from app.services.catalog_quiz_generation_service import run_quiz_generation_background

        await run_quiz_generation_background(
            parent_id,
            [completed_child_id, failed_child_id],
            ["class-admin-gen-a"],
        )

    async with async_session_factory() as db:
        parent = await db.get(AsyncTask, parent_id)
        assert parent.status == "partial"
        assert parent.progress == 100
        assert parent.result["completed_node_count"] == 1
        assert parent.result["failed_node_count"] == 1
        assert parent.result["total_question_count"] == 2
        assert parent.result["inserted_question_count"] == 2


@pytest.mark.asyncio
async def test_admin_catalog_quiz_child_uses_catalog_id_for_agent_rag_and_class_id_for_persistence():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    class_id = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")
    child_id = "quiz-child-agent-scope"
    async with async_session_factory() as db:
        db.add(
            AsyncTask(
                id=child_id,
                task_type="quiz_generation",
                status="processing",
                progress=10,
                user_id="admin-admin-gen",
                course_id=class_id,
                result={
                    "catalog_id": catalog_id,
                    "agent_course_id": catalog_id,
                    "node_name": "输入输出函数",
                    "chapter": "第7章 输入输出",
                    "course_ids": [class_id],
                },
            )
        )
        await db.commit()

    with patch("app.services.catalog_quiz_generation_service.quiz_agent_client.post_json", new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = {
            "questions": [
                {
                    "type": "single_choice",
                    "content": "关于 printf 的格式控制字符串，下列说法哪项正确？",
                    "options": [{"key": "A", "text": "%d 用于十进制整数输出"}],
                    "answer": "A",
                    "explanation": "printf 按格式控制字符串解释后续参数。",
                }
            ]
        }
        from app.services.catalog_quiz_generation_service import generate_quiz_for_child

        async with async_session_factory() as db:
            result = await generate_quiz_for_child(db, child_id, [class_id])
            await db.commit()

    assert result["status"] == "completed"
    assert mock_agent.await_args.args[0] == "/agent/v2/knowledge/quiz/generations"
    payload = mock_agent.await_args.args[1]
    assert payload["course_id"] == catalog_id
    assert payload["course_title"] == "Admin Generation Catalog"
    async with async_session_factory() as db:
        questions = (
            await db.execute(select(QuizQuestion).where(QuizQuestion.course_id == class_id))
        ).scalars().all()
        assert len(questions) == 1
        assert questions[0].content == "关于 printf 的格式控制字符串，下列说法哪项正确？"


@pytest.mark.asyncio
async def test_admin_catalog_quiz_child_splits_large_mixed_request_when_batch_returns_skeleton():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    class_id = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")
    child_id = "quiz-child-split-fallback"
    async with async_session_factory() as db:
        db.add(
            AsyncTask(
                id=child_id,
                task_type="quiz_generation",
                status="processing",
                progress=10,
                user_id="admin-admin-gen",
                course_id=class_id,
                result={
                    "catalog_id": catalog_id,
                    "agent_course_id": catalog_id,
                    "node_name": "输入输出函数",
                    "chapter": "第7章 输入输出",
                    "course_ids": [class_id],
                },
            )
        )
        await db.commit()

    skeleton_batch = {
        "questions": [
            {
                "type": "single_choice",
                "content": "第 1 题：请围绕输入输出函数完成一道单选题。",
                "options": [
                    {"key": "A", "text": "正确表述"},
                    {"key": "B", "text": "易混淆表述"},
                    {"key": "C", "text": "相关补充表述"},
                    {"key": "D", "text": "无关表述"},
                ],
                "answer": "A",
                "explanation": "本题用于检查对输入输出函数的基础理解。",
            }
        ]
    }
    single_batch = {
        "questions": [
            {
                "type": "single_choice",
                "content": f"关于 printf 格式控制的单选题 {index}，下列说法哪项正确？",
                "options": [
                    {"key": "A", "text": "%d 可用于输出十进制整数"},
                    {"key": "B", "text": "%d 用于输出字符串"},
                    {"key": "C", "text": "printf 不需要格式控制"},
                    {"key": "D", "text": "格式控制符只能写在参数末尾"},
                ],
                "answer": "A",
                "explanation": "printf 会按照格式控制字符串解释后续参数。",
            }
            for index in range(1, 4)
        ]
    }
    multi_batch = {
        "questions": [
            {
                "type": "multi_choice",
                "content": f"关于 scanf 与 printf 的多选题 {index}，哪些说法正确？",
                "options": [
                    {"key": "A", "text": "scanf 读取输入时需要匹配格式控制符"},
                    {"key": "B", "text": "printf 输出时完全不使用格式控制符"},
                    {"key": "C", "text": "printf 的格式控制字符串会影响输出形式"},
                    {"key": "D", "text": "scanf 的地址参数总是可以省略"},
                ],
                "answer": ["A", "C"],
                "explanation": "scanf 和 printf 都依赖格式控制字符串处理输入输出。",
            }
            for index in range(1, 5)
        ]
    }

    with patch("app.services.catalog_quiz_generation_service.quiz_agent_client.post_json", new_callable=AsyncMock) as mock_agent:
        mock_agent.side_effect = [skeleton_batch, single_batch, multi_batch]
        from app.services.catalog_quiz_generation_service import generate_quiz_for_child

        async with async_session_factory() as db:
            result = await generate_quiz_for_child(db, child_id, [class_id])
            await db.commit()

    assert result["status"] == "completed"
    assert result["question_count"] == 7
    assert mock_agent.await_count == 3
    first_payload = mock_agent.await_args_list[0].args[1]
    second_payload = mock_agent.await_args_list[1].args[1]
    third_payload = mock_agent.await_args_list[2].args[1]
    assert [
        first_payload["course_title"],
        second_payload["course_title"],
        third_payload["course_title"],
    ] == ["Admin Generation Catalog"] * 3
    assert first_payload["count"] == 7
    assert second_payload["question_types"] == ["single_choice"]
    assert second_payload["count"] == 3
    assert third_payload["question_types"] == ["multi_choice"]
    assert third_payload["count"] == 4
    async with async_session_factory() as db:
        questions = (
            await db.execute(
                select(QuizQuestion)
                .where(QuizQuestion.course_id == class_id, QuizQuestion.is_deleted == False)
                .order_by(QuizQuestion.type.asc(), QuizQuestion.content.asc())
            )
        ).scalars().all()
    assert len(questions) == 7
    assert [q.type for q in questions].count("single_choice") == 3
    assert [q.type for q in questions].count("multi_choice") == 4
    multi_question = next(q for q in questions if q.type == "multi_choice")
    assert multi_question.correct_answer == "A,C"


@pytest.mark.asyncio
async def test_admin_catalog_quiz_child_rejects_skeleton_fallback_questions():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    class_id = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")
    child_id = "quiz-child-skeleton"
    async with async_session_factory() as db:
        db.add(
            AsyncTask(
                id=child_id,
                task_type="quiz_generation",
                status="processing",
                progress=10,
                user_id="admin-admin-gen",
                course_id=class_id,
                result={
                    "catalog_id": catalog_id,
                    "agent_course_id": catalog_id,
                    "node_name": "输入输出函数",
                    "chapter": "第7章 输入输出",
                    "course_ids": [class_id],
                },
            )
        )
        await db.commit()

    with patch("app.services.catalog_quiz_generation_service.quiz_agent_client.post_json", new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = {
            "questions": [
                {
                    "type": "multi_choice",
                    "content": "第 7 题：请围绕输入输出函数完成一道多选题。",
                    "options": [
                        {"key": "A", "text": "正确表述"},
                        {"key": "B", "text": "易混淆表述"},
                        {"key": "C", "text": "相关补充表述"},
                        {"key": "D", "text": "无关表述"},
                    ],
                    "answer": ["A", "C"],
                    "explanation": "本题用于检查对输入输出函数的基础理解。",
                }
            ]
        }
        from app.services.catalog_quiz_generation_service import generate_quiz_for_child

        async with async_session_factory() as db:
            result = await generate_quiz_for_child(db, child_id, [class_id])
            await db.commit()

    assert result["status"] == "failed"
    assert result["error"] == "skeleton_rejected"


@pytest.mark.asyncio
async def test_admin_catalog_quiz_child_rejects_skeleton_fallback_string_options():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    class_id = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")
    child_id = "quiz-child-skeleton-str"
    async with async_session_factory() as db:
        db.add(
            AsyncTask(
                id=child_id,
                task_type="quiz_generation",
                status="processing",
                progress=10,
                user_id="admin-admin-gen",
                course_id=class_id,
                result={
                    "catalog_id": catalog_id,
                    "agent_course_id": catalog_id,
                    "node_name": "输入输出函数",
                    "chapter": "第7章 输入输出",
                    "course_ids": [class_id],
                },
            )
        )
        await db.commit()

    with patch("app.services.catalog_quiz_generation_service.quiz_agent_client.post_json", new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = {
            "questions": [
                {
                    "type": "multi_choice",
                    "content": "第 7 题：请围绕输入输出函数完成一道多选题。",
                    "options": ["正确表述", "易混淆表述", "相关补充表述", "无关表述"],
                    "answer": ["A", "C"],
                    "explanation": "本题用于检查对输入输出函数的基础理解。",
                }
            ]
        }
        from app.services.catalog_quiz_generation_service import generate_quiz_for_child

        async with async_session_factory() as db:
            result = await generate_quiz_for_child(db, child_id, [class_id])
            await db.commit()

            questions = (
                await db.execute(
                    select(QuizQuestion).where(
                        QuizQuestion.course_id == class_id,
                        QuizQuestion.is_deleted == False,
                    )
                )
            ).scalars().all()

    assert result["status"] == "failed"
    assert result["error"] == "skeleton_rejected"
    assert questions == []
    async with async_session_factory() as db:
        child = await db.get(AsyncTask, child_id)
        assert child.status == "failed"
        assert child.error_code == "skeleton_rejected"
        count = len((await db.execute(select(QuizQuestion))).scalars().all())
        assert count == 0


@pytest.mark.asyncio
async def test_admin_catalog_generation_creates_task_and_sends_catalog_id_to_agent():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    class_a = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")
    class_b = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-b")

    with patch("app.services.catalog_resource_generation_service.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = {"task_id": "ignored"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/resources/generations",
                headers=_auth_headers("admin-admin-gen", "admin"),
                json={
                    "chapter": "树",
                    "knowledge_point": "二叉树",
                    "resource_types": ["lesson", "diagram"],
                },
            )

    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["catalog_id"] == catalog_id
    assert data["status"] == "processing"
    assert data["task_id"]

    payload = mock_agent.await_args.args[1]
    assert payload["course_id"] == catalog_id
    assert payload["course_title"] == "Admin Generation Catalog"
    assert payload["chapter"] == "树"
    assert payload["knowledge_point"] == "二叉树"
    assert payload["resource_types"] == ["lesson", "diagram"]

    async with async_session_factory() as db:
        task = await db.get(AsyncTask, data["task_id"])
        assert task is not None
        assert task.task_type == "resource_generation"
        assert task.user_id == "admin-admin-gen"
        assert task.course_id is None
        assert task.result["catalog_id"] == catalog_id
        assert task.result["fanout_course_ids"] == [class_a, class_b]
        assert task.result["chapter"] == "树"
        assert task.result["knowledge_point"] == "二叉树"


@pytest.mark.asyncio
async def test_admin_catalog_generation_without_metadata_creates_parent_and_child_tasks_from_active_kg():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    class_a = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")
    await _seed_catalog_host_with_active_kg(
        catalog_id=catalog_id,
        host_course_id="host-admin-gen-a",
        nodes=[
            {
                "id": "node-1",
                "name": "变量",
                "chapter": "第一章",
                "support_band": "strong",
                "body_top1_score": 0.82,
            },
            {
                "id": "node-2",
                "name": "指针",
                "chapter": "第二章",
                "support_band": "good",
                "body_top1_score": 0.67,
            },
        ],
    )

    with patch("app.services.catalog_resource_generation_service.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = {"task_id": "accepted"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/resources/generations",
                headers=_auth_headers("admin-admin-gen", "admin"),
                json={"resource_types": ["lesson"]},
            )

    assert response.status_code == 202, response.text
    parent_task_id = response.json()["data"]["task_id"]
    assert mock_agent.await_count == 2
    payloads = [call.args[1] for call in mock_agent.await_args_list]
    assert [payload["course_id"] for payload in payloads] == [catalog_id, catalog_id]
    assert [payload["course_title"] for payload in payloads] == [
        "Admin Generation Catalog",
        "Admin Generation Catalog",
    ]
    assert [(payload["chapter"], payload["knowledge_point"]) for payload in payloads] == [
        ("第一章", "变量"),
        ("第二章", "指针"),
    ]

    async with async_session_factory() as db:
        parent = await db.get(AsyncTask, parent_task_id)
        assert parent is not None
        assert parent.status == "processing"
        assert parent.result["mode"] == "kg_node_targets"
        assert parent.result["fanout_course_ids"] == [class_a]
        assert parent.result["target_node_count"] == 2
        assert parent.result["total_child_count"] == 2
        assert parent.result["selection_degraded"] is False

        result = await db.execute(select(AsyncTask).where(AsyncTask.id != parent_task_id))
        children = sorted(
            result.scalars().all(),
            key=lambda task: task.result["target_node"]["node_id"],
        )
        assert len(children) == 2
        assert [child.result["parent_task_id"] for child in children] == [
            parent_task_id,
            parent_task_id,
        ]
        assert [child.result["target_node"]["node_name"] for child in children] == [
            "变量",
            "指针",
        ]
        assert [child.result["fanout_course_ids"] for child in children] == [
            [class_a],
            [class_a],
        ]


@pytest.mark.asyncio
async def test_admin_catalog_generation_without_metadata_fails_parent_when_no_active_kg():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")

    with patch("app.services.catalog_resource_generation_service.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/resources/generations",
                headers=_auth_headers("admin-admin-gen", "admin"),
                json={"resource_types": ["lesson"]},
            )

    assert response.status_code == 202, response.text
    mock_agent.assert_not_awaited()
    async with async_session_factory() as db:
        task = await db.get(AsyncTask, response.json()["data"]["task_id"])
        assert task.status == "failed"
        assert task.error_code == "kg_not_ready"
        assert task.error_message == "课程知识图谱未就绪"


@pytest.mark.asyncio
async def test_admin_catalog_generation_without_metadata_fails_parent_when_no_usable_targets():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")
    await _seed_catalog_host_with_active_kg(
        catalog_id=catalog_id,
        host_course_id="host-admin-gen-a",
        nodes=[
            {
                "id": "bad",
                "name": "目录",
                "chapter": "附录",
                "support_band": "unsupported",
                "body_top1_score": 0.40,
            }
        ],
    )

    with patch("app.services.catalog_resource_generation_service.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/resources/generations",
                headers=_auth_headers("admin-admin-gen", "admin"),
                json={"resource_types": ["lesson"]},
            )

    assert response.status_code == 202, response.text
    mock_agent.assert_not_awaited()
    async with async_session_factory() as db:
        task = await db.get(AsyncTask, response.json()["data"]["task_id"])
        assert task.status == "failed"
        assert task.error_code == "kg_target_empty"
        assert task.error_message == "没有可用于资源挂载的 KG 节点"


@pytest.mark.asyncio
async def test_admin_catalog_generation_rejects_no_bound_classes_without_task():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    catalog_id = await _seed_ready_catalog()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/admin/course-catalogs/{catalog_id}/resources/generations",
            headers=_auth_headers("admin-admin-gen", "admin"),
            json={"resource_types": ["lesson"]},
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == 40915
    assert await _count_tasks(catalog_id) == 0


@pytest.mark.asyncio
async def test_admin_catalog_generation_rejects_empty_resource_types_without_task():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/admin/course-catalogs/{catalog_id}/resources/generations",
            headers=_auth_headers("admin-admin-gen", "admin"),
            json={},
        )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == 42210
    assert await _count_tasks(catalog_id) == 0


@pytest.mark.asyncio
async def test_admin_catalog_generation_rejects_invalid_resource_types_without_task():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/admin/course-catalogs/{catalog_id}/resources/generations",
            headers=_auth_headers("admin-admin-gen", "admin"),
            json={"resource_types": ["lesson", "bad"]},
        )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": 42210,
        "message": "资源类型不合法",
        "data": {"invalid_types": ["bad"]},
    }
    assert await _count_tasks(catalog_id) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "knowledge_status", "chunk_count", "expected_code"),
    [
        ("draft", "draft", 0, 40913),
        ("ready", "dirty", 5, 40913),
        ("ready", "failed", 5, 40913),
        ("ready", "ready", 0, 40914),
    ],
)
async def test_admin_catalog_generation_rejects_not_ready_catalogs(
    status,
    knowledge_status,
    chunk_count,
    expected_code,
):
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog(
        status=status,
        knowledge_status=knowledge_status,
        chunk_count=chunk_count,
    )
    await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/admin/course-catalogs/{catalog_id}/resources/generations",
            headers=_auth_headers("admin-admin-gen", "admin"),
            json={"resource_types": ["lesson"]},
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == expected_code


@pytest.mark.asyncio
async def test_non_admin_cannot_generate_catalog_resources():
    await _reset_db()
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/admin/course-catalogs/{catalog_id}/resources/generations",
            headers=_auth_headers("teacher-admin-gen", "teacher"),
            json={"resource_types": ["lesson"]},
        )

    assert response.status_code == 403


def _webhook_headers() -> dict:
    from app.core.config import settings

    return {"X-Webhook-Secret": settings.WEBHOOK_SECRET}


@pytest.mark.asyncio
async def test_webhook_writes_shared_catalog_resource_visible_to_all_bound_classes():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    class_a = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")
    class_b = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-b")

    async with async_session_factory() as db:
        task = AsyncTask(
            id="task-admin-gen",
            task_type="resource_generation",
            status="processing",
            user_id="admin-admin-gen",
            course_id=None,
            result={
                "catalog_id": catalog_id,
                "fanout_course_ids": [class_a, class_b],
            },
        )
        db.add(task)
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/webhooks/agent",
            headers=_webhook_headers(),
            json={
                "task_id": "task-admin-gen",
                "task_type": "resource_generation",
                "status": "completed",
                "result": {
                    "resources": [
                        {
                            "title": "Catalog Doc",
                            "type": "lesson",
                            "description": "doc",
                            "content": "doc content",
                            "chapter": "树",
                            "knowledge_point": "二叉树",
                            "tags": ["catalog"],
                        }
                    ]
                },
            },
        )

    assert response.status_code == 200, response.text
    async with async_session_factory() as db:
        result = await db.execute(select(Resource).where(Resource.title == "Catalog Doc"))
        resources = result.scalars().all()
        assert len(resources) == 1
        assert resources[0].course_id == class_a
        assert resources[0].catalog_id == catalog_id
        task = await db.get(AsyncTask, "task-admin-gen")
        assert task.result["catalog_id"] == catalog_id
        assert task.result["fanout_course_ids"] == [class_a, class_b]
        assert task.result["resource_count"] == 1
        assert task.result["agent_result"]["resources"][0]["title"] == "Catalog Doc"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        class_b_resources = await client.get(
            f"/api/v1/resources?course_id={class_b}",
            headers=_auth_headers("teacher-admin-gen", "teacher"),
        )

    assert class_b_resources.status_code == 200, class_b_resources.text
    payload = class_b_resources.json()["data"]
    assert payload["total"] == 1
    assert [item["id"] for item in payload["resources"]] == [resources[0].id]


@pytest.mark.asyncio
async def test_webhook_kg_node_child_overrides_agent_metadata_and_updates_parent_completed():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    class_a = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")

    async with async_session_factory() as db:
        parent = AsyncTask(
            id="parent-kg-node",
            task_type="resource_generation",
            status="processing",
            user_id="admin-admin-gen",
            course_id=None,
            result={
                "catalog_id": catalog_id,
                "fanout_course_ids": [class_a],
                "mode": "kg_node_targets",
                "total_child_count": 1,
                "target_node_count": 1,
                "completed_child_count": 0,
                "failed_child_count": 0,
                "successful_node_count": 0,
                "failed_node_count": 0,
            },
        )
        child = AsyncTask(
            id="child-kg-node",
            task_type="resource_generation",
            status="processing",
            user_id="admin-admin-gen",
            course_id=None,
            result={
                "catalog_id": catalog_id,
                "parent_task_id": parent.id,
                "fanout_course_ids": [class_a],
                "mode": "kg_node_target",
                "target_node": {
                    "node_id": "node-pointer",
                    "node_name": "指针",
                    "chapter": "第二章",
                    "support_band": "good",
                    "body_top1_score": 0.67,
                },
                "resource_types": ["lesson"],
            },
        )
        db.add_all([parent, child])
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/webhooks/agent",
            headers=_webhook_headers(),
            json={
                "task_id": "child-kg-node",
                "task_type": "resource_generation",
                "status": "completed",
                "result": {
                    "resources": [
                        {
                            "title": "Pointer Doc",
                            "type": "lesson",
                            "description": "doc",
                            "content": "doc content",
                            "chapter": "课程整体",
                            "knowledge_point": "综合知识点",
                            "tags": ["agent"],
                        }
                    ]
                },
            },
        )

    assert response.status_code == 200, response.text
    async with async_session_factory() as db:
        result = await db.execute(select(Resource).where(Resource.title == "Pointer Doc"))
        resource = result.scalar_one()
        assert resource.course_id == class_a
        assert resource.catalog_id == catalog_id
        assert resource.chapter == "第二章"
        assert resource.knowledge_point == "指针"
        assert "kg_node:node-pointer" in resource.tags
        assert "support_band:good" in resource.tags

        parent = await db.get(AsyncTask, "parent-kg-node")
        assert parent.status == "completed"
        assert parent.progress == 100
        assert parent.result["completed_child_count"] == 1
        assert parent.result["failed_child_count"] == 0
        assert parent.result["successful_node_count"] == 1
        assert parent.result["failed_node_count"] == 0
        assert parent.result.get("degraded") is False


@pytest.mark.asyncio
async def test_webhook_parent_aggregation_marks_degraded_when_one_child_failed():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    async with async_session_factory() as db:
        parent = AsyncTask(
            id="parent-degraded",
            task_type="resource_generation",
            status="processing",
            user_id="admin-admin-gen",
            result={"mode": "kg_node_targets", "total_child_count": 2},
        )
        completed_child = AsyncTask(
            id="child-completed",
            task_type="resource_generation",
            status="completed",
            user_id="admin-admin-gen",
            result={"mode": "kg_node_target", "parent_task_id": "parent-degraded"},
        )
        failed_child = AsyncTask(
            id="child-failed",
            task_type="resource_generation",
            status="processing",
            user_id="admin-admin-gen",
            result={"mode": "kg_node_target", "parent_task_id": "parent-degraded"},
        )
        db.add_all([parent, completed_child, failed_child])
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/webhooks/agent",
            headers=_webhook_headers(),
            json={
                "task_id": "child-failed",
                "task_type": "resource_generation",
                "status": "failed",
                "error_code": "agent_error",
                "error_message": "model failed",
            },
        )

    assert response.status_code == 200, response.text
    async with async_session_factory() as db:
        parent = await db.get(AsyncTask, "parent-degraded")
        assert parent.status == "completed"
        assert parent.result["degraded"] is True
        assert parent.result["completed_child_count"] == 1
        assert parent.result["failed_child_count"] == 1
        assert parent.result["successful_node_count"] == 1
        assert parent.result["failed_node_count"] == 1


@pytest.mark.asyncio
async def test_webhook_parent_aggregation_marks_failed_when_all_children_failed():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    async with async_session_factory() as db:
        parent = AsyncTask(
            id="parent-failed",
            task_type="resource_generation",
            status="processing",
            user_id="admin-admin-gen",
            result={"mode": "kg_node_targets", "total_child_count": 1},
        )
        child = AsyncTask(
            id="child-failed-only",
            task_type="resource_generation",
            status="processing",
            user_id="admin-admin-gen",
            result={"mode": "kg_node_target", "parent_task_id": "parent-failed"},
        )
        db.add_all([parent, child])
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/webhooks/agent",
            headers=_webhook_headers(),
            json={
                "task_id": "child-failed-only",
                "task_type": "resource_generation",
                "status": "failed",
                "error_code": "agent_error",
                "error_message": "model failed",
            },
        )

    assert response.status_code == 200, response.text
    async with async_session_factory() as db:
        parent = await db.get(AsyncTask, "parent-failed")
        assert parent.status == "failed"
        assert parent.progress == 100
        assert parent.error_code == "all_children_failed"
        assert parent.result["completed_child_count"] == 0
        assert parent.result["failed_child_count"] == 1


@pytest.mark.asyncio
async def test_webhook_rejects_empty_generated_resources_without_marking_success():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    catalog_id = await _seed_ready_catalog()
    async with async_session_factory() as db:
        task = AsyncTask(
            id="task-admin-empty",
            task_type="resource_generation",
            status="processing",
            user_id="admin-admin-gen",
            course_id=None,
            result={"catalog_id": catalog_id, "fanout_course_ids": ["class-admin-gen-a"]},
        )
        db.add(task)
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/webhooks/agent",
            headers=_webhook_headers(),
            json={
                "task_id": "task-admin-empty",
                "task_type": "resource_generation",
                "status": "completed",
                "result": {"resources": []},
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "result.resources 不能为空"
    async with async_session_factory() as db:
        task = await db.get(AsyncTask, "task-admin-empty")
        assert task.status == "processing"


@pytest.mark.asyncio
async def test_admin_can_poll_catalog_resource_generation_task():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    async with async_session_factory() as db:
        db.add(
            AsyncTask(
                id="task-admin-gen",
                task_type="resource_generation",
                status="processing",
                user_id="admin-admin-gen",
                course_id=None,
                result={"catalog_id": "catalog-admin-gen", "fanout_course_ids": []},
            )
        )
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/tasks/task-admin-gen",
            headers=_auth_headers("admin-admin-gen", "admin"),
        )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["task_type"] == "resource_generation"


@pytest.mark.asyncio
async def test_teacher_cannot_poll_admin_catalog_resource_generation_task():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    async with async_session_factory() as db:
        db.add(
            AsyncTask(
                id="task-admin-gen",
                task_type="resource_generation",
                status="processing",
                user_id="admin-admin-gen",
                course_id=None,
                result={"catalog_id": "catalog-admin-gen", "fanout_course_ids": []},
            )
        )
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/tasks/task-admin-gen",
            headers=_auth_headers("teacher-admin-gen", "teacher"),
        )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == 40400


@pytest.mark.asyncio
async def test_teacher_can_poll_own_legacy_resource_generation_task():
    await _reset_db()
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")
    async with async_session_factory() as db:
        db.add(
            AsyncTask(
                id="task-teacher-gen",
                task_type="resource_generation",
                status="processing",
                user_id="teacher-admin-gen",
                course_id="class-admin-gen-a",
                result={"catalog_id": "catalog-admin-gen"},
            )
        )
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/tasks/task-teacher-gen",
            headers=_auth_headers("teacher-admin-gen", "teacher"),
        )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["task_id"] == "task-teacher-gen"


@pytest.mark.asyncio
async def test_admin_catalog_resource_list_aggregates_bound_class_resources():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    class_a = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")
    class_b = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-b")
    async with async_session_factory() as db:
        db.add_all([
            Resource(
                id="resource-a",
                course_id=class_a,
                catalog_id=catalog_id,
                title="Doc A",
                type="lesson",
                description="a",
                tags=[],
                chapter="树",
                knowledge_point="二叉树",
                content="a",
            ),
            Resource(
                id="resource-b",
                course_id=class_b,
                catalog_id=catalog_id,
                title="Doc B",
                type="lesson",
                description="b",
                tags=[],
                chapter="树",
                knowledge_point="二叉树",
                content="b",
            ),
            Resource(
                id="resource-deleted",
                course_id=class_a,
                catalog_id=catalog_id,
                title="Deleted",
                type="lesson",
                description="d",
                tags=[],
                chapter="树",
                knowledge_point="二叉树",
                content="d",
                is_deleted=True,
            ),
        ])
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/admin/course-catalogs/{catalog_id}/resources",
            headers=_auth_headers("admin-admin-gen", "admin"),
        )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["total"] == 2
    assert [item["id"] for item in data["resources"]] == ["resource-b", "resource-a"]
    assert all(item["course_id"] in {class_a, class_b} for item in data["resources"])


@pytest.mark.asyncio
async def test_admin_soft_deletes_resource_and_hides_from_reads():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    class_id = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")
    async with async_session_factory() as db:
        db.add(
            Resource(
                id="resource-soft-delete",
                course_id=class_id,
                title="Delete Me",
                type="lesson",
                description="d",
                tags=[],
                chapter="树",
                knowledge_point="二叉树",
                content="d",
            )
        )
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(
            "/api/v1/admin/resources/resource-soft-delete",
            headers=_auth_headers("admin-admin-gen", "admin"),
        )
        list_response = await client.get(
            f"/api/v1/admin/course-catalogs/{catalog_id}/resources",
            headers=_auth_headers("admin-admin-gen", "admin"),
        )
        missing_response = await client.delete(
            "/api/v1/admin/resources/not-found-resource",
            headers=_auth_headers("admin-admin-gen", "admin"),
        )

    assert response.status_code == 200, response.text
    assert response.json()["data"] == {"id": "resource-soft-delete", "deleted": True}
    assert list_response.json()["data"]["resources"] == []
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"]["code"] == 40412
    async with async_session_factory() as db:
        resource = await db.get(Resource, "resource-soft-delete")
        assert resource.is_deleted is True
        assert resource.update_by == "admin-admin-gen"


@pytest.mark.asyncio
async def test_admin_soft_deletes_material_marks_catalog_dirty_and_recalculates_chunks():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    catalog_id = await _seed_ready_catalog(chunk_count=7)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(
            f"/api/v1/admin/course-catalogs/{catalog_id}/materials/material-admin-gen",
            headers=_auth_headers("admin-admin-gen", "admin"),
        )
        materials_response = await client.get(
            f"/api/v1/admin/course-catalogs/{catalog_id}/materials",
            headers=_auth_headers("admin-admin-gen", "admin"),
        )
        status_response = await client.get(
            f"/api/v1/admin/course-catalogs/{catalog_id}/knowledge-status",
            headers=_auth_headers("admin-admin-gen", "admin"),
        )
        missing_response = await client.delete(
            f"/api/v1/admin/course-catalogs/{catalog_id}/materials/not-found-material",
            headers=_auth_headers("admin-admin-gen", "admin"),
        )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["knowledge_status"] == "dirty"
    assert materials_response.json()["data"]["materials"] == []
    status_data = status_response.json()["data"]
    assert status_data["material_count"] == 0
    assert status_data["knowledge_status"] == "dirty"
    assert status_data["chunk_count"] == 0
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"]["code"] == 40411
    async with async_session_factory() as db:
        material = await db.get(CourseCatalogMaterial, "material-admin-gen")
        catalog = await db.get(CourseCatalog, catalog_id)
        assert material.is_deleted is True
        assert catalog.chunk_count == 0
