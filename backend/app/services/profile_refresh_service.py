import logging
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from app.db.session import async_session_factory
from app.models.others import AsyncTask
from app.models.user import User
from app.infrastructure.locks import profile_lock, LockAcquisitionTimeout
from app.services.profile_service import ProfileService

logger = logging.getLogger(__name__)

class ProfileRefreshService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_processing_refresh_task(self, user_id: str, course_id: str) -> AsyncTask | None:
        result = await self.db.execute(
            select(AsyncTask)
            .where(
                AsyncTask.task_type == "profile_refresh",
                AsyncTask.user_id == user_id,
                AsyncTask.course_id == course_id,
                AsyncTask.status == "processing",
                AsyncTask.is_deleted == False,
            )
            .order_by(AsyncTask.create_time.desc(), AsyncTask.id.desc())
        )
        return result.scalars().first()

    async def create_refresh_task(self, user_id: str, course_id: str) -> AsyncTask:
        task = AsyncTask(
            task_type="profile_refresh",
            user_id=user_id,
            course_id=course_id,
            status="processing",
        )
        self.db.add(task)
        await self.db.flush()
        return task

async def run_profile_refresh_background(task_id: str, user_id: str, course_id: str) -> None:
    async with async_session_factory() as db:
        try:
            async with profile_lock(db, user_id, course_id) as lock_name:
                now = datetime.now(timezone.utc)
                profile_service = ProfileService(db)
                pf = await profile_service.get_or_create_profile(user_id, course_id)
                await db.flush()
                pf.generated_at = now

                user_result = await db.execute(select(User).where(User.id == user_id))
                user = user_result.scalars().first()
                
                from app.services.knowledge_progress import build_node_progress_rows
                from app.services.profile_rules import compute_profile_fields
                node_progress_rows = await build_node_progress_rows(user_id, course_id, db)
                computed = await compute_profile_fields(user_id, course_id, user, node_progress_rows, db)

                pf.modal_preference = computed["modal_preference"]
                pf.guidance_level_current = user.guidance_level if user else "L2"
                pf.guidance_level_updated_at = now
                pf.knowledge_coordinates = computed["knowledge_coordinates"]
                pf.cognitive_blindspots = computed["cognitive_blindspots"]
                
                drive_intent = {
                    **(pf.drive_intent or {}),
                    "learning_habits": computed["learning_habits"],
                    "knowledge_progress_summary": computed["knowledge_progress_summary"],
                }
                pf.drive_intent = drive_intent
                flag_modified(pf, "drive_intent")
                flag_modified(pf, "modal_preference")
                flag_modified(pf, "knowledge_coordinates")
                flag_modified(pf, "cognitive_blindspots")
                
                pf.discipline_badge = computed["discipline_badge"]

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
                    "Profile refresh background: completed task_id=%s user_id=%s course_id=%s",
                    task_id, user_id, course_id,
                )
        except LockAcquisitionTimeout as e:
            await db.rollback()
            logger.warning(
                "Profile refresh background: lock timeout task_id=%s user_id=%s course_id=%s error=%s",
                task_id, user_id, course_id, str(e),
            )
            await db.execute(
                update(AsyncTask)
                .where(AsyncTask.id == task_id)
                .values(
                    status="failed",
                    result={"error_code": "lock_timeout", "error_message": "并发刷新锁定超时"},
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(
                "Profile refresh background: error task_id=%s user_id=%s course_id=%s error=%s",
                task_id, user_id, course_id, str(e),
                exc_info=True
            )
            await db.execute(
                update(AsyncTask)
                .where(AsyncTask.id == task_id)
                .values(
                    status="failed",
                    result={"error_code": "internal_error", "error_message": str(e)[:500]},
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
