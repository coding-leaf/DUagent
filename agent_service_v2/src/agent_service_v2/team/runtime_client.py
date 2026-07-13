from __future__ import annotations

import httpx
from collections.abc import Awaitable, Callable
from agentscope.message import UserMsg

from agent_service_v2.agents.model_provider import AgentModelSettings
from agent_service_v2.agents.resource_team_leader import (
    ResourceTeamRequest,
    build_resource_team_leader_prompt,
    build_resource_team_user_message,
)


class TeamRuntimeUnavailable(RuntimeError):
    pass


class OfficialTeamRuntimeClient:
    def __init__(
        self,
        *,
        settings: AgentModelSettings,
        transport: httpx.AsyncBaseTransport,
        grant_permissions: Callable[[str, str, str], Awaitable[None]] | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport
        self.grant_permissions = grant_permissions

    async def start(self, request: ResourceTeamRequest) -> dict:
        self._require_model_settings()
        headers = {"X-User-ID": request.user_id}
        async with httpx.AsyncClient(
            base_url="http://agentscope-runtime",
            transport=self.transport,
            timeout=self.settings.LLM_TIMEOUT,
        ) as client:
            credential = await self._post(
                client,
                "/credential/",
                headers,
                {
                    "data": {
                        "type": "openai_credential",
                        "name": "EDUagent runtime credential",
                        "api_key": self.settings.LLM_API_KEY,
                        "base_url": self.settings.LLM_BASE_URL,
                    }
                },
            )
            agent = await self._post(
                client,
                "/agent/",
                headers,
                {
                    "name": f"resource_leader_{request.task_id}",
                    "system_prompt": build_resource_team_leader_prompt(),
                },
            )
            session = await self._post(
                client,
                "/sessions/",
                headers,
                {
                    "agent_id": agent["agent_id"],
                    "name": f"个性化资源任务 {request.task_id}",
                    "chat_model_config": {
                        "type": "openai_credential",
                        "credential_id": credential["credential_id"],
                        "model": self.settings.LLM_MODEL,
                        "parameters": {"stream": True},
                    },
                },
            )
            if self.grant_permissions:
                await self.grant_permissions(
                    request.user_id,
                    agent["agent_id"],
                    session["session_id"],
                )
            message = UserMsg(
                name="student_request",
                content=build_resource_team_user_message(request),
            )
            await self._post(
                client,
                "/chat/",
                headers,
                {
                    "agent_id": agent["agent_id"],
                    "session_id": session["session_id"],
                    "input": message.model_dump(mode="json"),
                },
            )
        session_id = session["session_id"]
        return {
            "status": "started",
            "agent_id": agent["agent_id"],
            "session_id": session_id,
        }

    async def _post(
        self,
        client: httpx.AsyncClient,
        path: str,
        headers: dict,
        payload: dict,
    ) -> dict:
        response = await client.post(path, headers=headers, json=payload)
        if response.status_code >= 400:
            raise TeamRuntimeUnavailable(f"official_runtime_http_{response.status_code}")
        return response.json()

    def _require_model_settings(self) -> None:
        if not all(
            (
                self.settings.LLM_BASE_URL,
                self.settings.LLM_API_KEY,
                self.settings.LLM_MODEL,
            )
        ):
            raise TeamRuntimeUnavailable("model_not_configured")
