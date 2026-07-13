from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.others import AsyncTask, Resource, UserPersonalizedResource
from app.models.personalized_resource_generation import PersonalizedResourceGeneration
from app.services.content_safety import ensure_student_visible_content_safe


_ALLOWED_TRANSITIONS = {
    "drafted": {"validated", "failed"},
    "validated": {"approved", "approved_with_advice", "rejected", "failed"},
    "approved": {"published", "failed"},
    "approved_with_advice": {"published", "failed"},
    "rejected": set(),
    "published": set(),
    "failed": set(),
}


class ResourcePublicationError(ValueError):
    pass


def validate_generation_transition(current: str, target: str) -> None:
    if target not in _ALLOWED_TRANSITIONS.get(current, set()):
        raise ResourcePublicationError(f"invalid_transition:{current}->{target}")


class PersonalizedResourceGenerationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_draft(
        self,
        *,
        user_id: str,
        course_id: str,
        source_type: str,
        goal: str,
        resource_type: str,
        draft: dict,
        conversation_id: str | None = None,
        run_id: str | None = None,
    ) -> PersonalizedResourceGeneration:
        generation = PersonalizedResourceGeneration(
            user_id=user_id,
            course_id=course_id,
            source_type=source_type,
            goal=goal,
            resource_type=resource_type,
            draft=draft,
            conversation_id=conversation_id,
            run_id=run_id,
            status="drafted",
        )
        self.db.add(generation)
        await self.db.flush()
        await self.db.refresh(generation)
        return generation

    async def record_validation(
        self,
        generation_id: str,
        report: dict,
        *,
        user_id: str | None = None,
        course_id: str | None = None,
    ):
        generation = await self._get(
            generation_id, user_id=user_id, course_id=course_id
        )
        target = "validated" if report.get("status") == "passed" else "failed"
        validate_generation_transition(generation.status, target)
        generation.validation_report = report
        generation.status = target
        await self.db.flush()
        return generation

    async def record_review(
        self,
        generation_id: str,
        report: dict,
        *,
        user_id: str | None = None,
        course_id: str | None = None,
    ):
        generation = await self._get(
            generation_id, user_id=user_id, course_id=course_id
        )
        decision = str(report.get("decision") or "")
        validate_generation_transition(generation.status, decision)
        generation.review_decision = decision
        generation.review_report = report
        generation.status = decision
        await self.db.flush()
        return generation

    async def publish(
        self,
        generation_id: str,
        *,
        user_id: str | None = None,
        course_id: str | None = None,
    ) -> Resource:
        generation = await self._get(
            generation_id,
            for_update=True,
            user_id=user_id,
            course_id=course_id,
        )
        if (generation.validation_report or {}).get("status") != "passed":
            raise ResourcePublicationError("validation_required")
        if generation.review_decision not in {"approved", "approved_with_advice"}:
            raise ResourcePublicationError("review_required")
        validate_generation_transition(generation.status, "published")

        draft = generation.draft
        ensure_student_visible_content_safe({
            key: draft.get(key) for key in (
                "title", "description", "content", "chapter", "knowledge_point", "tags"
            )
        })
        resource = Resource(
            course_id=generation.course_id,
            title=str(draft.get("title") or "个性化学习资料"),
            type=generation.resource_type,
            description=str(draft.get("description") or ""),
            content=str(draft.get("content") or ""),
            chapter=str(draft.get("chapter") or ""),
            knowledge_point=str(draft.get("knowledge_point") or ""),
            tags=draft.get("tags") or [],
            url="",
            create_by=generation.user_id,
        )
        self.db.add(resource)
        await self.db.flush()
        await link_published_generation(
            self.db,
            generation=generation,
            resource_id=resource.id,
        )
        generation.published_resource_id = resource.id
        generation.status = "published"
        await self.db.flush()
        return resource

    async def _get(
        self,
        generation_id: str,
        *,
        for_update: bool = False,
        user_id: str | None = None,
        course_id: str | None = None,
    ):
        query = select(PersonalizedResourceGeneration).where(
            PersonalizedResourceGeneration.id == generation_id,
            PersonalizedResourceGeneration.is_deleted == False,
        )
        if user_id is not None:
            query = query.where(PersonalizedResourceGeneration.user_id == user_id)
        if course_id is not None:
            query = query.where(PersonalizedResourceGeneration.course_id == course_id)
        if for_update:
            query = query.with_for_update()
        result = await self.db.execute(query)
        generation = result.scalar_one_or_none()
        if generation is None:
            raise ResourcePublicationError("generation_not_found")
        return generation


async def link_published_generation(
    db: AsyncSession,
    *,
    generation: PersonalizedResourceGeneration,
    resource_id: str | None = None,
    code_problem_id: str | None = None,
) -> UserPersonalizedResource:
    task = None
    if generation.run_id:
        task_result = await db.execute(
            select(AsyncTask).where(AsyncTask.id == generation.run_id).with_for_update()
        )
        task = task_result.scalar_one_or_none()
    task_id = task.id if task is not None else None

    link = None
    if task_id:
        result = await db.execute(
            select(UserPersonalizedResource).where(
                UserPersonalizedResource.task_id == task_id,
                UserPersonalizedResource.user_id == generation.user_id,
                UserPersonalizedResource.course_id == generation.course_id,
                UserPersonalizedResource.is_deleted == False,
            )
        )
        link = result.scalar_one_or_none()
    if link is None:
        link = UserPersonalizedResource(
            user_id=generation.user_id,
            course_id=generation.course_id,
            source_type=generation.source_type,
            task_id=task_id,
        )
        db.add(link)
    link.resource_id = resource_id
    link.code_problem_id = code_problem_id

    if task:
        task.status = "completed"
        task.progress = 100
        task.completed_at = datetime.now(timezone.utc)
    return link
