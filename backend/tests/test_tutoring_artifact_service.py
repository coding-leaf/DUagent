from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.tutoring_artifact_service import TutoringArtifactService


@pytest.mark.asyncio
async def test_artifact_service_reads_file_through_agent_http_client():
    db = SimpleNamespace(
        scalar=AsyncMock(return_value=SimpleNamespace(course_id="course-1"))
    )
    client = SimpleNamespace(get_bytes=AsyncMock(return_value=b"content"))

    artifact = await TutoringArtifactService(db, client).download(
        user_id="user-1",
        conversation_id="conv-1",
        filename="lesson.md",
    )

    client.get_bytes.assert_awaited_once_with(
        "/agent/v2/workbench/artifacts",
        {
            "user_id": "user-1",
            "course_id": "course-1",
            "conversation_id": "conv-1",
            "filename": "lesson.md",
        },
    )
    assert artifact.content == b"content"
    assert artifact.media_type == "text/markdown"
