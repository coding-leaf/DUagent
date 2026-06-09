import os
import sys
from unittest.mock import AsyncMock, patch

import pytest
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
from app.models.others import AsyncTask, Resource
from app.models.user import User


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
async def test_admin_catalog_generation_creates_task_and_sends_catalog_id_to_agent():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    class_a = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")
    class_b = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-b")

    with patch("app.api.v1.catalogs.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = {"task_id": "ignored"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/resources/generations",
                headers=_auth_headers("admin-admin-gen", "admin"),
                json={
                    "chapter": "树",
                    "knowledge_point": "二叉树",
                    "resource_types": ["document", "mindmap"],
                },
            )

    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["catalog_id"] == catalog_id
    assert data["status"] == "processing"
    assert data["task_id"]

    payload = mock_agent.await_args.args[1]
    assert payload["course_id"] == catalog_id
    assert payload["chapter"] == "树"
    assert payload["knowledge_point"] == "二叉树"
    assert payload["resource_types"] == ["document", "mindmap"]

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
async def test_admin_catalog_generation_rejects_no_bound_classes_without_task():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    catalog_id = await _seed_ready_catalog()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/admin/course-catalogs/{catalog_id}/resources/generations",
            headers=_auth_headers("admin-admin-gen", "admin"),
            json={"resource_types": ["document"]},
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
            json={"resource_types": ["document", "bad"]},
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
            json={"resource_types": ["document"]},
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
            json={"resource_types": ["document"]},
        )

    assert response.status_code == 403


def _webhook_headers() -> dict:
    from app.core.config import settings

    return {"X-Webhook-Secret": settings.WEBHOOK_SECRET}


@pytest.mark.asyncio
async def test_webhook_fanout_writes_resources_to_bound_classes():
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
                            "type": "document",
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
        assert sorted(resource.course_id for resource in resources) == [class_a, class_b]
        assert len(resources) == 2
        task = await db.get(AsyncTask, "task-admin-gen")
        assert task.result["catalog_id"] == catalog_id
        assert task.result["fanout_course_ids"] == [class_a, class_b]
        assert task.result["resource_count"] == 1
        assert task.result["agent_result"]["resources"][0]["title"] == "Catalog Doc"


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
                title="Doc A",
                type="document",
                description="a",
                tags=[],
                chapter="树",
                knowledge_point="二叉树",
                content="a",
            ),
            Resource(
                id="resource-b",
                course_id=class_b,
                title="Doc B",
                type="document",
                description="b",
                tags=[],
                chapter="树",
                knowledge_point="二叉树",
                content="b",
            ),
            Resource(
                id="resource-deleted",
                course_id=class_a,
                title="Deleted",
                type="document",
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
                type="document",
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
async def test_admin_soft_deletes_material_marks_catalog_dirty_without_changing_chunks():
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
    assert status_data["chunk_count"] == 7
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"]["code"] == 40411
    async with async_session_factory() as db:
        material = await db.get(CourseCatalogMaterial, "material-admin-gen")
        catalog = await db.get(CourseCatalog, catalog_id)
        assert material.is_deleted is True
        assert catalog.chunk_count == 7
