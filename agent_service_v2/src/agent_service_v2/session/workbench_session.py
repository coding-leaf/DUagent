from __future__ import annotations

import asyncio

from agentscope.message import Msg, TextBlock

from agent_service_v2.agents.workbench_factory import (
    MissingModelConfigError,
    WorkbenchAgentFactory,
)
from agent_service_v2.runtime.protocol_adapter import EDUProtocolAdapter
from agent_service_v2.session.run_bus import WorkbenchRun, WorkbenchRunBus
from agent_service_v2.workspaces.workbench_workspace_manager import (
    WorkbenchWorkspaceManager,
)


class WorkbenchSession:
    def __init__(
        self,
        *,
        run_bus: WorkbenchRunBus,
        workspace_manager: WorkbenchWorkspaceManager,
        agent_factory: WorkbenchAgentFactory,
    ) -> None:
        self._run_bus = run_bus
        self._workspace_manager = workspace_manager
        self._agent_factory = agent_factory

    def start(
        self,
        *,
        user_id: str,
        course_id: str | None,
        conversation_id: str | None,
        message: str,
        context: dict,
    ) -> WorkbenchRun:
        return asyncio.run(
            self.start_async(
                user_id=user_id,
                course_id=course_id,
                conversation_id=conversation_id,
                message=message,
                context=context,
            )
        )

    async def start_async(
        self,
        *,
        user_id: str,
        course_id: str | None,
        conversation_id: str | None,
        message: str,
        context: dict,
    ) -> WorkbenchRun:
        run = self._run_bus.create_run(conversation_id=conversation_id)
        workspace = self._workspace_manager.get_workspace(
            user_id=user_id,
            course_id=course_id,
            conversation_id=conversation_id or run.run_id,
        )

        try:
            agent = self._agent_factory.create_agent(
                user_id=user_id,
                course_id=course_id,
                workspace=workspace,
            )
        except MissingModelConfigError:
            self._run_bus.fail(run.run_id, reason="model_not_configured")
            return run

        await self._run_agent(run=run, agent=agent, message=message)
        return run

    async def _run_agent(self, *, run: WorkbenchRun, agent, message: str) -> None:
        adapter = EDUProtocolAdapter(
            run_id=run.run_id,
            conversation_id=run.conversation_id,
            agent=run.agent,
        )
        user_message = Msg(
            name="student",
            role="user",
            content=[TextBlock(text=message)],
        )
        try:
            async for agent_event in agent.reply_stream(user_message):
                self._run_bus.publish_event(adapter.adapt(agent_event))
            self._run_bus.complete(run.run_id)
        except Exception as exc:
            self._run_bus.fail(run.run_id, reason=exc.__class__.__name__)
