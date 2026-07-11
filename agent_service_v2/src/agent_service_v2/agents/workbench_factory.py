from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agentscope.agent import Agent, ContextConfig, ReActConfig
from agentscope.state import AgentState
from agentscope.tool import Toolkit
from agentscope.workspace import LocalWorkspace

from agent_service_v2.agents.permissions import build_workbench_permission_context
from agent_service_v2.agents.prompts import WORKBENCH_SYSTEM_PROMPT
from agent_service_v2.observability.agent_middleware import AgentRunLoggingMiddleware
from agent_service_v2.observability.logging import LogSink
from agent_service_v2.tools.backend_learning_client import build_backend_learning_client_from_settings
from agent_service_v2.tools.learning_progress import build_learning_progress_tools
from agent_service_v2.tools.oj_execution import build_oj_execution_tools
from agent_service_v2.tools.personal_code_problem import build_personal_code_problem_tools
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
        run_id: str | None = None,
        conversation_id: str | None = None,
        log_sink: LogSink | None = None,
    ) -> Agent:
        model = self._model_provider()
        if model is None:
            raise MissingModelConfigError("model_not_configured")
        if run_id is None:
            raise ValueError("run_id is required for workbench artifact tools")

        learning_client = build_backend_learning_client_from_settings()
        learning_progress_tools = build_learning_progress_tools(
            client=learning_client,
            user_id=user_id,
            course_id=course_id,
        )
        oj_execution_tools = build_oj_execution_tools(
            client=learning_client,
        )
        personal_code_problem_tools = build_personal_code_problem_tools(
            client=learning_client,
            user_id=user_id,
            course_id=course_id,
            conversation_id=conversation_id,
            run_id=run_id,
            workspace=workspace,
        )
        toolkit = Toolkit(
            tool_groups=build_workbench_tool_groups(
                memory_tools=[],
                rag_tools=[],
                learning_progress_tools=learning_progress_tools,
                oj_execution_tools=oj_execution_tools,
                personal_code_problem_tools=personal_code_problem_tools,
                workspace=workspace,
                run_id=run_id,
            )
        )
        middlewares = []
        if run_id and log_sink:
            middlewares.append(
                AgentRunLoggingMiddleware(
                    run_id=run_id,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    course_id=course_id,
                    sink=log_sink,
                )
            )

        return Agent(
            name=_agent_name(course_id),
            system_prompt=_system_prompt(user_id=user_id, course_id=course_id),
            model=model,
            toolkit=toolkit,
            middlewares=middlewares,
            state=AgentState(permission_context=build_workbench_permission_context()),
            offloader=workspace,
            context_config=ContextConfig(tool_result_limit=20000),
            react_config=ReActConfig(max_iters=12),
        )


def _agent_name(course_id: str | None) -> str:
    return f"edu_ai_chat_workbench:{course_id or 'global'}"


def _system_prompt(*, user_id: str, course_id: str | None) -> str:
    return (
        f"{WORKBENCH_SYSTEM_PROMPT}\n"
        f"Current user_id: {user_id}\n"
        f"Current course_id: {course_id or 'global'}\n"
    )
