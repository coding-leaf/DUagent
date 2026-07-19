import httpx
import pytest

from app.services.agent_client import AgentClient, AgentServiceError


@pytest.mark.asyncio
async def test_agent_client_downloads_artifact_bytes():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/agent/v2/workbench/artifacts"
        assert request.url.params["filename"] == "lesson.md"
        return httpx.Response(200, content=b"lesson")

    client = AgentClient(transport=httpx.MockTransport(handler))

    assert await client.get_bytes(
        "/agent/v2/workbench/artifacts",
        {"filename": "lesson.md"},
    ) == b"lesson"


@pytest.mark.asyncio
async def test_agent_client_maps_missing_artifact_to_not_found():
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(404, json={"message": "not found"})
    )
    client = AgentClient(transport=transport)

    with pytest.raises(AgentServiceError) as exc_info:
        await client.get_bytes("/agent/v2/workbench/artifacts", {})

    assert exc_info.value.status_code == 404
