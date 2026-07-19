import os
import sys
from urllib.parse import urlparse

import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
if not TEST_DATABASE_URL.startswith("mysql+"):
    pytest.skip("requires TEST_DATABASE_URL=mysql+...", allow_module_level=True)

parsed_test_url = urlparse(TEST_DATABASE_URL)
test_database_name = parsed_test_url.path.strip("/")
if test_database_name == "duagent":
    pytest.skip("refusing to use the real duagent database", allow_module_level=True)

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException
from app.services.resource_service import ResourceService
from app.db.session import async_session_factory, engine
from app.db.base import Base
from app.models.course import Course, CourseEnrollment
from app.models.others import Resource, UserPersonalizedResource
from app.models.user import User


async def clean_and_init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest.mark.asyncio(loop_scope="module")
async def test_get_resource_detail_not_found():
    try:
        await clean_and_init_db()
        async with async_session_factory() as db:
            service = ResourceService(db)
            mock_user = User(id="user-123", email="user123@test.com", role="student")
            with pytest.raises(HTTPException) as exc:
                await service.get_resource_detail("invalid_resource_id", mock_user)
            assert exc.value.status_code == 404
    finally:
        await engine.dispose()


@pytest.mark.asyncio(loop_scope="module")
async def test_list_resources_unauthorized():
    try:
        await clean_and_init_db()
        async with async_session_factory() as db:
            service = ResourceService(db)
            mock_user = User(id="user-456", email="user456@test.com", role="student")
            with pytest.raises(HTTPException) as exc:
                await service.list_resources("course-nonexistent", mock_user)
            assert exc.value.status_code == 404
    finally:
        await engine.dispose()


@pytest.mark.asyncio(loop_scope="module")
async def test_public_resource_search_excludes_other_users_personalized_resources():
    try:
        await clean_and_init_db()
        async with async_session_factory() as db:
            teacher = User(
                id="teacher-resource",
                username="teacher_resource",
                email="teacher-resource@test.com",
                password_hash="x",
                role="teacher",
            )
            owner = User(
                id="resource-owner",
                username="resource_owner",
                email="resource-owner@test.com",
                password_hash="x",
                role="student",
            )
            classmate = User(
                id="resource-classmate",
                username="resource_classmate",
                email="resource-classmate@test.com",
                password_hash="x",
                role="student",
            )
            course = Course(
                id="course-resource-scope",
                name="Resource Scope",
                course_code="RESOURCE_SCOPE",
                teacher_id=teacher.id,
            )
            public_resource = Resource(
                id="public-resource",
                course_id=course.id,
                title="标准讲义",
                type="lesson",
                knowledge_point="变量与数据类型",
            )
            private_resource = Resource(
                id="private-resource",
                course_id=course.id,
                title="个人薄弱点讲义",
                type="lesson",
                knowledge_point="变量与数据类型",
                create_by=owner.id,
            )
            db.add_all([teacher, owner, classmate])
            await db.flush()
            db.add(course)
            await db.flush()
            db.add_all([
                CourseEnrollment(student_id=owner.id, course_id=course.id),
                CourseEnrollment(student_id=classmate.id, course_id=course.id),
                public_resource,
                private_resource,
            ])
            await db.flush()
            db.add(
                UserPersonalizedResource(
                    user_id=owner.id,
                    course_id=course.id,
                    resource_id=private_resource.id,
                    source_type="ai_chat",
                )
            )
            await db.commit()

        async with async_session_factory() as db:
            service = ResourceService(db)
            resources, total = await service.list_resources(
                course.id,
                classmate,
                keyword="变量与数据类型",
            )
            assert total == 1
            assert [resource.id for resource in resources] == [public_resource.id]

            with pytest.raises(HTTPException) as exc:
                await service.get_resource_detail(private_resource.id, classmate)
            assert exc.value.status_code == 403

            resource, _preview = await service.get_resource_detail(private_resource.id, owner)
            assert resource.id == private_resource.id
    finally:
        await engine.dispose()
