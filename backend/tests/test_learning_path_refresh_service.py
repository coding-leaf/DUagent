import asyncio
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_learning_path_refresh_service.db",
)

from app.db.session import async_session_factory, engine, init_db  # noqa: E402

asyncio.run(init_db())
asyncio.run(engine.dispose())

from app.models.others import AsyncTask  # noqa: E402
from app.models.course import Course  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.learning_path_refresh_service import LearningPathRefreshService  # noqa: E402


@pytest.mark.asyncio(loop_scope="module")
async def test_create_refresh_task_uses_learning_path_task_type():
    suffix = uuid.uuid4().hex[:8]
    user_id = f"user_{suffix}"
    course_id = f"course_{suffix}"
    teacher_id = f"teacher_{suffix}"

    async with async_session_factory() as db:
        db.add(User(
            id=teacher_id,
            username=f"teacher_{suffix}",
            email=f"teacher_{suffix}@test.com",
            password_hash="hash",
            role="teacher",
        ))
        db.add(User(
            id=user_id,
            username=f"user_{suffix}",
            email=f"user_{suffix}@test.com",
            password_hash="hash",
            role="student",
        ))
        db.add(Course(
            id=course_id,
            name="Learning Path Refresh Service Course",
            course_code=f"LPRS{suffix[:6].upper()}",
            teacher_id=teacher_id,
        ))
        await db.flush()

        task = await LearningPathRefreshService(db).create_refresh_task(user_id, course_id)
        await db.commit()

        persisted = await db.get(AsyncTask, task.id)

    assert persisted is not None
    assert persisted.task_type == "learning_path_refresh"
    assert persisted.status == "processing"
    assert persisted.user_id == user_id
    assert persisted.course_id == course_id
