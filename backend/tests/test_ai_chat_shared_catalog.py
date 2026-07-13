import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_ai_chat_shared_catalog.db",
)

from app.db.session import async_session_factory, init_db
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.course import Course
from app.models.others import CourseKnowledgeGraph
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.models.user import User
from app.services.ai_chat_learning_context import query_recent_answers


@pytest.fixture(scope="module", autouse=True)
def _init_db():
    import asyncio

    asyncio.run(init_db())


@pytest.mark.asyncio
async def test_query_recent_answers_resolves_node_from_shared_catalog_kg():
    suffix = uuid.uuid4().hex[:8]
    user = User(
        id=f"shared_user_{suffix}",
        username=f"shared_student_{suffix}",
        email=f"shared_student_{suffix}@test.local",
        password_hash="x",
        role="student",
    )
    host_course = Course(
        id=f"host_{suffix}",
        name="C语言资源宿主",
        course_code=f"HOST{suffix}",
        teacher_id=user.id,
    )
    class_course = Course(
        id=f"class_{suffix}",
        name="C语言教学班",
        course_code=f"CLASS{suffix}",
        teacher_id=user.id,
    )
    catalog = CourseCatalog(
        id=f"catalog_{suffix}",
        title="C语言共享库",
        status="ready",
        knowledge_status="ready",
        kg_host_course_id=host_course.id,
    )
    offering = CourseOffering(
        id=class_course.id,
        name=class_course.name,
        catalog_id=catalog.id,
        teacher_id=user.id,
        class_code=f"SH{suffix}",
    )
    graph = CourseKnowledgeGraph(
        id=f"shared_kg_{suffix}",
        course_id=host_course.id,
        version=1,
        is_active=True,
        nodes=[{"id": "constants", "name": "常量与字面量", "chapter": "基础"}],
        edges=[],
    )
    question = QuizQuestion(
        id=f"shared_q_{suffix}",
        course_id=host_course.id,
        catalog_id=catalog.id,
        chapter="基础",
        knowledge_point="常量与字面量",
        type="single_choice",
        source="baseline",
        personalized=False,
        difficulty="easy",
        content="字符常量使用哪种引号？",
        options=["单引号", "双引号"],
        correct_answer="A",
    )
    session = QuizSession(
        id=f"shared_quiz_{suffix}",
        user_id=user.id,
        course_id=class_course.id,
        chapter="基础",
        score=0,
        correct_count=0,
        total_count=1,
    )
    answer = QuizAnswer(
        quiz_id=session.id,
        question_id=question.id,
        user_answer="B",
        is_correct=False,
        correct_answer="A",
    )
    async with async_session_factory() as db:
        db.add(user)
        await db.flush()
        db.add_all([host_course, class_course])
        await db.flush()
        db.add(catalog)
        await db.flush()
        db.add_all([offering, graph, question, session])
        await db.flush()
        db.add(answer)
        await db.commit()

        result = await query_recent_answers(
            db,
            user_id=user.id,
            course_id=class_course.id,
            node_id="constants",
            only_wrong=True,
        )

    assert result["status"] == "available"
    assert result["query"]["resolved_knowledge_point"] == "常量与字面量"
    assert result["summary"]["returned_count"] == 1
