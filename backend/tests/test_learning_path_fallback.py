"""Unit tests for _topo_sort_kg_nodes in learning_path.py fallback path.

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
from app.api.v1.learning_path import _topo_sort_kg_nodes


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
        result = _topo_sort_kg_nodes(nodes, edges)
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
        result = _topo_sort_kg_nodes(nodes, edges)
        ids = [n["id"] for n in result]
        assert ids[0] in ("a", "b")
        assert ids[1] in ("a", "b")
        assert ids[2] == "c"

    def test_no_edges_falls_back_to_original_order(self):
        nodes = [
            {"id": "z", "name": "Z", "chapter": "Ch3"},
            {"id": "a", "name": "A", "chapter": "Ch1"},
        ]
        result = _topo_sort_kg_nodes(nodes, [])
        ids = [n["id"] for n in result]
        assert ids == ["z", "a"]

    def test_empty_nodes(self):
        assert _topo_sort_kg_nodes([], []) == []

    def test_preserves_all_node_fields(self):
        nodes = [
            {"id": "n1", "name": "Node1", "chapter": "Ch1"},
        ]
        result = _topo_sort_kg_nodes(nodes, [{"from": "n1", "to": "n2"}])
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
        result = _topo_sort_kg_nodes(nodes, edges)
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

from app.db.session import async_session_factory, init_db  # noqa: E402

asyncio.run(init_db())

from app.main import app  # noqa: E402
from app.models.catalog import CourseCatalog, CourseOffering  # noqa: E402
from app.models.others import CourseKnowledgeGraph  # noqa: E402
from app.models.user import RegistrationCode  # noqa: E402
from httpx import AsyncClient, ASGITransport  # noqa: E402


async def _captcha_answer(client):
    r = await client.get("/api/v1/auth/captcha")
    d = r.json()["data"]
    nums = re.findall(r"\d+", d["captcha_question"])
    ans = str(int(nums[0]) + int(nums[1])) if "+" in d["captcha_question"] else str(int(nums[0]) - int(nums[1]))
    return d["captcha_token"], ans


@pytest.mark.asyncio
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

        # Seed: CourseCatalog + KG + CourseOffering
        catalog_id = f"cat_{uuid.uuid4().hex[:8]}"
        host_course_id = f"hcourse_{uuid.uuid4().hex[:8]}"
        course_id = f"course_{uuid.uuid4().hex[:8]}"

        async with async_session_factory() as db:
            db.add(CourseCatalog(
                id=catalog_id, title="Test Catalog",
                kg_host_course_id=host_course_id,
            ))
            db.add(CourseOffering(
                id=course_id, name="Test Class", catalog_id=catalog_id,
                teacher_id=user_id, class_code=f"CLS_{uuid.uuid4().hex[:6].upper()}",
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
        assert data["source"] == "kg_fallback"
        assert len(data["nodes"]) == 2
        assert data["nodes"][0]["id"] == "n1"
        assert data["nodes"][0]["status"] == "recommended"
        assert data["nodes"][0]["order"] == 1
        assert data["nodes"][1]["id"] == "n2"
        assert data["current_position"]["node_id"] == "n1"
        assert len(data["edges"]) == 1
        assert data["generated_at"] is not None


@pytest.mark.asyncio
async def test_learning_path_kg_fallback_no_course_offering_returns_empty():
    """When CourseOffering doesn't exist, return empty nodes."""
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
        await client.post("/api/v1/auth/register", json={
            "registration_code": reg_code, "email": email,
            "password": "Abc12345", "username": username,
            "captcha_token": ct_token, "captcha_code": ct_ans,
        })
        ct_token, ct_ans = await _captcha_answer(client)
        r = await client.post("/api/v1/auth/login", json={
            "email": email,
            "password": "Abc12345",
            "captcha_token": ct_token, "captcha_code": ct_ans,
        })
        headers = {"Authorization": f"Bearer {r.json()['data']['token']}"}

        r = await client.get("/api/v1/learning-path?course_id=nonexistent_course", headers=headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["source"] == "kg_fallback"
        assert data["nodes"] == []
        assert data["current_position"] is None
