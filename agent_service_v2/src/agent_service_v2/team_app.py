from __future__ import annotations

from pathlib import Path

from agentscope.app import SubAgentTemplate, create_app
from agentscope.app.message_bus import InMemoryMessageBus, MessageBus
from agentscope.tool import FunctionTool

from agent_service_v2.agents.model_provider import AgentModelSettings
from agent_service_v2.agents.team_templates import build_resource_team_templates
from agent_service_v2.team.storage import build_team_storage
from agent_service_v2.team.workspaces import build_team_workspace_manager
from agent_service_v2.tools.backend_learning_client import (
    build_backend_learning_client_from_settings,
)
from agent_service_v2.tools.rag import retrieve_course_context
from agent_service_v2.tools.resource_drafts import build_resource_draft_tools
from agent_service_v2.tools.resource_reviews import build_resource_review_tools


def build_team_app(
    *,
    templates: list[SubAgentTemplate] | None = None,
    message_bus: MessageBus | None = None,
    workspace_root: str | Path | None = None,
):
    root = workspace_root or Path("workspaces/team_runtime")
    settings = AgentModelSettings()
    client = build_backend_learning_client_from_settings(settings)

    async def extra_agent_tools(_user_id: str, _agent_id: str, _session_id: str):
        if client is None:
            return []

        async def retrieve_course_context_tool(
            query: str, course_id: str, limit: int = 4
        ) -> dict:
            return await retrieve_course_context(
                query=query,
                course_id=course_id,
                limit=limit,
                settings=settings,
            )

        return [
            *build_resource_draft_tools(client),
            *build_resource_review_tools(client),
            FunctionTool(
                retrieve_course_context_tool,
                name="retrieve_course_context_tool",
                description="Retrieve grounded course excerpts for one personalized-resource goal.",
                is_read_only=True,
            ),
        ]

    return create_app(
        storage=build_team_storage(),
        message_bus=message_bus or InMemoryMessageBus(),
        workspace_manager=build_team_workspace_manager(root),
        custom_subagent_templates=templates or build_resource_team_templates(),
        extra_agent_tools=extra_agent_tools,
        enable_index_worker=False,
        title="EDUagent Personalized Resource Team",
        version="2.0.3",
    )


team_runtime_app = build_team_app()
