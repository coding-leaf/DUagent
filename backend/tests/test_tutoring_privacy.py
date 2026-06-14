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
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.conversation import Conversation, Message
from app.models.course import Course
from app.models.others import CourseKnowledgeGraph, UserProfile
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


@pytest.mark.asyncio
async def test_tutoring_payload_uses_active_kg_nodes_field():
    await init_db()

    async with async_session_factory() as db:
        suffix = uuid.uuid4().hex[:8]
        user = User(
            username=f"kg_payload_{suffix}",
            email=f"kg_payload_{suffix}@example.com",
            password_hash="hash",
            role="teacher",
        )
        db.add(user)
        await db.flush()

        catalog_id = f"catalog_{suffix}"
        host_course_id = f"host_{suffix}"
        course_id = f"course_{suffix}"
        db.add_all([
            Course(
                id=host_course_id,
                name="C 语言资源库宿主课程",
                course_code=f"HKG{suffix[:6].upper()}",
                teacher_id=user.id,
            ),
            Course(
                id=course_id,
                name="C 语言程序设计",
                course_code=f"CKG{suffix[:6].upper()}",
                teacher_id=user.id,
            ),
        ])
        await db.flush()

        conversation = Conversation(
            user_id=user.id,
            scope="course",
            course_id=course_id,
            title="kg payload",
        )
        db.add_all([
            CourseCatalog(
                id=catalog_id,
                title="C 语言资源库",
                kg_host_course_id=host_course_id,
            ),
            CourseOffering(
                id=course_id,
                name="C 语言程序设计",
                catalog_id=catalog_id,
                teacher_id=user.id,
                class_code=f"KG{suffix[:6].upper()}",
            ),
            CourseKnowledgeGraph(
                course_id=host_course_id,
                version=1,
                is_active=True,
                source_type="catalog_chunks",
                generation_strategy="catalog_chunks_llm",
                nodes=[
                    {"id": "n1", "name": "指针", "chapter": "第 6 章"},
                    {"id": "n2", "name": "malloc/free", "chapter": "第 7 章", "extra": "hidden"},
                ],
                edges=[{"from": "n1", "to": "n2"}],
            ),
            conversation,
        ])
        await db.commit()

        payload = await _assemble_tutoring_payload(
            user.id,
            "course",
            course_id,
            conversation.id,
            "讲一下 malloc",
            db,
        )

    assert payload["active_kg_nodes"] == [
        {"id": "n1", "name": "指针", "chapter": "第 6 章"},
        {"id": "n2", "name": "malloc/free", "chapter": "第 7 章"},
    ]


@pytest.mark.asyncio
async def test_tutoring_payload_recent_messages_excludes_current_turn_placeholders():
    await init_db()

    async with async_session_factory() as db:
        suffix = uuid.uuid4().hex[:8]
        user = User(
            username=f"recent_{suffix}",
            email=f"recent_{suffix}@example.com",
            password_hash="hash",
        )
        db.add(user)
        await db.flush()

        course_id = f"course_recent_{suffix}"
        conversation = Conversation(
            user_id=user.id,
            scope="course",
            course_id=course_id,
            title="recent payload",
        )
        db.add(conversation)
        await db.flush()

        db.add_all([
            Message(
                conversation_id=conversation.id,
                role="user",
                content="请记住：变量名是 alpha_count",
            ),
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content="我记住了，变量名是 alpha_count。",
            ),
        ])
        await db.flush()

        current_user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content="我刚才说的变量名是什么？",
        )
        current_assistant_placeholder = Message(
            conversation_id=conversation.id,
            role="assistant",
            content="",
        )
        db.add_all([current_user_msg, current_assistant_placeholder])
        await db.commit()

        payload = await _assemble_tutoring_payload(
            user.id,
            "course",
            course_id,
            conversation.id,
            "我刚才说的变量名是什么？",
            db,
            exclude_message_ids={current_user_msg.id, current_assistant_placeholder.id},
        )

    assert [m["content"] for m in payload["recent_messages"]] == [
        "请记住：变量名是 alpha_count",
        "我记住了，变量名是 alpha_count。",
    ]
