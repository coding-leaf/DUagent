from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai_chat_profile_service import update_dialogue_learner_profile


@asynccontextmanager
async def _lock(*_args, **_kwargs):
    yield


def _profile():
    return SimpleNamespace(
        drive_intent={"learning_goal": "casual", "learning_habits": {}},
        modal_preference={},
        guidance_level_current="L2",
        guidance_level_updated_at=None,
        generated_at=None,
    )


@pytest.mark.asyncio
async def test_dialogue_profile_update_persists_explicit_facts_and_safe_audit():
    db = MagicMock()
    db.flush = AsyncMock()
    profile = _profile()
    with patch("app.services.ai_chat_profile_service.profile_lock", _lock), patch(
        "app.services.ai_chat_profile_service.flag_modified"
    ), patch(
        "app.services.ai_chat_profile_service.ProfileService.get_or_create_profile",
        new_callable=AsyncMock,
        return_value=profile,
    ):
        result = await update_dialogue_learner_profile(
            db,
            user_id="u1",
            course_id="c1",
            conversation_id="conv-secret",
            run_id="run1",
            learning_goal="通过期末考试",
            resource_preferences=["text_reading", "practice_reinforcement"],
            learning_habits={"study_time": "工作日晚上"},
        )

    assert result["outcome"] == "success"
    audit = db.add.call_args.args[0]
    assert audit.detail == {
        "fields": ["learning_goal", "learning_habits", "resource_preferences"],
        "run_id": "run1",
        "result": "updated",
    }
    assert "通过期末考试" not in str(audit.detail)
    assert "conv-secret" not in str(audit.detail)


@pytest.mark.asyncio
async def test_dialogue_profile_duplicate_is_neutral_without_audit():
    db = MagicMock()
    db.flush = AsyncMock()
    profile = _profile()
    profile.drive_intent = {"learning_goal": "通过期末考试", "type": "通过期末考试"}
    with patch("app.services.ai_chat_profile_service.profile_lock", _lock), patch(
        "app.services.ai_chat_profile_service.ProfileService.get_or_create_profile",
        new_callable=AsyncMock,
        return_value=profile,
    ):
        result = await update_dialogue_learner_profile(
            db,
            user_id="u1",
            course_id="c1",
            conversation_id="conv1",
            run_id="run1",
            learning_goal="通过期末考试",
        )

    assert result == {"outcome": "neutral", "result": "unchanged", "updated_fields": []}
    db.add.assert_not_called()
    db.flush.assert_not_awaited()
