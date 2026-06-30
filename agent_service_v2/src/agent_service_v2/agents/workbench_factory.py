from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agentscope.agent import Agent, ContextConfig, ReActConfig
from agentscope.tool import Toolkit
from agentscope.workspace import LocalWorkspace

from agent_service_v2.agents.prompts import WORKBENCH_SYSTEM_PROMPT
from agent_service_v2.tools.workbench_toolkit import build_workbench_tool_groups


class MissingModelConfigError(RuntimeError):
    pass


class WorkbenchAgentFactory:
    def __init__(self, model_provider: Callable[[], Any]) -> None:
        self._model_provider = model_provider

    def create_agent(
        self,
        *,
        user_id: str,
        course_id: str | None,
        workspace: LocalWorkspace,
    ) -> Agent:
        model = self._model_provider()
        if model is None:
            raise MissingModelConfigError("model_not_configured")

        toolkit = Toolkit(
            tool_groups=build_workbench_tool_groups(
                memory_tools=[],
                rag_tools=[],
            )
        )
        return Agent(
            name=_agent_name(course_id),
            system_prompt=_system_prompt(user_id=user_id, course_id=course_id),
            model=model,
            toolkit=toolkit,
            offloader=workspace,
            context_config=ContextConfig(tool_result_limit=20000),
            react_config=ReActConfig(max_iters=8),
        )


def _agent_name(course_id: str | None) -> str:
    return f"edu_ai_chat_workbench:{course_id or 'global'}"


def _system_prompt(*, user_id: str, course_id: str | None) -> str:
    return (
        f"{WORKBENCH_SYSTEM_PROMPT}\n"
        f"Current user_id: {user_id}\n"
        f"Current course_id: {course_id or 'global'}\n"
    )
