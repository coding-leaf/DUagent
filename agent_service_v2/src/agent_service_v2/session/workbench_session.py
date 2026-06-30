from __future__ import annotations

from agent_service_v2.agents.workbench_factory import (
    MissingModelConfigError,
    WorkbenchAgentFactory,
)
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
        run = self._run_bus.create_run(conversation_id=conversation_id)
        workspace = self._workspace_manager.get_workspace(
            user_id=user_id,
            course_id=course_id,
            conversation_id=conversation_id or run.run_id,
        )

        try:
            self._agent_factory.create_agent(
                user_id=user_id,
                course_id=course_id,
                workspace=workspace,
            )
        except MissingModelConfigError:
            self._run_bus.fail(run.run_id, reason="model_not_configured")
            return run

        self._run_bus.fail(run.run_id, reason="agent_execution_not_implemented")
        return run
