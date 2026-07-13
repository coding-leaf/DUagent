from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.course import CourseEnrollment
from app.models.personalized_resource_generation import PersonalizedResourceGeneration
from app.schemas.code_problem import CodeProblemDraft
from app.schemas.internal_ai_chat import (
    PersonalChoiceQuizDraft,
    PersonalPracticePrepareRequest,
)
from app.services.ai_chat_choice_quiz_service import (
    _resolve_catalog_id,
    persist_personal_choice_questions,
)
from app.services.code_problem_service import (
    _create_problem_from_generation,
    validate_code_problem_draft,
)


class PersonalPracticeDeliveryError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


async def prepare_personal_practice_delivery(
    db: AsyncSession,
    *,
    request: PersonalPracticePrepareRequest,
    execute_case: Callable[[str, str, str], Awaitable[dict[str, Any]]] | None = None,
) -> PersonalizedResourceGeneration:
    await _verify_scope(
        db,
        user_id=request.user_id,
        course_id=request.course_id,
        conversation_id=request.conversation_id,
    )
    normalized, validation_report = await _normalize_draft(request, execute_case=execute_case)
    idempotency_key = _idempotency_key(request, normalized)
    existing = (
        await db.execute(
            select(PersonalizedResourceGeneration).where(
                PersonalizedResourceGeneration.idempotency_key == idempotency_key,
                PersonalizedResourceGeneration.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    generation = PersonalizedResourceGeneration(
        user_id=request.user_id,
        course_id=request.course_id,
        conversation_id=request.conversation_id,
        run_id=request.run_id,
        agent_run_id=request.run_id,
        idempotency_key=idempotency_key,
        source_type="ai_chat",
        goal=str(normalized.get("title") or normalized.get("statement") or "personal practice"),
        resource_type=request.practice_type,
        status="delivery_pending",
        draft=normalized,
        validation_report=validation_report,
        delivery_attempts=0,
    )
    db.add(generation)
    await db.flush()
    return generation


async def finalize_personal_practice_delivery(
    db: AsyncSession,
    *,
    generation_id: str,
    user_id: str,
    course_id: str,
) -> dict[str, Any]:
    generation = await _get_generation(
        db,
        generation_id=generation_id,
        user_id=user_id,
        course_id=course_id,
        for_update=True,
    )
    if generation.status == "published" and generation.artifact_payload:
        return _published_result(generation)
    if generation.status not in {"delivery_pending", "delivery_failed"}:
        raise PersonalPracticeDeliveryError("generation_not_deliverable")

    generation.delivery_attempts = int(generation.delivery_attempts or 0) + 1
    generation.delivery_error = None
    if generation.resource_type == "choice_quiz":
        generation.artifact_payload = await _publish_choice_quiz(db, generation)
    elif generation.resource_type == "code_problem":
        generation.artifact_payload = await _publish_code_problem(db, generation)
    else:
        raise PersonalPracticeDeliveryError("unsupported_practice_type")

    generation.status = "published"
    await db.flush()
    return _published_result(generation)


async def _publish_choice_quiz(
    db: AsyncSession,
    generation: PersonalizedResourceGeneration,
) -> dict[str, Any]:
    draft = PersonalChoiceQuizDraft.model_validate(generation.draft)
    catalog_id = await _resolve_catalog_id(db, generation.course_id)
    question_ids = await persist_personal_choice_questions(
        db,
        owner_user_id=generation.user_id,
        course_id=generation.course_id,
        catalog_id=catalog_id,
        chapter=draft.chapter,
        knowledge_point=draft.knowledge_point,
        source_type="ai_chat",
        questions=draft.questions,
    )
    return {
        "id": generation.id,
        "type": "QuizCard",
        "title": draft.title,
        "course_id": generation.course_id,
        "question_ids": question_ids,
    }


async def _publish_code_problem(
    db: AsyncSession,
    generation: PersonalizedResourceGeneration,
) -> dict[str, Any]:
    created = await _create_problem_from_generation(db, generation)
    return {
        "id": generation.id,
        "type": "CodeSandboxCard",
        "title": created.problem.title,
        "problem_id": created.problem.id,
        "language": created.problem.language,
    }


async def resume_personal_practice_delivery(
    db: AsyncSession,
    *,
    generation_id: str,
    user_id: str,
    course_id: str,
) -> dict[str, Any]:
    return await finalize_personal_practice_delivery(
        db,
        generation_id=generation_id,
        user_id=user_id,
        course_id=course_id,
    )


async def record_personal_practice_delivery_failure(
    db: AsyncSession,
    *,
    generation_id: str,
    reason: str,
) -> None:
    generation = await _get_generation(db, generation_id=generation_id, for_update=True)
    if generation.status == "published":
        return
    generation.status = "delivery_failed"
    generation.delivery_error = reason[:2000]
    generation.delivery_attempts = int(generation.delivery_attempts or 0) + 1
    await db.flush()


async def _normalize_draft(
    request: PersonalPracticePrepareRequest,
    *,
    execute_case: Callable[[str, str, str], Awaitable[dict[str, Any]]] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if request.practice_type == "choice_quiz" and request.choice_quiz:
        return request.choice_quiz.model_dump(mode="json"), {"status": "passed"}
    if request.practice_type == "code_problem" and request.code_problem:
        draft = CodeProblemDraft.model_validate(request.code_problem)
        outputs = await validate_code_problem_draft(draft, execute_case=execute_case)
        public_count = sum(case.is_public for case in draft.test_inputs)
        return {
            **draft.model_dump(mode="json"),
            "expected_outputs": outputs,
        }, {
            "status": "passed",
            "validator": "oj_fixed_cases",
            "public_case_count": public_count,
            "hidden_case_count": len(draft.test_inputs) - public_count,
        }
    raise PersonalPracticeDeliveryError("practice_draft_missing")


def _idempotency_key(request: PersonalPracticePrepareRequest, draft: dict[str, Any]) -> str:
    canonical = json.dumps(
        {
            "user_id": request.user_id,
            "conversation_id": request.conversation_id,
            "run_id": request.run_id,
            "practice_type": request.practice_type,
            "draft": draft,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def _verify_scope(
    db: AsyncSession,
    *,
    user_id: str,
    course_id: str,
    conversation_id: str,
) -> None:
    conversation_id_value = (
        await db.execute(
            select(Conversation.id).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
                Conversation.course_id == course_id,
                Conversation.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if conversation_id_value is None:
        raise PersonalPracticeDeliveryError("conversation_ownership_check_failed")
    enrollment_id = (
        await db.execute(
            select(CourseEnrollment.id).where(
                CourseEnrollment.student_id == user_id,
                CourseEnrollment.course_id == course_id,
                CourseEnrollment.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if enrollment_id is None:
        raise PersonalPracticeDeliveryError("course_enrollment_check_failed")


async def _get_generation(
    db: AsyncSession,
    *,
    generation_id: str,
    user_id: str | None = None,
    course_id: str | None = None,
    for_update: bool = False,
) -> PersonalizedResourceGeneration:
    query = select(PersonalizedResourceGeneration).where(
        PersonalizedResourceGeneration.id == generation_id,
        PersonalizedResourceGeneration.is_deleted.is_(False),
    )
    if user_id is not None:
        query = query.where(PersonalizedResourceGeneration.user_id == user_id)
    if course_id is not None:
        query = query.where(PersonalizedResourceGeneration.course_id == course_id)
    if for_update:
        query = query.with_for_update()
    generation = (await db.execute(query)).scalar_one_or_none()
    if generation is None:
        raise PersonalPracticeDeliveryError("generation_not_found")
    return generation


def _published_result(generation: PersonalizedResourceGeneration) -> dict[str, Any]:
    artifact = generation.artifact_payload or {}
    return {
        "generation_id": generation.id,
        "status": "published",
        "artifact": artifact,
        "delivery_attempts": generation.delivery_attempts,
        **({"question_ids": artifact.get("question_ids", [])} if artifact.get("type") == "QuizCard" else {}),
        **(
            {
                "problem_id": artifact.get("problem_id"),
                "language": artifact.get("language"),
            }
            if artifact.get("type") == "CodeSandboxCard"
            else {}
        ),
    }
