from __future__ import annotations

import asyncio
from contextlib import suppress

from agentscope.event import RequireUserConfirmEvent
from agentscope.message import Msg, TextBlock

from agent_service_v2.agents.workbench_factory import (
    MissingModelConfigError,
    WorkbenchAgentFactory,
)
from agent_service_v2.observability.logging import (
    build_log_record,
    build_agentscope_event_log,
    input_preview,
)
from agent_service_v2.runtime.protocol_adapter import EDUProtocolAdapter
from agent_service_v2.runtime.edu_events import EduEventType
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
        self._tasks: dict[str, asyncio.Task] = {}

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
            self._start_async(
                user_id=user_id,
                course_id=course_id,
                conversation_id=conversation_id,
                message=message,
                context=context,
                run_in_background=False,
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
        return await self._start_async(
            user_id=user_id,
            course_id=course_id,
            conversation_id=conversation_id,
            message=message,
            context=context,
            run_in_background=True,
        )

    async def _start_async(
        self,
        *,
        user_id: str,
        course_id: str | None,
        conversation_id: str | None,
        message: str,
        context: dict,
        run_in_background: bool,
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
                run_id=run.run_id,
                conversation_id=run.conversation_id,
                log_sink=lambda record: self._run_bus.publish(
                    run.run_id,
                    EduEventType.DEBUG_LOG,
                    record,
                ),
            )
        except MissingModelConfigError:
            self._run_bus.fail(run.run_id, reason="model_not_configured")
            return run

        if not run_in_background:
            await self._run_agent(
                run=run,
                agent=agent,
                message=message,
                user_id=user_id,
                course_id=course_id,
            )
            return run

        task = asyncio.create_task(
            self._run_agent(
                run=run,
                agent=agent,
                message=message,
                user_id=user_id,
                course_id=course_id,
            )
        )
        self._tasks[run.run_id] = task
        task.add_done_callback(lambda _task, run_id=run.run_id: self._tasks.pop(run_id, None))
        return run

    async def cancel_run(self, run_id: str) -> bool:
        task = self._tasks.get(run_id)
        if task is None or task.done():
            return False
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        return True

    async def _run_agent(
        self,
        *,
        run: WorkbenchRun,
        agent,
        message: str,
        user_id: str,
        course_id: str | None,
    ) -> None:
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
                debug_record = build_agentscope_event_log(
                    agent_event,
                    run_id=run.run_id,
                    conversation_id=run.conversation_id,
                    user_id=user_id,
                    course_id=course_id,
                    agent=run.agent,
                )
                if debug_record is not None:
                    self._run_bus.publish(
                        run.run_id,
                        EduEventType.DEBUG_LOG,
                        debug_record,
                    )
                if isinstance(agent_event, RequireUserConfirmEvent):
                    self._run_bus.publish(
                        run.run_id,
                        EduEventType.DEBUG_LOG,
                        build_log_record(
                            event="permission.required",
                            level="error",
                            message="Tool call requires user confirmation",
                            run_id=run.run_id,
                            conversation_id=run.conversation_id,
                            user_id=user_id,
                            course_id=course_id,
                            agent=run.agent,
                            span_id=f"span_{run.run_id}_permission_{agent_event.reply_id}",
                            span_kind="permission",
                            name="permission.required",
                            phase="event",
                            attributes={
                                "reply_id": agent_event.reply_id,
                                "tool_calls": [
                                    {
                                        "id": tool_call.id,
                                        "name": tool_call.name,
                                        "tool_input_preview": input_preview(tool_call.input),
                                    }
                                    for tool_call in agent_event.tool_calls
                                ],
                            },
                        ),
                    )
                    self._run_bus.fail(
                        run.run_id,
                        reason="user_confirmation_required",
                    )
                    return
                for edu_event in adapter.adapt_many(agent_event):
                    self._run_bus.publish_event(edu_event)
            self._run_bus.complete(run.run_id)
        except asyncio.CancelledError:
            self._run_bus.fail(run.run_id, reason="cancelled")
            raise
        except Exception as exc:
            self._run_bus.fail(run.run_id, reason=exc.__class__.__name__)
