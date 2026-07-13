from __future__ import annotations

import asyncio
from contextlib import suppress

from agentscope.event import (
    ExceedMaxItersEvent,
    ReplyEndEvent,
    RequireUserConfirmEvent,
    TextBlockDeltaEvent,
)

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
from agent_service_v2.artifacts.manifest import ArtifactPublisher
from agent_service_v2.safety.content_review_middleware import ContentSafetyReviewer
from agent_service_v2.safety.local_wordlist import LocalSensitiveWordFilter
from agent_service_v2.session.workbench_input import build_workbench_agent_input
from agent_service_v2.session.run_bus import WorkbenchRun, WorkbenchRunBus
from agent_service_v2.workspaces.workbench_workspace_manager import (
    WorkbenchWorkspaceManager,
)
from agent_service_v2.workspaces.run_store import WorkbenchRunStore


class WorkbenchSession:
    def __init__(
        self,
        *,
        run_bus: WorkbenchRunBus,
        workspace_manager: WorkbenchWorkspaceManager,
        agent_factory: WorkbenchAgentFactory,
        content_reviewer: ContentSafetyReviewer | None = None,
    ) -> None:
        self._run_bus = run_bus
        self._workspace_manager = workspace_manager
        self._agent_factory = agent_factory
        self._content_reviewer = content_reviewer or ContentSafetyReviewer()
        self._tasks: dict[str, asyncio.Task] = {}

    def start(
        self,
        *,
        user_id: str,
        course_id: str | None,
        catalog_id: str | None = None,
        conversation_id: str | None,
        message: str,
        context: dict,
    ) -> WorkbenchRun:
        return asyncio.run(
            self._start_async(
                user_id=user_id,
                course_id=course_id,
                catalog_id=catalog_id,
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
        catalog_id: str | None = None,
        conversation_id: str | None,
        message: str,
        context: dict,
    ) -> WorkbenchRun:
        return await self._start_async(
            user_id=user_id,
            course_id=course_id,
            catalog_id=catalog_id,
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
        catalog_id: str | None,
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
                catalog_id=catalog_id,
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
                context=context,
                run_store=WorkbenchRunStore(workspace=workspace),
                user_id=user_id,
                course_id=course_id,
            )
            return run

        task = asyncio.create_task(
            self._run_agent(
                run=run,
                agent=agent,
                message=message,
                context=context,
                run_store=WorkbenchRunStore(workspace=workspace),
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
        context: dict,
        run_store: WorkbenchRunStore,
        user_id: str,
        course_id: str | None,
    ) -> None:
        run_store.write_state(run.run_id, {"status": "running", "conversation_id": run.conversation_id})
        adapter = EDUProtocolAdapter(
            run_id=run.run_id,
            conversation_id=run.conversation_id,
            agent=run.agent,
            artifact_publisher=ArtifactPublisher(
                run_id=run.run_id,
                artifact_dir=run_store.artifact_dir(run.run_id),
            ),
        )
        agent_inputs = build_workbench_agent_input(
            message=message,
            context=context,
        )
        raw_assistant_chunks: list[str] = []
        stream_filter = LocalSensitiveWordFilter().stream()
        last_text_event = None
        pending_filtered = ""
        pending_text_event = None
        failed = False
        try:
            async for agent_event in agent.reply_stream(agent_inputs):
                if isinstance(agent_event, TextBlockDeltaEvent):
                    raw_assistant_chunks.append(agent_event.delta)
                    last_text_event = agent_event
                    filtered_delta = stream_filter.feed(agent_event.delta)
                    if not filtered_delta:
                        continue
                    if pending_filtered and pending_text_event is not None:
                        buffered_event = pending_text_event.model_copy(
                            update={"delta": pending_filtered}
                        )
                        for edu_event in adapter.adapt_many(buffered_event):
                            published_event = self._run_bus.publish_event(edu_event)
                            run_store.append_event(run.run_id, published_event.to_dict())
                    pending_filtered = filtered_delta
                    pending_text_event = agent_event
                    continue
                if isinstance(agent_event, ExceedMaxItersEvent) and last_text_event is not None:
                    final_delta = pending_filtered + stream_filter.finish()
                    if final_delta:
                        tail_event = (pending_text_event or last_text_event).model_copy(
                            update={"delta": final_delta}
                        )
                        for edu_event in adapter.adapt_many(tail_event):
                            published_event = self._run_bus.publish_event(edu_event)
                            run_store.append_event(run.run_id, published_event.to_dict())
                    pending_filtered = ""
                    last_text_event = None
                if (
                    isinstance(agent_event, ReplyEndEvent)
                    and not failed
                    and last_text_event is not None
                ):
                    tail = stream_filter.finish()
                    final_delta = pending_filtered + tail
                    if final_delta:
                        tail_event = (pending_text_event or last_text_event).model_copy(
                            update={"delta": final_delta}
                        )
                        for edu_event in adapter.adapt_many(tail_event):
                            published_event = self._run_bus.publish_event(edu_event)
                            run_store.append_event(run.run_id, published_event.to_dict())
                debug_record = build_agentscope_event_log(
                    agent_event,
                    run_id=run.run_id,
                    conversation_id=run.conversation_id,
                    user_id=user_id,
                    course_id=course_id,
                    agent=run.agent,
                )
                if debug_record is not None:
                    debug_event = self._run_bus.publish(
                        run.run_id,
                        EduEventType.DEBUG_LOG,
                        debug_record,
                    )
                    run_store.append_event(run.run_id, debug_event.to_dict())
                if isinstance(agent_event, RequireUserConfirmEvent):
                    permission_event = self._run_bus.publish(
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
                    run_store.append_event(run.run_id, permission_event.to_dict())
                    failed_event = self._run_bus.fail(
                        run.run_id,
                        reason="user_confirmation_required",
                    )
                    run_store.append_event(run.run_id, failed_event.to_dict())
                    return
                if failed and isinstance(agent_event, ReplyEndEvent):
                    continue
                for edu_event in adapter.adapt_many(agent_event):
                    published_event = self._run_bus.publish_event(edu_event)
                    run_store.append_event(run.run_id, published_event.to_dict())
                    if published_event.type == EduEventType.WORKFLOW_FAILED:
                        failed = True
                if isinstance(agent_event, ExceedMaxItersEvent):
                    run_store.write_state(
                        run.run_id,
                        {"status": "failed", "conversation_id": run.conversation_id},
                    )
                if isinstance(agent_event, ReplyEndEvent) and not failed:
                    await self._publish_content_safety_review(
                        run=run,
                        run_store=run_store,
                        content="".join(raw_assistant_chunks),
                    )
            if failed:
                run_store.write_state(run.run_id, {"status": "failed", "conversation_id": run.conversation_id})
            else:
                run_store.write_state(run.run_id, {"status": "completed", "conversation_id": run.conversation_id})
            self._run_bus.complete(run.run_id)
        except asyncio.CancelledError:
            failed_event = self._run_bus.fail(run.run_id, reason="cancelled")
            run_store.append_event(run.run_id, failed_event.to_dict())
            run_store.write_state(run.run_id, {"status": "cancelled", "conversation_id": run.conversation_id})
            raise
        except Exception as exc:
            failed_event = self._run_bus.fail(run.run_id, reason=exc.__class__.__name__)
            run_store.append_event(run.run_id, failed_event.to_dict())
            run_store.write_state(run.run_id, {"status": "failed", "conversation_id": run.conversation_id})

    async def _publish_content_safety_review(
        self,
        *,
        run: WorkbenchRun,
        run_store: WorkbenchRunStore,
        content: str,
    ) -> None:
        review = await self._content_reviewer.review(content)
        payload = review.to_payload()
        run_store.write_review(run.run_id, payload)
        event = self._run_bus.publish(
            run.run_id,
            EduEventType.CONTENT_SAFETY_REVIEWED,
            payload,
        )
        run_store.append_event(run.run_id, event.to_dict())
