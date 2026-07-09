import asyncio

import httpx
import pytest

from agent_service_v2.agents.model_provider import AgentModelSettings
from agent_service_v2.tools.backend_learning_client import (
    BackendLearningClient,
    BackendLearningClientError,
    build_backend_learning_client_from_settings,
)


class StubTransport(httpx.AsyncBaseTransport):
    def __init__(self):
        self.requests = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(
            200,
            json={"code": 200, "message": "success", "data": {"status": "available"}},
            request=request,
        )


def test_backend_learning_client_posts_token_and_returns_data():
    transport = StubTransport()
    client = BackendLearningClient(
        base_url="http://backend",
        token="secret",
        timeout=5.0,
        transport=transport,
    )

    data = asyncio.run(client.post_json("/internal/ai-chat/learning-progress", {"user_id": "u1"}))

    assert data == {"status": "available"}
    request = transport.requests[0]
    assert request.headers["X-Internal-Agent-Token"] == "secret"
    assert str(request.url) == "http://backend/internal/ai-chat/learning-progress"


def test_backend_learning_client_raises_structured_error_on_http_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "forbidden"}, request=request)

    client = BackendLearningClient(
        base_url="http://backend",
        token="secret",
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(BackendLearningClientError) as exc:
        asyncio.run(client.post_json("/internal/ai-chat/learning-progress", {}))

    assert exc.value.reason == "backend_http_error"
    assert exc.value.status_code == 403


def test_build_backend_learning_client_from_settings_requires_base_url_and_token():
    missing = AgentModelSettings(
        BACKEND_INTERNAL_BASE_URL="",
        BACKEND_INTERNAL_AGENT_TOKEN="",
    )
    assert build_backend_learning_client_from_settings(missing) is None

    configured = AgentModelSettings(
        BACKEND_INTERNAL_BASE_URL="http://backend",
        BACKEND_INTERNAL_AGENT_TOKEN="secret",
        BACKEND_INTERNAL_TIMEOUT=3.0,
    )
    client = build_backend_learning_client_from_settings(configured)
    assert isinstance(client, BackendLearningClient)
    assert client.base_url == "http://backend"
