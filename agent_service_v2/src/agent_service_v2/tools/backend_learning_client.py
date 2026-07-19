from __future__ import annotations

from typing import Any

import httpx

from agent_service_v2.agents.model_provider import AgentModelSettings


class BackendLearningClientError(RuntimeError):
    def __init__(
        self,
        reason: str,
        status_code: int | None = None,
        detail_reason: str | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code
        self.detail_reason = detail_reason


def _http_error_reason(status_code: int) -> str:
    if status_code == 422:
        return "backend_validation_error"
    if 400 <= status_code < 500:
        return "backend_rejected"
    return "backend_server_error"


class BackendLearningClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._transport = transport

    async def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {"X-Internal-Agent-Token": self._token}
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise BackendLearningClientError("backend_timeout") from exc
        except httpx.ConnectError as exc:
            raise BackendLearningClientError("backend_unavailable") from exc

        if response.status_code >= 400:
            detail_reason = _response_detail_reason(response)
            raise BackendLearningClientError(
                _http_error_reason(response.status_code),
                status_code=response.status_code,
                detail_reason=detail_reason,
            )

        body = response.json()
        data = body.get("data") if isinstance(body, dict) else None
        return data if isinstance(data, dict) else {}


def _response_detail_reason(response: httpx.Response) -> str | None:
    try:
        body = response.json()
    except ValueError:
        return None
    detail = body.get("detail") if isinstance(body, dict) else None
    data = detail.get("data") if isinstance(detail, dict) else None
    reason = data.get("reason") if isinstance(data, dict) else None
    return reason if isinstance(reason, str) and reason else None


def build_backend_learning_client_from_settings(
    settings: AgentModelSettings | None = None,
) -> BackendLearningClient | None:
    settings = settings or AgentModelSettings()
    if not settings.BACKEND_INTERNAL_BASE_URL or not settings.BACKEND_INTERNAL_AGENT_TOKEN:
        return None
    return BackendLearningClient(
        base_url=settings.BACKEND_INTERNAL_BASE_URL,
        token=settings.BACKEND_INTERNAL_AGENT_TOKEN,
        timeout=settings.BACKEND_INTERNAL_TIMEOUT,
    )
