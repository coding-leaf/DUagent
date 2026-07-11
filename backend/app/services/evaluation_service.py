import asyncio
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.course import CourseEnrollment
from app.models.others import AsyncTask, Evaluation, LearningActivity, Resource, UserProfile
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.models.user import User
from app.services.agent_client import AgentServiceError, agent_client
from app.services.course_knowledge_graphs import get_active_knowledge_graph
from app.services.resource_scope import resolve_course_resource_scope, resource_scope_clause
from app.services.knowledge_progress import build_node_progress_rows
from app.infrastructure.locks import evaluation_lock

logger = logging.getLogger(__name__)

_empty_table = {"columns": [], "rows": []}


class EvaluationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_evaluation(self, user_id: str, course_id: str) -> dict:
        node_progress = await build_node_progress_rows(user_id, course_id, self.db)
        result = await self.db.execute(
            select(Evaluation)
            .where(
                Evaluation.user_id == user_id,
                Evaluation.course_id == course_id,
                Evaluation.is_deleted == False,
            )
            .order_by(Evaluation.generated_at.desc())
        )
        ev = result.scalars().first()

        if ev is None:
            return {
                "course_id": course_id,
                "progress_table": _empty_table,
                "mastery_table": _empty_table,
                "resource_usage_table": _empty_table,
                "node_progress": node_progress,
                "summary_text": "",
                "generated_at": None,
            }

        progress_table = ev.progress_table or _empty_table
        return {
            "course_id": ev.course_id,
            "progress_table": progress_table,
            "mastery_table": ev.mastery_table or _empty_table,
            "resource_usage_table": ev.resource_usage_table or _empty_table,
            "node_progress": node_progress,
            "summary_text": ev.summary_text or "",
            "generated_at": ev.generated_at.isoformat() if ev.generated_at else None,
        }

    async def _get_processing_refresh_task(self, user_id: str, course_id: str) -> AsyncTask | None:
        result = await self.db.execute(
            select(AsyncTask)
            .where(
                AsyncTask.task_type == "evaluation_refresh",
                AsyncTask.user_id == user_id,
                AsyncTask.course_id == course_id,
                AsyncTask.status == "processing",
                AsyncTask.is_deleted == False,
            )
            .order_by(AsyncTask.create_time.desc(), AsyncTask.id.desc())
        )
        return result.scalars().first()

    async def _assemble_evaluation_payload(self, user_id: str, course_id: str) -> dict:
        payload: dict = {"user_id": user_id, "course_id": course_id}
        resource_scope = await resolve_course_resource_scope(self.db, course_id)
        node_progress = await build_node_progress_rows(user_id, course_id, self.db)

        user_result = await self.db.execute(select(User).where(User.id == user_id, User.is_deleted == False))
        user = user_result.scalar_one_or_none()
        if user:
            payload["student_profile"] = {
                "major": user.major,
                "grade": user.grade,
                "guidance_level": user.guidance_level,
            }

        profile_result = await self.db.execute(
            select(UserProfile)
            .where(
                UserProfile.user_id == user_id,
                UserProfile.course_id == course_id,
                UserProfile.is_deleted == False,
            )
            .order_by(UserProfile.generated_at.desc())
        )
        profile = profile_result.scalars().first()
        if profile:
            payload["profile_context"] = {
                "modal_preference": profile.modal_preference,
                "knowledge_coordinates": profile.knowledge_coordinates,
                "cognitive_blindspots": profile.cognitive_blindspots,
                "drive_intent": profile.drive_intent,
                "discipline_badge": profile.discipline_badge,
                "generated_at": profile.generated_at.isoformat() if profile.generated_at else None,
            }

        kg = await get_active_knowledge_graph(self.db, course_id)
        if kg is None:
            offering_result = await self.db.execute(
                select(CourseOffering).where(
                    CourseOffering.id == course_id,
                    CourseOffering.is_deleted == False,
                )
            )
            offering = offering_result.scalar_one_or_none()
            if offering:
                catalog_result = await self.db.execute(
                    select(CourseCatalog).where(
                        CourseCatalog.id == offering.catalog_id,
                        CourseCatalog.is_deleted == False,
                    )
                )
                catalog = catalog_result.scalar_one_or_none()
                if catalog and catalog.kg_host_course_id:
                    kg = await get_active_knowledge_graph(self.db, catalog.kg_host_course_id)
        payload["kg_context"] = {
            "nodes": kg.nodes if kg and isinstance(kg.nodes, list) else [],
            "node_progress": node_progress,
        }

        activity_result = await self.db.execute(
            select(
                func.count(LearningActivity.id),
                func.coalesce(func.sum(LearningActivity.duration_seconds), 0),
                func.count(func.distinct(func.date(LearningActivity.occurred_at))),
                func.max(LearningActivity.occurred_at),
            ).where(
                LearningActivity.user_id == user_id,
                LearningActivity.course_id == course_id,
                LearningActivity.is_deleted == False,
            )
        )
        activity_count, total_duration, active_days, last_activity_at = activity_result.one()
        payload["learning_activity"] = {
            "total_events": int(activity_count or 0),
            "total_duration_seconds": int(total_duration or 0),
            "active_days": int(active_days or 0),
            "last_activity_at": last_activity_at.isoformat() if last_activity_at else None,
        }

        chapters_r = await self.db.execute(
            select(Resource.chapter, func.count(Resource.id))
            .where(resource_scope_clause(course_id, resource_scope.catalog_id), Resource.is_deleted == False)
            .group_by(Resource.chapter)
        )
        chapter_progress = [
            {"chapter": row[0] or "默认", "completion_rate": 0.0, "time_spent": 0}
            for row in chapters_r
        ]
        payload["learning_progress"] = {"chapter_progress": chapter_progress}

        qz_r = await self.db.execute(
            select(QuizSession)
            .where(QuizSession.user_id == user_id, QuizSession.course_id == course_id, QuizSession.is_deleted == False)
            .order_by(QuizSession.create_time.desc())
            .limit(50)
        )
        quizzes = qz_r.scalars().all()
        quiz_ids = [q.id for q in quizzes]

        kp_stats: dict[str, dict] = {}
        if quiz_ids:
            qa_result = await self.db.execute(
                select(
                    QuizAnswer.is_correct,
                    QuizAnswer.create_time,
                    QuizQuestion.knowledge_point,
                    QuizQuestion.chapter,
                    QuizQuestion.personalized,
                )
                .join(QuizQuestion, QuizAnswer.question_id == QuizQuestion.id)
                .where(
                    QuizAnswer.quiz_id.in_(quiz_ids),
                    QuizAnswer.is_deleted == False,
                    QuizQuestion.is_deleted == False,
                )
                .order_by(QuizAnswer.create_time.asc())
            )
            for row in qa_result.all():
                kp = row.knowledge_point or "未分类"
                if kp not in kp_stats:
                    kp_stats[kp] = {
                        "chapter": row.chapter or "",
                        "total": 0,
                        "correct": 0,
                        "personalized_count": 0,
                        "recent_scores": [],
                    }
                kp_stats[kp]["total"] += 1
                if row.is_correct:
                    kp_stats[kp]["correct"] += 1
                if row.personalized:
                    kp_stats[kp]["personalized_count"] += 1
                if len(kp_stats[kp]["recent_scores"]) < 10:
                    kp_stats[kp]["recent_scores"].append(1 if row.is_correct else 0)

        payload["quiz_results"] = [
            {
                "knowledge_point": kp,
                "chapter": stats["chapter"],
                "score": round(stats["correct"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0.0,
                "total_answers": stats["total"],
                "personalized_count": stats["personalized_count"],
                "recent_trend": round(sum(stats["recent_scores"]) / len(stats["recent_scores"]) * 100, 1)
                                if stats["recent_scores"] else 0.0,
            }
            for kp, stats in kp_stats.items()
        ]

        types = ["document", "mindmap", "reading", "code", "video"]
        by_type: dict = {}
        for t in types:
            c_r = await self.db.execute(
                select(func.count(Resource.id)).where(
                    resource_scope_clause(course_id, resource_scope.catalog_id),
                    Resource.type == t,
                    Resource.is_deleted == False,
                )
            )
            by_type[t] = c_r.scalar() or 0
        payload["resource_usage"] = {"by_type": by_type}

        return payload

    async def refresh_evaluation(self, current_user: User, course_id: str) -> dict:
        if current_user.role == "student":
            check = await self.db.execute(
                select(CourseEnrollment).where(
                    CourseEnrollment.student_id == current_user.id,
                    CourseEnrollment.course_id == course_id,
                    CourseEnrollment.is_deleted == False,
                )
            )
            if not check.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"code": 40300, "message": "未加入该课程", "data": None},
                )

        existing_task = await self._get_processing_refresh_task(current_user.id, course_id)
        if existing_task:
            return {"task_id": existing_task.id}

        payload = await self._assemble_evaluation_payload(current_user.id, course_id)

        task = AsyncTask(
            task_type="evaluation_refresh",
            status="processing",
            user_id=current_user.id,
            course_id=course_id,
        )
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)
        await self.db.commit()

        # Run background evaluation refresh
        asyncio.create_task(run_evaluation_refresh_background(
            task_id=task.id,
            user_id=current_user.id,
            course_id=course_id,
            payload=payload,
        ))

        return {"task_id": task.id}


async def run_evaluation_refresh_background(
    task_id: str,
    user_id: str,
    course_id: str,
    payload: dict,
) -> None:
    """后台异步执行 Agent /evaluation/generate 并写入 Evaluation。"""
    async with async_session_factory() as db:
        try:
            data = await agent_client.post_json("/agent/v2/evaluation/generations", payload)

            async with evaluation_lock(db, user_id, course_id):
                now = datetime.now(timezone.utc)
                node_progress = await build_node_progress_rows(user_id, course_id, db)
                progress_table = data.get("progress_table", _empty_table)
                if not isinstance(progress_table, dict):
                    progress_table = _empty_table
                progress_table = {
                    "columns": progress_table.get("columns") or [],
                    "rows": node_progress,
                }
                old_result = await db.execute(
                    select(Evaluation).where(
                        Evaluation.user_id == user_id,
                        Evaluation.course_id == course_id,
                        Evaluation.is_deleted == False,
                    )
                )
                for old in old_result.scalars().all():
                    old.is_deleted = True

                ev = Evaluation(
                    user_id=user_id,
                    course_id=course_id,
                    progress_table=progress_table,
                    mastery_table=data.get("mastery_table", _empty_table),
                    resource_usage_table=data.get("resource_usage_table", _empty_table),
                    summary_text=data.get("summary_text", ""),
                    generated_at=now,
                )
                db.add(ev)

                await db.execute(
                    update(AsyncTask)
                    .where(AsyncTask.id == task_id)
                    .values(
                        status="completed",
                        result={"updated_at": now.isoformat()},
                        completed_at=now,
                    )
                )
                await db.flush()
            await db.commit()
            logger.info(
                "Evaluation refresh background: completed task_id=%s user_id=%s course_id=%s",
                task_id, user_id, course_id,
            )
        except AgentServiceError as e:
            await db.rollback()
            await db.execute(
                update(AsyncTask)
                .where(AsyncTask.id == task_id)
                .values(
                    status="failed",
                    error_code=str(e.agent_code or "agent_error"),
                    error_message=e.message,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            logger.error(
                "Evaluation refresh background: AgentServiceError task_id=%s user_id=%s course_id=%s "
                "status=%s agent_code=%s message=%s",
                task_id, user_id, course_id, e.status_code, e.agent_code, e.message,
            )
        except Exception as e:
            await db.rollback()
            error_msg = str(e)[:500]
            is_lock_timeout = "GET_LOCK timeout" in str(e)
            await db.execute(
                update(AsyncTask)
                .where(AsyncTask.id == task_id)
                .values(
                    status="failed",
                    error_code="lock_timeout" if is_lock_timeout else "internal_error",
                    error_message=error_msg,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            logger.error(
                "Evaluation refresh background: unexpected error task_id=%s user_id=%s course_id=%s "
                "type=%s message=%s",
                task_id, user_id, course_id, type(e).__name__, error_msg,
            )
