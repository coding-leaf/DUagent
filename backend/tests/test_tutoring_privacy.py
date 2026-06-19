import json
import os
import sys
import uuid

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_tutoring_privacy.db",
)

from app.db.session import async_session_factory, engine, init_db
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.conversation import Conversation, Message
from app.models.course import Course
from app.models.others import CourseKnowledgeGraph, UserProfile
from app.models.user import User
from app.services.tutoring_payload_builder import TutoringPayloadBuilder


@pytest_asyncio.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


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

        course_id = f"course_privacy_{suffix}"
        db.add(Course(
            id=course_id,
            name="隐私测试课程",
            course_code=f"PRIV{suffix[:6].upper()}",
            teacher_id=user.id,
        ))
        await db.flush()

        conversation = Conversation(
            user_id=user.id,
            scope="course",
            course_id=course_id,
            title="privacy",
        )
        db.add(conversation)
        db.add(UserProfile(
            user_id=user.id,
            course_id=course_id,
            guidance_level_current="L1",
            modal_preference=["text"],
            knowledge_coordinates=[
                {"name": "栈", "status": "mastered"},
                {"name": "队列", "status": "weak"},
            ],
        ))
        await db.commit()

        payload = await TutoringPayloadBuilder(db).build(
            user_id=user.id,
            scope="course",
            course_id=course_id,
            conversation_id=conversation.id,
            message="讲一下队列",
        )

    payload_text = json.dumps(payload, ensure_ascii=False)
    assert "real_name" not in payload_text
    assert "email" not in payload_text
    assert "student_id" not in payload_text
    assert "username" not in payload_text
    assert "张三" not in payload_text
    assert email not in payload_text
    assert student_id not in payload_text
    assert "learner_context" not in payload
    assert set(payload["user_profile"]) == {
        "guidance_level",
        "modal_preference",
        "knowledge_mastered",
        "knowledge_weak",
        "custom_instruction",
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

        payload = await TutoringPayloadBuilder(db).build(
            user_id=user.id,
            scope="course",
            course_id=course_id,
            conversation_id=conversation.id,
            message="讲一下 malloc",
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
        db.add(Course(
            id=course_id,
            name="最近消息测试课程",
            course_code=f"REC{suffix[:6].upper()}",
            teacher_id=user.id,
        ))
        await db.flush()
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

        payload = await TutoringPayloadBuilder(db).build(
            user_id=user.id,
            scope="course",
            course_id=course_id,
            conversation_id=conversation.id,
            message="我刚才说的变量名是什么？",
            exclude_message_ids={current_user_msg.id, current_assistant_placeholder.id},
        )

    assert [m["content"] for m in payload["recent_messages"]] == [
        "请记住：变量名是 alpha_count",
        "我记住了，变量名是 alpha_count。",
    ]


@pytest.mark.asyncio
async def test_global_payload_uses_default_profile_and_no_course_context():
    await init_db()
    async with async_session_factory() as db:
        suffix = uuid.uuid4().hex[:8]
        user = User(
            username=f"global_payload_{suffix}",
            email=f"global_payload_{suffix}@example.com",
            password_hash="hash",
        )
        db.add(user)
        await db.flush()
        conversation = Conversation(user_id=user.id, scope="global", title="global")
        db.add(conversation)
        await db.commit()

        payload = await TutoringPayloadBuilder(db).build(
            user_id=user.id,
            scope="global",
            course_id=None,
            conversation_id=conversation.id,
            message="hello",
        )

    assert "course_id" not in payload
    assert "catalog_id" not in payload
    assert payload["active_kg_nodes"] == []
    assert payload["user_profile"] == {"guidance_level": "L2"}
