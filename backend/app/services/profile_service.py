from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.others import UserProfile
from app.services.profile_presenters import _default_profile
from app.infrastructure.locks import profile_lock

class ProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_profile(self, user_id: str, course_id: str) -> UserProfile:
        result = await self.db.execute(
            select(UserProfile)
            .where(
                UserProfile.user_id == user_id,
                UserProfile.course_id == course_id,
            )
            .order_by(UserProfile.generated_at.desc())
        )
        pf = result.scalars().first()
        if pf:
            if pf.is_deleted:
                pf.is_deleted = False
            return pf

        pf = UserProfile(user_id=user_id, course_id=course_id)
        self.db.add(pf)
        return pf

    async def initialize_profile(self, user_id: str, course_id: str, answers: dict) -> UserProfile:
        async with profile_lock(self.db, user_id, course_id):
            profile = await self.get_or_create_profile(user_id, course_id)
            now = datetime.now(timezone.utc)
            
            profile.guidance_level_current = answers.get("guidance_level", "L2")
            profile.guidance_level_updated_at = now
            profile.modal_preference = {k: 60 for k in (answers.get("modal_preference") or ["text"])}
            profile.drive_intent = {"type": answers.get("learning_goal", "casual"), "intensity": 50}
            profile.knowledge_coordinates = [{"name": "入门", "status": "learning", "mastered_at": None}]
            profile.generated_at = now
            
            await self.db.flush()
            await self.db.refresh(profile)
            return profile

    async def update_learning_goal(self, user_id: str, course_id: str, goal: str) -> UserProfile:
        async with profile_lock(self.db, user_id, course_id):
            pf = await self.get_or_create_profile(user_id, course_id)
            drive_intent = dict(pf.drive_intent or _default_profile["drive_intent"])
            drive_intent["learning_goal"] = goal
            pf.drive_intent = drive_intent
            pf.generated_at = datetime.now(timezone.utc)
            await self.db.flush()
            return pf

    async def update_custom_instruction(self, user_id: str, course_id: str, instruction: str) -> UserProfile:
        async with profile_lock(self.db, user_id, course_id):
            pf = await self.get_or_create_profile(user_id, course_id)
            drive_intent = dict(pf.drive_intent or _default_profile["drive_intent"])
            drive_intent["custom_instruction"] = instruction
            pf.drive_intent = drive_intent
            pf.generated_at = datetime.now(timezone.utc)
            await self.db.flush()
            return pf
