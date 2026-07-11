from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_internal_personalized_draft_requires_agent_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/internal/personalized-resources/drafts",
            json={
                "user_id": "u1",
                "course_id": "c1",
                "source_type": "manual",
                "goal": "复习指针",
                "resource_type": "personal_lesson",
                "draft": {"title": "指针", "content": "# 指针"},
            },
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_internal_personalized_publish_delegates_owner_scoped_service():
    resource = MagicMock(id="resource-1", type="personal_lesson")
    with patch(
        "app.api.v1.internal_personalized_resources.settings.INTERNAL_AGENT_TOKEN",
        "secret",
    ), patch(
        "app.api.v1.internal_personalized_resources.PersonalizedResourceGenerationService.publish",
        new_callable=AsyncMock,
        return_value=resource,
    ) as publish:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/internal/personalized-resources/generation-1/publish",
                headers={"X-Internal-Agent-Token": "secret"},
                json={"user_id": "u1", "course_id": "c1"},
            )

    assert response.status_code == 200
    assert response.json()["data"]["resource_id"] == "resource-1"
    assert publish.await_args.kwargs == {"user_id": "u1", "course_id": "c1"}
