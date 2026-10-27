"""Unit tests for topo_sort_kg_nodes in learning_path service fallback path.

Run: python -m pytest tests/test_learning_path_fallback.py -v
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_learning_path_fb.db",
)

import pytest
from app.services.learning_path_service import topo_sort_kg_nodes


class TestTopoSortKgNodes:
    def test_sorts_simple_dag(self):
        nodes = [
            {"id": "a", "name": "A", "chapter": "Ch1"},
            {"id": "b", "name": "B", "chapter": "Ch1"},
            {"id": "c", "name": "C", "chapter": "Ch2"},
        ]
        edges = [
            {"from": "a", "to": "b"},
            {"from": "b", "to": "c"},
        ]
        result = topo_sort_kg_nodes(nodes, edges)
        ids = [n["id"] for n in result]
        assert ids == ["a", "b", "c"]

    def test_multiple_roots(self):
        nodes = [
            {"id": "a", "name": "A", "chapter": "Ch1"},
            {"id": "b", "name": "B", "chapter": "Ch1"},
            {"id": "c", "name": "C", "chapter": "Ch2"},
        ]
        edges = [
            {"from": "a", "to": "c"},
            {"from": "b", "to": "c"},
        ]
        result = topo_sort_kg_nodes(nodes, edges)
        ids = [n["id"] for n in result]
        assert ids[0] in ("a", "b")
        assert ids[1] in ("a", "b")
        assert ids[2] == "c"

    def test_no_edges_falls_back_to_original_order(self):
        nodes = [
            {"id": "z", "name": "Z", "chapter": "Ch3"},
            {"id": "a", "name": "A", "chapter": "Ch1"},
        ]
        result = topo_sort_kg_nodes(nodes, [])
        ids = [n["id"] for n in result]
        assert ids == ["z", "a"]

    def test_empty_nodes(self):
        assert topo_sort_kg_nodes([], []) == []

    def test_preserves_all_node_fields(self):
        nodes = [
            {"id": "n1", "name": "Node1", "chapter": "Ch1"},
        ]
        result = topo_sort_kg_nodes(nodes, [{"from": "n1", "to": "n2"}])
        assert result[0]["id"] == "n1"
        assert result[0]["name"] == "Node1"
        assert result[0]["chapter"] == "Ch1"

    def test_disjoint_subgraphs(self):
        nodes = [
            {"id": "a", "name": "A", "chapter": "Ch1"},
            {"id": "b", "name": "B", "chapter": "Ch1"},
            {"id": "c", "name": "C", "chapter": "Ch2"},
            {"id": "d", "name": "D", "chapter": "Ch2"},
        ]
        edges = [
            {"from": "a", "to": "b"},
            {"from": "c", "to": "d"},
        ]
        result = topo_sort_kg_nodes(nodes, edges)
        ids = [n["id"] for n in result]
        assert ids.index("a") < ids.index("b")
        assert ids.index("c") < ids.index("d")


# ── Integration tests (KG fallback via API) ──────────────────────────────
import asyncio
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_learning_path_fb.db",
)

import pytest_asyncio
from app.db.session import async_session_factory, engine, init_db  # noqa: E402


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_test_schema():
    await init_db()
    yield
    await engine.dispose()

from app.main import app  # noqa: E402
from app.models.catalog import CourseCatalog, CourseOffering  # noqa: E402
from app.models.course import Course, CourseEnrollment  # noqa: E402
from app.models.others import CourseKnowledgeGraph  # noqa: E402
from app.models.user import RegistrationCode, User  # noqa: E402
from app.models.quiz import QuizQuestion  # noqa: E402
from httpx import AsyncClient, ASGITransport  # noqa: E402


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


async def _captcha_answer(client):
    r = await client.get("/api/v1/auth/captcha")
    d = r.json()["data"]
    nums = re.findall(r"\d+", d["captcha_question"])
    ans = str(int(nums[0]) + int(nums[1])) if "+" in d["captcha_question"] else str(int(nums[0]) - int(nums[1]))
    return d["captcha_token"], ans


@pytest.mark.asyncio(loop_scope="module")
async def test_learning_path_kg_fallback_returns_nodes():
    """When no LearningPath exists, GET /learning-path should return KG fallback with nodes."""
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Seed: register+login student
        suffix = uuid.uuid4().hex[:8]
        reg_code = f"lpfb_{suffix}"
        email = f"lpfb_{uuid.uuid4().hex[:6]}@t.com"
        username = f"lpfb_{uuid.uuid4().hex[:6]}"

        async with async_session_factory() as db:
            db.add(RegistrationCode(code=reg_code, role="student"))
            await db.commit()

        ct_token, ct_ans = await _captcha_answer(client)
        r = await client.post("/api/v1/auth/register", json={
            "registration_code": reg_code, "email": email,
            "password": "Abc12345", "username": username,
            "captcha_token": ct_token, "captcha_code": ct_ans,
        })
        assert r.status_code == 201, f"Register failed: {r.json()}"
        user_id = r.json()["data"]["user_id"]

        ct_token, ct_ans = await _captcha_answer(client)
        r = await client.post("/api/v1/auth/login", json={
            "email": email,
            "password": "Abc12345",
            "captcha_token": ct_token, "captcha_code": ct_ans,
        })
        headers = {"Authorization": f"Bearer {r.json()['data']['token']}"}

        # Seed: CourseCatalog + KG + CourseOffering + Course + Enrollment
        catalog_id = f"cat_{uuid.uuid4().hex[:8]}"
        host_course_id = f"hcourse_{uuid.uuid4().hex[:8]}"
        course_id = f"course_{uuid.uuid4().hex[:8]}"
        teacher_id = f"teacher_{uuid.uuid4().hex[:8]}"
        await _seed_user(teacher_id, "teacher")

        async with async_session_factory() as db:
            db.add(Course(
                id=host_course_id,
                name="Test Catalog Host Course",
                course_code=f"HOST_{uuid.uuid4().hex[:6].upper()}",
                teacher_id=teacher_id,
            ))
            db.add(Course(
                id=course_id,
                name="Test Class Course",
                course_code=f"CLS_{uuid.uuid4().hex[:6].upper()}",
                teacher_id=teacher_id,
            ))
            await db.flush()
            db.add(CourseEnrollment(course_id=course_id, student_id=user_id))
            db.add(CourseCatalog(
                id=catalog_id, title="Test Catalog",
                kg_host_course_id=host_course_id,
            ))
            db.add(CourseOffering(
                id=course_id, name="Test Class", catalog_id=catalog_id,
                teacher_id=teacher_id, class_code=f"CLS_{uuid.uuid4().hex[:6].upper()}",
            ))
            await db.flush()

            db.add(CourseKnowledgeGraph(
                course_id=host_course_id, version=1, is_active=True,
                source_type="catalog_chunks", generation_strategy="catalog_chunks_llm",
                nodes=[{"id": "n1", "name": "Node1", "chapter": "Ch1"},
                       {"id": "n2", "name": "Node2", "chapter": "Ch2"}],
                edges=[{"from": "n1", "to": "n2"}],
            ))
            await db.commit()

        # Test: GET /learning-path
        r = await client.get(f"/api/v1/learning-path?course_id={course_id}", headers=headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["source"] == "kg_realtime"
        assert len(data["nodes"]) == 2
        assert data["nodes"][0]["id"] == "n1"
        assert data["nodes"][0]["status"] == "pending"
        assert data["nodes"][0]["order"] == 1
        assert data["nodes"][1]["id"] == "n2"
        assert data["current_position"]["node_id"] == "n1"
        assert len(data["edges"]) == 1
        assert data["generated_at"] is not None


@pytest.mark.asyncio(loop_scope="module")
async def test_learning_path_kg_fallback_no_course_offering_returns_empty():
    """When CourseOffering doesn't exist, return empty nodes; unenrolled returns 403, missing 404."""
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        suffix = uuid.uuid4().hex[:8]
        reg_code = f"lpfb2_{suffix}"
        email = f"lpfb2_{uuid.uuid4().hex[:6]}@t.com"
        username = f"lpfb2_{uuid.uuid4().hex[:6]}"

        async with async_session_factory() as db:
            db.add(RegistrationCode(code=reg_code, role="student"))
            await db.commit()

        ct_token, ct_ans = await _captcha_answer(client)
        r = await client.post("/api/v1/auth/register", json={
            "registration_code": reg_code, "email": email,
            "password": "Abc12345", "username": username,
            "captcha_token": ct_token, "captcha_code": ct_ans,
        })
        assert r.status_code == 201
        user_id = r.json()["data"]["user_id"]

        ct_token, ct_ans = await _captcha_answer(client)
        r = await client.post("/api/v1/auth/login", json={
            "email": email,
            "password": "Abc12345",
            "captcha_token": ct_token, "captcha_code": ct_ans,
        })
        headers = {"Authorization": f"Bearer {r.json()['data']['token']}"}

        # 1. Nonexistent course returns 404
        r = await client.get("/api/v1/learning-path?course_id=nonexistent_course", headers=headers)
        assert r.status_code == 404

        teacher_id = f"teacher_{uuid.uuid4().hex[:8]}"
        unenrolled_course_id = f"course_{uuid.uuid4().hex[:8]}"
        enrolled_course_id = f"course_{uuid.uuid4().hex[:8]}"
        await _seed_user(teacher_id, "teacher")

        async with async_session_factory() as db:
            db.add(Course(
                id=unenrolled_course_id,
                name="Unenrolled Course",
                course_code=f"UNEN_{uuid.uuid4().hex[:6].upper()}",
                teacher_id=teacher_id,
            ))
            db.add(Course(
                id=enrolled_course_id,
                name="Enrolled Course Without Offering",
                course_code=f"ENR_{uuid.uuid4().hex[:6].upper()}",
                teacher_id=teacher_id,
            ))
            await db.flush()
            db.add(CourseEnrollment(course_id=enrolled_course_id, student_id=user_id))
            await db.commit()

        # 2. Unenrolled course returns 403
        r = await client.get(f"/api/v1/learning-path?course_id={unenrolled_course_id}", headers=headers)
        assert r.status_code == 403

        # 3. Enrolled course without CourseOffering / KG returns 200 empty nodes
        r = await client.get(f"/api/v1/learning-path?course_id={enrolled_course_id}", headers=headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["source"] == "kg_fallback"
        assert data["nodes"] == []
        assert data["current_position"] is None
        assert data["edges"] == []
        assert data["generated_at"] is None


@pytest.mark.asyncio(loop_scope="module")
async def test_quiz_questions_node_id_filter_returns_node_questions():
    """GET /quiz/questions?node_id=xxx should return only that node's questions."""
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        suffix = uuid.uuid4().hex[:8]
        reg_code = f"qzfb_{suffix}"
        email = f"qznode_{suffix[:6]}@t.com"
        username = f"qznode_{suffix[:6]}"

        async with async_session_factory() as db:
            db.add(RegistrationCode(code=reg_code, role="student"))
            await db.commit()

        ct_token, ct_ans = await _captcha_answer(client)
        r = await client.post("/api/v1/auth/register", json={
            "registration_code": reg_code, "email": email, "password": "Abc12345",
            "username": username, "captcha_token": ct_token, "captcha_code": ct_ans,
        })
        assert r.status_code == 201
        user_id = r.json()["data"]["user_id"]

        ct_token, ct_ans = await _captcha_answer(client)
        r = await client.post("/api/v1/auth/login", json={
            "email": email, "password": "Abc12345",
            "captcha_token": ct_token, "captcha_code": ct_ans,
        })
        headers = {"Authorization": f"Bearer {r.json()['data']['token']}"}

        catalog_id = f"qzcat_{suffix[:8]}"
        host_course_id = f"qzhc_{suffix[:8]}"
        course_id = f"qzco_{suffix[:8]}"
        teacher_id = f"teacher_{suffix[:8]}"
        await _seed_user(teacher_id, "teacher")

        async with async_session_factory() as db:
            db.add(Course(id=host_course_id, name="QZ Host Course",
                          course_code=f"QZH{suffix[:6].upper()}", teacher_id=teacher_id))
            db.add(Course(id=course_id, name="QZ Offering Course",
                          course_code=f"QZO{suffix[:6].upper()}", teacher_id=teacher_id))
            await db.flush()
            db.add(CourseEnrollment(course_id=course_id, student_id=user_id))
            db.add(CourseCatalog(id=catalog_id, title="QZ Catalog", kg_host_course_id=host_course_id))
            db.add(CourseOffering(id=course_id, name="QZ Class", catalog_id=catalog_id,
                                  teacher_id=teacher_id, class_code=f"QZ{suffix[:4].upper()}"))
            await db.flush()
            db.add(CourseKnowledgeGraph(course_id=host_course_id, version=1, is_active=True,
                source_type="catalog_chunks", generation_strategy="catalog_chunks_llm",
                nodes=[{"id":"n1","name":"Node1","chapter":"Ch1"}],
                edges=[]))
            db.add(QuizQuestion(course_id=course_id, chapter="Ch1", knowledge_point="Node1",
                type="single_choice", source="common", content="Q1 for Node1",
                correct_answer="A", options={"A":"x","B":"y"}))
            db.add(QuizQuestion(course_id=course_id, chapter="Ch1", knowledge_point="OtherNode",
                type="single_choice", source="common", content="Q2 for Other",
                correct_answer="B", options={"A":"x","B":"y"}))
            await db.commit()

        r = await client.get(f"/api/v1/quiz/questions?course_id={course_id}&node_id=n1", headers=headers)
        assert r.status_code == 200
        questions = r.json()["data"]["questions"]
        assert len(questions) == 1
        assert questions[0]["content"] == "Q1 for Node1"


@pytest.mark.asyncio(loop_scope="module")
async def test_quiz_questions_course_access_guards():
    """GET /quiz/questions should return 404 for nonexistent course and 403 for unenrolled student."""
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        suffix = uuid.uuid4().hex[:8]
        reg_code = f"qzguard_{suffix}"
        email = f"qzguard_{suffix[:6]}@t.com"
        username = f"qzguard_{suffix[:6]}"

        async with async_session_factory() as db:
            db.add(RegistrationCode(code=reg_code, role="student"))
            await db.commit()

        ct_token, ct_ans = await _captcha_answer(client)
        r = await client.post("/api/v1/auth/register", json={
            "registration_code": reg_code, "email": email, "password": "Abc12345",
            "username": username, "captcha_token": ct_token, "captcha_code": ct_ans,
        })
        assert r.status_code == 201

        ct_token, ct_ans = await _captcha_answer(client)
        r = await client.post("/api/v1/auth/login", json={
            "email": email, "password": "Abc12345",
            "captcha_token": ct_token, "captcha_code": ct_ans,
        })
        headers = {"Authorization": f"Bearer {r.json()['data']['token']}"}

        # 1. Nonexistent course returns 404
        r = await client.get("/api/v1/quiz/questions?course_id=nonexistent_course", headers=headers)
        assert r.status_code == 404

        # 2. Existing course without enrollment returns 403
        teacher_id = f"teacher_{suffix[:8]}"
        course_id = f"course_guard_{suffix[:8]}"
        await _seed_user(teacher_id, "teacher")
        async with async_session_factory() as db:
            db.add(Course(id=course_id, name="Guard Course",
                          course_code=f"GD_{suffix[:4].upper()}", teacher_id=teacher_id))
            await db.commit()

        r = await client.get(f"/api/v1/quiz/questions?course_id={course_id}", headers=headers)
        assert r.status_code == 403

