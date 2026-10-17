from __future__ import annotations

from agentscope.agent import Agent, ContextConfig, ReActConfig
from agentscope.state import AgentState
from agentscope.tool import Toolkit
from agentscope.workspace import LocalWorkspace

from agent_service_v2.agents.permissions import build_workbench_permission_context


class WorkbenchReActAgent(Agent):
    """The single teaching agent used by `/agent/v2/workbench/chat`.

    It is a plain AgentScope ReAct agent: business capabilities are mounted
    through the native `Toolkit` (knowledge retrieval, OJ execution, practice
    publishing, workspace artifacts, long-term memory), so tool failures are
    converted by the framework into `ToolResultState.ERROR` observations
    instead of escaping into the SSE response stream.

    No sub-agent team, ASGI sub-application or HTTP loopback is involved.
    """

    @classmethod
    def build(
        cls,
        *,
        name: str,
        system_prompt: str,
        model,
        toolkit: Toolkit,
        workspace: LocalWorkspace,
        middlewares: list | None = None,
        max_iters: int = 20,
        tool_result_limit: int = 20000,
    ) -> "WorkbenchReActAgent":
        return cls(
            name=name,
            system_prompt=system_prompt,
            model=model,
            toolkit=toolkit,
            middlewares=middlewares or [],
            state=AgentState(
                permission_context=build_workbench_permission_context(),
                tool_context={"activated_groups": []},
            ),
            offloader=workspace,
            context_config=ContextConfig(tool_result_limit=tool_result_limit),
            react_config=ReActConfig(max_iters=max_iters),
        )
