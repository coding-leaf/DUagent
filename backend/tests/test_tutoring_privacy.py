import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_tutoring_privacy.db",
)

from app.api.v1.tutoring import _assemble_tutoring_payload, _build_learner_context
from app.db.session import async_session_factory, init_db
from app.models.conversation import Conversation
from app.models.others import UserProfile
from app.models.user import User


@pytest.mark.asyncio
async def test_tutoring_payload_excludes_personal_identifiers():
    await init_db()

    async with async_session_factory() as db:
        suffix = uuid.uuid4().hex[:8]
        email = f"privacy_{suffix}@example.com"
        student_id = f"2026{suffix}"
        user = User(
            username=f"privacy_{suffix}",
            email=email,
            password_hash="hash",
            real_name="张三",
            student_id=student_id,
            major="计算机科学",
            grade="大一 (Freshman)",
            guidance_level="L3",
        )
        db.add(user)
        await db.flush()

        conversation = Conversation(
            user_id=user.id,
            scope="course",
            course_id=f"course_privacy_{suffix}",
            title="privacy",
        )
        db.add(conversation)
        db.add(UserProfile(
            user_id=user.id,
            course_id=f"course_privacy_{suffix}",
            guidance_level_current="L1",
            modal_preference=["text"],
            knowledge_coordinates=[
                {"name": "栈", "status": "mastered"},
                {"name": "队列", "status": "weak"},
            ],
        ))
        await db.commit()

        payload = await _assemble_tutoring_payload(
            user.id,
            "course",
            f"course_privacy_{suffix}",
            conversation.id,
            "讲一下队列",
            db,
        )

    payload_text = str(payload)
    assert "real_name" not in payload_text
    assert "email" not in payload_text
    assert "student_id" not in payload_text
    assert "username" not in payload_text
    assert "张三" not in payload_text
    assert email not in payload_text
    assert student_id not in payload_text
    assert "learner_context" not in payload
    assert _build_learner_context(user) == {
        "major": "计算机科学",
        "grade": "大一 (Freshman)",
        "guidance_level": "L3",
    }
