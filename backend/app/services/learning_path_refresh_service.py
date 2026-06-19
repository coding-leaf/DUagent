import logging
from datetime import datetime, timezone

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.others import AsyncTask, Evaluation, LearningPath, UserProfile
from app.services.agent_client import AgentServiceError, agent_client
from app.services.course_knowledge_graphs import get_active_knowledge_graph

logger = logging.getLogger(__name__)


class LearningPathRefreshService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def assemble_payload(self, user_id: str, course_id: str) -> dict:
        """组装调用 Agent /learning-path/generate 所需的 payload。"""
        payload: dict = {"user_id": user_id, "course_id": course_id}

        evaluation_result = await self.db.execute(
            select(Evaluation)
            .where(
                Evaluation.user_id == user_id,
                Evaluation.course_id == course_id,
                Evaluation.is_deleted == False,
            )
            .order_by(Evaluation.generated_at.desc())
        )
        evaluation = evaluation_result.scalars().first()
        payload["evaluation"] = {
            "progress_table": evaluation.progress_table,
            "mastery_table": evaluation.mastery_table,
            "summary_text": evaluation.summary_text,
        } if evaluation else {}

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
        payload["profile"] = {
            "modal_preference": profile.modal_preference,
            "guidance_level": profile.guidance_level_current,
            "knowledge_coordinates": profile.knowledge_coordinates,
        } if profile else {}

        knowledge_graph = await get_active_knowledge_graph(self.db, course_id)
        payload["knowledge_graph"] = (
            {"nodes": knowledge_graph.nodes or [], "edges": knowledge_graph.edges or []}
            if knowledge_graph
            else {"nodes": [], "edges": []}
        )
        return payload

    async def create_refresh_task(self, user_id: str, course_id: str) -> AsyncTask:
        task = AsyncTask(
            task_type="learning_path_refresh",
            status="processing",
            user_id=user_id,
            course_id=course_id,
        )
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)
        return task


async def run_learning_path_refresh_background(
    task_id: str,
    user_id: str,
    course_id: str,
    payload: dict,
) -> None:
    """后台异步执行 Agent /learning-path/generate 并写入 LearningPath。"""
    async with async_session_factory() as db:
        try:
            data = await agent_client.post_json("/agent/v1/learning-path/generate", payload)

            lock_name = f"learningpath_{user_id}_{course_id}"
            if db.bind.dialect.name == "sqlite":
                locked = 1
            else:
                lock_result = await db.execute(text("SELECT GET_LOCK(:name, 5)"), {"name": lock_name})
                locked = lock_result.scalar()
            if not locked:
                raise RuntimeError(f"GET_LOCK timeout: {lock_name}")

            try:
                now = datetime.now(timezone.utc)
                old_result = await db.execute(
                    select(LearningPath).where(
                        LearningPath.user_id == user_id,
                        LearningPath.course_id == course_id,
                        LearningPath.is_deleted == False,
                    )
                )
                for old_path in old_result.scalars().all():
                    old_path.is_deleted = True

                current_position = data.get("current_position") or {}
                db.add(
                    LearningPath(
                        user_id=user_id,
                        course_id=course_id,
                        nodes=data.get("nodes", []),
                        edges=data.get("edges", []),
                        current_node_id=current_position.get("node_id", ""),
                        current_node_name=current_position.get("node_name", ""),
                        generated_at=now,
                    )
                )

                await db.execute(
                    update(AsyncTask)
                    .where(AsyncTask.id == task_id)
                    .values(
                        status="completed",
                        result={"updated_at": now.isoformat()},
                        completed_at=now,
                    )
                )
                await db.commit()
                logger.info(
                    "Learning path refresh background: completed task_id=%s user_id=%s course_id=%s",
                    task_id,
                    user_id,
                    course_id,
                )
            finally:
                try:
                    if db.bind.dialect.name != "sqlite":
                        await db.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})
                except Exception:
                    logger.warning("Learning path refresh background: RELEASE_LOCK failed lock_name=%s", lock_name)
        except AgentServiceError as exc:
            await db.rollback()
            await db.execute(
                update(AsyncTask)
                .where(AsyncTask.id == task_id)
                .values(
                    status="failed",
                    error_code=str(exc.agent_code or "agent_error"),
                    error_message=exc.message,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            logger.error(
                "Learning path refresh background: AgentServiceError task_id=%s user_id=%s "
                "course_id=%s status=%s agent_code=%s message=%s",
                task_id,
                user_id,
                course_id,
                exc.status_code,
                exc.agent_code,
                exc.message,
            )
        except Exception as exc:
            await db.rollback()
            error_message = str(exc)[:500]
            await db.execute(
                update(AsyncTask)
                .where(AsyncTask.id == task_id)
                .values(
                    status="failed",
                    error_code="lock_timeout" if "GET_LOCK timeout" in str(exc) else "internal_error",
                    error_message=error_message,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            logger.error(
                "Learning path refresh background: unexpected error task_id=%s user_id=%s "
                "course_id=%s type=%s message=%s",
                task_id,
                user_id,
                course_id,
                type(exc).__name__,
                error_message,
            )
