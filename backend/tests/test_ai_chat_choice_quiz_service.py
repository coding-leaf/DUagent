import pytest
from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.conversation import Conversation
from app.models.course import Course, CourseEnrollment
from app.models.others import UserPersonalizedResource
from app.models.quiz import QuizQuestion
from app.models.user import User
from app.schemas.internal_ai_chat import ChoiceQuestionDraft
from app.services.ai_chat_choice_quiz_service import create_personal_choice_quiz_from_ai_chat


@pytest.mark.asyncio
async def test_choice_quiz_service_persists_private_questions_and_resource_links():
    async with async_session_factory() as db:
        teacher = User(
            username="choice_teacher",
            email="choice_teacher@example.com",
            password_hash="test",
            role="teacher",
        )
        student = User(
            username="choice_student",
            email="choice_student@example.com",
            password_hash="test",
            role="student",
        )
        db.add_all([teacher, student])
        await db.flush()
        course = Course(
            name="C语言",
            course_code="CHOICE101",
            teacher_id=teacher.id,
        )
        db.add(course)
        await db.flush()
        db.add(CourseEnrollment(student_id=student.id, course_id=course.id))
        conversation = Conversation(
            user_id=student.id,
            course_id=course.id,
            scope="course",
            title="选择题练习",
        )
        db.add(conversation)
        await db.flush()

        question_ids = await create_personal_choice_quiz_from_ai_chat(
            db,
            owner_user_id=student.id,
            course_id=course.id,
            conversation_id=conversation.id,
            chapter="指针",
            knowledge_point="指针基础",
            questions=[
                ChoiceQuestionDraft.model_validate(
                    {
                        "type": "multi_choice",
                        "content": "以下哪些属于合法指针操作？",
                        "options": [
                            {"key": "A", "text": "取地址"},
                            {"key": "B", "text": "解引用"},
                            {"key": "C", "text": "越界访问"},
                        ],
                        "answer": ["A", "B"],
                        "explanation": "取地址和解引用属于基本指针操作。",
                        "difficulty": "medium",
                    }
                )
            ],
        )
        await db.commit()

        question = (
            await db.execute(select(QuizQuestion).where(QuizQuestion.id == question_ids[0]))
        ).scalar_one()
        resource_link = (
            await db.execute(
                select(UserPersonalizedResource).where(
                    UserPersonalizedResource.question_id == question.id
                )
            )
        ).scalar_one()

    assert question.type == "multi_choice"
    assert question.owner_user_id == student.id
    assert question.correct_answer == '["A", "B"]'
    assert resource_link.user_id == student.id
    assert resource_link.course_id == course.id
    assert resource_link.source_type == "ai_chat"
