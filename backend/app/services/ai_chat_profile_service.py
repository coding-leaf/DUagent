from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.infrastructure.locks import profile_lock
from app.models.others import OperationLog, UserProfile
from app.services.profile_presenters import DEFAULT_PROFILE, profile_data
from app.services.profile_service import ProfileService


_PREFERENCE_FIELDS = {
    "text_reading": "text_analysis",
    "chart_logic": "chart_logic",
    "code_practice": "code_practice",
    "practice_reinforcement": "formula_derivation",
}


async def read_dialogue_learner_profile(
    db: AsyncSession, *, user_id: str, course_id: str
) -> dict:
    result = await db.execute(
        select(UserProfile).where(
            UserProfile.user_id == user_id,
            UserProfile.course_id == course_id,
            UserProfile.is_deleted.is_(False),
        )
    )
    return profile_data(result.scalars().first(), course_id)


async def update_dialogue_learner_profile(
    db: AsyncSession,
    *,
    user_id: str,
    course_id: str,
    conversation_id: str,
    run_id: str,
    learning_goal: str | None = None,
    resource_preferences: list[str] | None = None,
    guidance_level: str | None = None,
    custom_instruction: str | None = None,
    learning_habits: dict[str, str] | None = None,
) -> dict:
    del conversation_id  # Conversation text and identifiers are deliberately absent from audit data.
    async with profile_lock(db, user_id, course_id):
        profile = await ProfileService(db).get_or_create_profile(user_id, course_id)
        updated_fields: list[str] = []
        drive_intent = dict(profile.drive_intent or DEFAULT_PROFILE["drive_intent"])

        if learning_goal is not None and drive_intent.get("learning_goal") != learning_goal:
            drive_intent["type"] = learning_goal
            drive_intent["learning_goal"] = learning_goal
            drive_intent["source"] = "profile_dialogue"
            updated_fields.append("learning_goal")
        if custom_instruction is not None and drive_intent.get("custom_instruction") != custom_instruction:
            drive_intent["custom_instruction"] = custom_instruction
            updated_fields.append("custom_instruction")
        if learning_habits is not None:
            merged_habits = dict(drive_intent.get("learning_habits") or {})
            changed = any(merged_habits.get(key) != value for key, value in learning_habits.items())
            if changed:
                merged_habits.update(learning_habits)
                drive_intent["learning_habits"] = merged_habits
                updated_fields.append("learning_habits")
        if any(field in updated_fields for field in ("learning_goal", "custom_instruction", "learning_habits")):
            profile.drive_intent = drive_intent
            flag_modified(profile, "drive_intent")

        if resource_preferences is not None:
            modal = dict(profile.modal_preference or DEFAULT_PROFILE["modal_preference"])
            selected = set(resource_preferences)
            next_values = {
                storage_key: 100 if preference in selected else 0
                for preference, storage_key in _PREFERENCE_FIELDS.items()
            }
            if any(modal.get(key) != value for key, value in next_values.items()):
                modal.update(next_values)
                profile.modal_preference = modal
                flag_modified(profile, "modal_preference")
                updated_fields.append("resource_preferences")

        if guidance_level is not None and profile.guidance_level_current != guidance_level:
            profile.guidance_level_current = guidance_level
            profile.guidance_level_updated_at = datetime.now(timezone.utc)
            updated_fields.append("guidance_level")

        if not updated_fields:
            return {"outcome": "neutral", "result": "unchanged", "updated_fields": []}

        profile.generated_at = datetime.now(timezone.utc)
        db.add(
            OperationLog(
                event_type="profile_dialogue_update",
                user_id=user_id,
                description="AI Chat 更新课程学习画像",
                detail={
                    "fields": updated_fields,
                    "run_id": run_id,
                    "result": "updated",
                },
            )
        )
        await db.flush()
        return {"outcome": "success", "result": "updated", "updated_fields": updated_fields}
