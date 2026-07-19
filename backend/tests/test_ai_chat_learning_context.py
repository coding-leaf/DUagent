import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_ai_chat_learning_context.db",
)

from app.db.session import async_session_factory, init_db
from app.models.course import Course
from app.models.others import CourseKnowledgeGraph, LearningActivity
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.models.user import User
from app.services.ai_chat_learning_context import (
    build_learning_progress_overview,
    normalize_question_options,
    query_recent_answers,
    resolve_node_knowledge_point,
)


@pytest.fixture(scope="module", autouse=True)
def _init_db():
    import asyncio

    asyncio.run(init_db())


async def _seed_context():
    suffix = uuid.uuid4().hex[:8]
    user = User(
        id=f"user_{suffix}",
        username=f"student_{suffix}",
        email=f"student_{suffix}@test.local",
        password_hash="x",
        role="student",
    )
    course = Course(
        id=f"course_{suffix}",
        name="数据结构",
        course_code=f"DS{suffix}",
        teacher_id=user.id,
    )
    kg = CourseKnowledgeGraph(
        id=f"kg_{suffix}",
        course_id=course.id,
        version=1,
        is_active=True,
        nodes=[
            {"id": "n-avl", "name": "AVL 树旋转", "chapter": "树"},
            {"id": "n-hash", "name": "散列冲突", "chapter": "散列"},
        ],
        edges=[],
    )
    now = datetime.now(timezone.utc)
    q1 = QuizQuestion(
        id=f"q1_{suffix}",
        course_id=course.id,
        chapter="树",
        knowledge_point="AVL 树旋转",
        type="single_choice",
        source="baseline",
        personalized=False,
        difficulty="medium",
        content="插入后应进行哪种旋转？",
        options=[{"key": "A", "text": "左旋"}, {"key": "B", "text": "右旋"}],
        correct_answer="B",
        explanation="根据失衡类型判断旋转方向。",
    )
    q2 = QuizQuestion(
        id=f"q2_{suffix}",
        course_id=course.id,
        chapter="树",
        knowledge_point="AVL 树旋转",
        type="multi_choice",
        source="baseline",
        personalized=False,
        difficulty="medium",
        content="哪些情况需要双旋？",
        options=["LR", "LL", "RL", "RR"],
        correct_answer="A,C",
        explanation="LR 和 RL 需要双旋。",
    )
    q3 = QuizQuestion(
        id=f"q3_{suffix}",
        course_id=course.id,
        chapter="散列",
        knowledge_point="散列冲突",
        type="single_choice",
        source="baseline",
        personalized=False,
        difficulty="easy",
        content="开放定址法用于什么？",
        options=["解决冲突", "排序"],
        correct_answer="A",
        explanation="开放定址法用于解决散列冲突。",
    )
    session = QuizSession(
        id=f"quiz_{suffix}",
        user_id=user.id,
        course_id=course.id,
        chapter="树",
        score=50,
        correct_count=1,
        total_count=2,
        time_spent=300,
    )
    answers_and_activity = [
        QuizAnswer(
            quiz_id=session.id,
            question_id=q1.id,
            user_answer="A",
            is_correct=False,
            correct_answer="B",
            explanation="根据失衡类型判断旋转方向。",
            create_time=now - timedelta(minutes=2),
        ),
        QuizAnswer(
            quiz_id=session.id,
            question_id=q2.id,
            user_answer="A",
            is_correct=True,
            correct_answer="A,C",
            explanation="LR 和 RL 需要双旋。",
            create_time=now - timedelta(minutes=1),
        ),
        QuizAnswer(
            quiz_id=session.id,
            question_id=q3.id,
            user_answer="B",
            is_correct=False,
            correct_answer="A",
            explanation="开放定址法用于解决散列冲突。",
            create_time=now,
        ),
        LearningActivity(
            user_id=user.id,
            course_id=course.id,
            node_id="n-avl",
            node_name="AVL 树旋转",
            activity_type="node_practice_submit",
            duration_seconds=300,
            occurred_at=now,
        ),
    ]
    async with async_session_factory() as db:
        db.add(user)
        await db.flush()
        db.add(course)
        await db.flush()
        db.add(kg)
        db.add_all([q1, q2, q3, session])
        await db.flush()
        db.add_all(answers_and_activity)
        await db.commit()
    return user.id, course.id


def test_normalize_question_options_supports_strings_and_objects():
    assert normalize_question_options(["左旋", "右旋"]) == [
        {"key": "A", "text": "左旋"},
        {"key": "B", "text": "右旋"},
    ]
    assert normalize_question_options([{"key": "T", "text": "正确"}]) == [
        {"key": "T", "text": "正确"}
    ]


@pytest.mark.asyncio
async def test_resolve_node_knowledge_point_uses_active_kg_node_name():
    _user_id, course_id = await _seed_context()
    async with async_session_factory() as db:
        resolved = await resolve_node_knowledge_point(db, course_id, "n-avl")
    assert resolved == "AVL 树旋转"


@pytest.mark.asyncio
async def test_query_recent_answers_filters_by_node_and_wrong_only():
    user_id, course_id = await _seed_context()
    async with async_session_factory() as db:
        result = await query_recent_answers(
            db,
            user_id=user_id,
            course_id=course_id,
            scope="node",
            node_id="n-avl",
            limit=10,
            only_wrong=True,
        )

    assert result["status"] == "available"
    assert result["scope"] == "node"
    assert result["query"]["resolved_knowledge_point"] == "AVL 树旋转"
    assert result["summary"]["returned_count"] == 1
    item = result["items"][0]
    assert item["knowledge_point"] == "AVL 树旋转"
    assert item["is_correct"] is False
    assert item["user_answer"] == "A"
    assert item["correct_answer"] == "B"
    assert item["options"] == [
        {"key": "A", "text": "左旋"},
        {"key": "B", "text": "右旋"},
    ]


@pytest.mark.asyncio
async def test_query_recent_answers_can_include_correct_answers_and_caps_limit():
    user_id, course_id = await _seed_context()
    async with async_session_factory() as db:
        result = await query_recent_answers(
            db,
            user_id=user_id,
            course_id=course_id,
            scope="knowledge_point",
            knowledge_point="AVL 树旋转",
            limit=99,
            only_wrong=False,
        )

    assert result["query"]["limit"] == 10
    assert result["summary"]["returned_count"] == 2
    assert {item["is_correct"] for item in result["items"]} == {True, False}


@pytest.mark.asyncio
async def test_build_learning_progress_overview_returns_node_metrics():
    user_id, course_id = await _seed_context()
    async with async_session_factory() as db:
        result = await build_learning_progress_overview(
            db,
            user_id=user_id,
            course_id=course_id,
            limit_nodes=50,
        )

    assert result["status"] == "available"
    assert result["course_id"] == course_id
    assert result["summary"]["total_nodes"] >= 2
    node = next(item for item in result["nodes"] if item["node_id"] == "n-avl")
    assert node["node_name"] == "AVL 树旋转"
    assert node["attempt_count"] >= 2
    assert node["wrong_count"] >= 1
    assert result["recent_activity"][0]["activity_type"] == "node_practice_submit"
