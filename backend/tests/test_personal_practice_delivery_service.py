import os
import sys
import uuid
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_personal_practice_delivery.db",
)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import async_session_factory, engine, init_db
from app.models.conversation import Conversation
from app.models.code_problem import CodeProblem, CodeProblemTestCase
from app.models.course import Course, CourseEnrollment
from app.models.others import UserPersonalizedResource
from app.models.personalized_resource_generation import PersonalizedResourceGeneration
from app.models.quiz import QuizQuestion
from app.models.user import User
from app.schemas.internal_ai_chat import PersonalPracticePrepareRequest
from app.services.personal_practice_delivery_service import (
    finalize_personal_practice_delivery,
    prepare_personal_practice_delivery,
    record_personal_practice_delivery_failure,
    resume_personal_practice_delivery,
)


@pytest_asyncio.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def practice_scope():
    await init_db()
    suffix = uuid.uuid4().hex[:8]
    async with async_session_factory() as db:
        user = User(
            id=f"practice_user_{suffix}",
            username=f"practice_{suffix}",
            email=f"practice_{suffix}@test.local",
            password_hash="x",
            role="student",
        )
        course = Course(
            id=f"practice_course_{suffix}",
            name="C 语言",
            course_code=f"P{suffix}",
            teacher_id=user.id,
        )
        db.add_all([user, course])
        await db.flush()
        enrollment = CourseEnrollment(student_id=user.id, course_id=course.id)
        conversation = Conversation(user_id=user.id, course_id=course.id, scope="course")
        db.add_all([enrollment, conversation])
        await db.commit()
        yield user.id, course.id, conversation.id

        problem_ids = select(CodeProblem.id).where(CodeProblem.owner_user_id == user.id)
        await db.execute(delete(CodeProblemTestCase).where(
            CodeProblemTestCase.problem_id.in_(problem_ids)
        ))
        await db.execute(delete(UserPersonalizedResource).where(
            UserPersonalizedResource.user_id == user.id
        ))
        await db.execute(delete(PersonalizedResourceGeneration).where(
            PersonalizedResourceGeneration.user_id == user.id
        ))
        await db.execute(delete(CodeProblem).where(CodeProblem.owner_user_id == user.id))
        await db.execute(delete(Conversation).where(Conversation.id == conversation.id))
        await db.execute(delete(CourseEnrollment).where(CourseEnrollment.id == enrollment.id))
        await db.execute(delete(Course).where(Course.id == course.id))
        await db.execute(delete(User).where(User.id == user.id))
        await db.commit()


def _choice_request(user_id: str, course_id: str, conversation_id: str):
    return PersonalPracticePrepareRequest(
        user_id=user_id,
        course_id=course_id,
        conversation_id=conversation_id,
        run_id="agent-run-1",
        practice_type="choice_quiz",
        choice_quiz={
            "title": "指针练习",
            "chapter": "指针",
            "knowledge_point": "指针基础",
            "questions": [{
                "type": "single_choice",
                "content": "哪个运算符用于取地址？",
                "options": [{"key": "A", "text": "&"}, {"key": "B", "text": "*"}],
                "answer": "A",
                "explanation": "& 用于取地址。",
                "difficulty": "easy",
            }],
        },
    )


def _code_request(user_id: str, course_id: str, conversation_id: str):
    return PersonalPracticePrepareRequest(
        user_id=user_id,
        course_id=course_id,
        conversation_id=conversation_id,
        run_id="agent-run-code-1",
        practice_type="code_problem",
        code_problem={
            "title": "回显",
            "statement": "读取并输出输入。",
            "language": "python",
            "starter_code": "print(input())",
            "reference_solution": "print(input())",
            "test_inputs": [
                {"stdin": "public\n", "is_public": True},
                {"stdin": "hidden\n", "is_public": False},
            ],
        },
    )


@pytest.mark.asyncio
async def test_prepare_is_idempotent_and_creates_no_visible_question(practice_scope):
    user_id, course_id, conversation_id = practice_scope
    request = _choice_request(user_id, course_id, conversation_id)
    async with async_session_factory() as db:
        first = await prepare_personal_practice_delivery(db, request=request)
        await db.commit()
        second = await prepare_personal_practice_delivery(db, request=request)
        await db.commit()
        count = (await db.execute(select(func.count(QuizQuestion.id)).where(
            QuizQuestion.owner_user_id == user_id
        ))).scalar_one()

    assert first.id == second.id
    assert first.status == "delivery_pending"
    assert first.agent_run_id == "agent-run-1"
    assert count == 0


@pytest.mark.asyncio
async def test_finalize_and_resume_are_idempotent(practice_scope):
    user_id, course_id, conversation_id = practice_scope
    async with async_session_factory() as db:
        generation = await prepare_personal_practice_delivery(
            db,
            request=_choice_request(user_id, course_id, conversation_id),
        )
        await db.commit()
        generation_id = generation.id
        first = await finalize_personal_practice_delivery(
            db,
            generation_id=generation.id,
            user_id=user_id,
            course_id=course_id,
        )
        await db.commit()
        second = await resume_personal_practice_delivery(
            db,
            generation_id=generation.id,
            user_id=user_id,
            course_id=course_id,
        )
        await db.commit()
        count = (await db.execute(select(func.count(QuizQuestion.id)).where(
            QuizQuestion.owner_user_id == user_id
        ))).scalar_one()

    assert first == second
    assert first["status"] == "published"
    assert first["artifact"]["type"] == "QuizCard"
    assert len(first["artifact"]["question_ids"]) == 1
    assert count == 1


@pytest.mark.asyncio
async def test_finalize_failure_rolls_back_and_can_be_resumed(practice_scope, monkeypatch):
    user_id, course_id, conversation_id = practice_scope
    async with async_session_factory() as db:
        generation = await prepare_personal_practice_delivery(
            db,
            request=_choice_request(user_id, course_id, conversation_id),
        )
        await db.commit()
        generation_id = generation.id

        async def fail_after_staging(*_args, **_kwargs):
            db.add(QuizQuestion(
                course_id=course_id,
                chapter="指针",
                knowledge_point="指针",
                type="single_choice",
                source="personalized",
                personalized=True,
                owner_user_id=user_id,
                difficulty="easy",
                content="should rollback",
                options=[],
                correct_answer="A",
            ))
            await db.flush()
            raise RuntimeError("mid_delivery_failure")

        monkeypatch.setattr(
            "app.services.personal_practice_delivery_service.persist_personal_choice_questions",
            fail_after_staging,
        )
        with pytest.raises(RuntimeError, match="mid_delivery_failure"):
            await finalize_personal_practice_delivery(
                db,
                generation_id=generation_id,
                user_id=user_id,
                course_id=course_id,
            )
        await db.rollback()
        await record_personal_practice_delivery_failure(
            db,
            generation_id=generation_id,
            reason="mid_delivery_failure",
        )
        await db.commit()
        count = (await db.execute(select(func.count(QuizQuestion.id)).where(
            QuizQuestion.owner_user_id == user_id
        ))).scalar_one()
        failed = await db.get(PersonalizedResourceGeneration, generation_id)

    assert count == 0
    assert failed.status == "delivery_failed"
    assert failed.delivery_error == "mid_delivery_failure"


@pytest.mark.asyncio
async def test_code_problem_finalize_publishes_problem_cases_and_artifact(practice_scope):
    user_id, course_id, conversation_id = practice_scope

    async def execute_case(_code, _language, stdin):
        return {
            "status": "success",
            "compile_status": "OK",
            "execution": {"stdout": stdin},
        }

    async with async_session_factory() as db:
        generation = await prepare_personal_practice_delivery(
            db,
            request=_code_request(user_id, course_id, conversation_id),
            execute_case=execute_case,
        )
        await db.commit()
        result = await finalize_personal_practice_delivery(
            db,
            generation_id=generation.id,
            user_id=user_id,
            course_id=course_id,
        )
        await db.commit()
        case_count = (await db.execute(select(func.count(CodeProblemTestCase.id)).where(
            CodeProblemTestCase.problem_id == result["problem_id"]
        ))).scalar_one()

    assert result["status"] == "published"
    assert result["artifact"]["type"] == "CodeSandboxCard"
    assert result["artifact"]["problem_id"] == result["problem_id"]
    assert case_count == 2
