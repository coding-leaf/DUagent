import os
import sys

import pytest
from fastapi import HTTPException

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:////tmp/course_catalog_ready_gate.db",
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import Base
from app.db.session import async_session_factory, engine as async_engine
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.course import Course
from app.models.user import User


async def _reset_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def _seed_course_with_catalog(
    *,
    catalog_status="ready",
    knowledge_status="ready",
    chunk_count=3,
    with_offering=True,
    with_catalog=True,
    catalog_deleted=False,
):
    async with async_session_factory() as db:
        teacher = User(
            id="teacher-ready-gate",
            email="teacher-ready-gate@example.com",
            username="teacher_ready_gate",
            password_hash="x",
            role="teacher",
        )
        course = Course(
            id="class-ready-gate",
            name="Ready Gate Class",
            course_code="RGCLASS1",
            teacher_id=teacher.id,
        )
        db.add_all([teacher, course])
        if with_catalog:
            catalog = CourseCatalog(
                id="catalog-ready-gate",
                title="Ready Gate Catalog",
                status=catalog_status,
                knowledge_status=knowledge_status,
                chunk_count=chunk_count,
                is_deleted=catalog_deleted,
            )
            db.add(catalog)
        if with_offering:
            db.add(
                CourseOffering(
                    id=course.id,
                    name=course.name,
                    catalog_id="catalog-ready-gate",
                    teacher_id=teacher.id,
                    class_code=course.course_code,
                )
            )
        await db.commit()
    return "class-ready-gate"


async def _resolve(course_id):
    from app.services.course_catalog_gate import resolve_generation_catalog

    async with async_session_factory() as db:
        return await resolve_generation_catalog(db, course_id)


def _detail(exc: HTTPException):
    return exc.detail


@pytest.mark.asyncio
async def test_missing_course_offering_returns_course_catalog_missing():
    await _reset_db()
    course_id = await _seed_course_with_catalog(with_offering=False)

    with pytest.raises(HTTPException) as exc:
        await _resolve(course_id)

    assert exc.value.status_code == 404
    assert _detail(exc.value)["code"] == "course_catalog_missing"


@pytest.mark.asyncio
async def test_missing_catalog_returns_course_catalog_missing():
    await _reset_db()
    course_id = await _seed_course_with_catalog(with_catalog=False)

    with pytest.raises(HTTPException) as exc:
        await _resolve(course_id)

    assert exc.value.status_code == 404
    assert _detail(exc.value)["code"] == "course_catalog_missing"


@pytest.mark.asyncio
async def test_deleted_catalog_returns_course_catalog_missing():
    await _reset_db()
    course_id = await _seed_course_with_catalog(catalog_deleted=True)

    with pytest.raises(HTTPException) as exc:
        await _resolve(course_id)

    assert exc.value.status_code == 404
    assert _detail(exc.value)["code"] == "course_catalog_missing"


@pytest.mark.asyncio
@pytest.mark.parametrize("catalog_status", ["draft", "ingesting", "failed"])
async def test_non_ready_catalog_status_returns_course_material_missing(catalog_status):
    await _reset_db()
    course_id = await _seed_course_with_catalog(catalog_status=catalog_status)

    with pytest.raises(HTTPException) as exc:
        await _resolve(course_id)

    assert exc.value.status_code == 409
    assert _detail(exc.value)["code"] == "course_material_missing"


@pytest.mark.asyncio
@pytest.mark.parametrize("knowledge_status", ["draft", "dirty", "ingesting", "failed"])
async def test_unusable_knowledge_status_returns_course_material_missing(knowledge_status):
    await _reset_db()
    course_id = await _seed_course_with_catalog(knowledge_status=knowledge_status)

    with pytest.raises(HTTPException) as exc:
        await _resolve(course_id)

    assert exc.value.status_code == 409
    assert _detail(exc.value)["code"] == "course_material_missing"


@pytest.mark.asyncio
@pytest.mark.parametrize("knowledge_status", ["ready", "partial"])
async def test_usable_status_with_zero_chunks_returns_knowledge_base_empty(knowledge_status):
    await _reset_db()
    course_id = await _seed_course_with_catalog(
        knowledge_status=knowledge_status,
        chunk_count=0,
    )

    with pytest.raises(HTTPException) as exc:
        await _resolve(course_id)

    assert exc.value.status_code == 409
    assert _detail(exc.value)["code"] == "knowledge_base_empty"


@pytest.mark.asyncio
async def test_ready_catalog_with_chunks_is_allowed():
    await _reset_db()
    course_id = await _seed_course_with_catalog(knowledge_status="ready", chunk_count=3)

    context = await _resolve(course_id)

    assert context.class_course_id == course_id
    assert context.catalog_id == "catalog-ready-gate"
    assert context.catalog_title == "Ready Gate Catalog"
    assert context.knowledge_status == "ready"
    assert context.chunk_count == 3
    assert context.degraded is False


@pytest.mark.asyncio
async def test_partial_catalog_with_chunks_is_allowed_as_degraded():
    await _reset_db()
    course_id = await _seed_course_with_catalog(knowledge_status="partial", chunk_count=2)

    context = await _resolve(course_id)

    assert context.catalog_id == "catalog-ready-gate"
    assert context.knowledge_status == "partial"
    assert context.chunk_count == 2
    assert context.degraded is True
