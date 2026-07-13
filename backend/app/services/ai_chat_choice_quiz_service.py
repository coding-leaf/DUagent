import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CourseOffering
from app.models.conversation import Conversation
from app.models.course import CourseEnrollment
from app.models.others import UserPersonalizedResource
from app.models.quiz import QuizQuestion
from app.schemas.internal_ai_chat import ChoiceQuestionDraft


class ChoiceQuizValidationError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


async def create_personal_choice_quiz_from_ai_chat(
    db: AsyncSession,
    *,
    owner_user_id: str,
    course_id: str,
    conversation_id: str,
    chapter: str,
    knowledge_point: str,
    questions: list[ChoiceQuestionDraft],
) -> list[str]:
    await _verify_ai_chat_quiz_scope(
        db,
        owner_user_id=owner_user_id,
        course_id=course_id,
        conversation_id=conversation_id,
    )
    catalog_id = await _resolve_catalog_id(db, course_id)
    return await persist_personal_choice_questions(
        db,
        owner_user_id=owner_user_id,
        course_id=course_id,
        catalog_id=catalog_id,
        chapter=chapter,
        knowledge_point=knowledge_point,
        source_type="ai_chat",
        questions=questions,
    )


async def persist_personal_choice_questions(
    db: AsyncSession,
    *,
    owner_user_id: str,
    course_id: str,
    catalog_id: str | None,
    chapter: str,
    knowledge_point: str,
    source_type: str,
    questions: list[ChoiceQuestionDraft],
) -> list[str]:
    question_ids: list[str] = []
    for draft in questions:
        answer = (
            json.dumps(draft.answer, ensure_ascii=False)
            if isinstance(draft.answer, list)
            else draft.answer
        )
        question = QuizQuestion(
            course_id=course_id,
            catalog_id=catalog_id,
            chapter=chapter,
            knowledge_point=knowledge_point,
            type=draft.type,
            source="personalized",
            personalized=True,
            owner_user_id=owner_user_id,
            difficulty=draft.difficulty,
            content=draft.content,
            options=[option.model_dump() for option in draft.options],
            correct_answer=answer,
            explanation=draft.explanation,
            create_by=owner_user_id,
        )
        db.add(question)
        await db.flush()
        db.add(
            UserPersonalizedResource(
                user_id=owner_user_id,
                course_id=course_id,
                question_id=question.id,
                source_type=source_type,
            )
        )
        question_ids.append(question.id)
    await db.flush()
    return question_ids


async def _verify_ai_chat_quiz_scope(
    db: AsyncSession,
    *,
    owner_user_id: str,
    course_id: str,
    conversation_id: str,
) -> None:
    conversation_result = await db.execute(
        select(Conversation.id).where(
            Conversation.id == conversation_id,
            Conversation.user_id == owner_user_id,
            Conversation.course_id == course_id,
            Conversation.is_deleted.is_(False),
        )
    )
    if conversation_result.scalar_one_or_none() is None:
        raise ChoiceQuizValidationError("conversation_ownership_check_failed")
    enrollment_result = await db.execute(
        select(CourseEnrollment.id).where(
            CourseEnrollment.student_id == owner_user_id,
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.is_deleted.is_(False),
        )
    )
    if enrollment_result.scalar_one_or_none() is None:
        raise ChoiceQuizValidationError("course_enrollment_check_failed")


async def _resolve_catalog_id(db: AsyncSession, course_id: str) -> str | None:
    result = await db.execute(
        select(CourseOffering.catalog_id).where(
            CourseOffering.id == course_id,
            CourseOffering.is_deleted.is_(False),
        )
    )
    return result.scalar_one_or_none()
