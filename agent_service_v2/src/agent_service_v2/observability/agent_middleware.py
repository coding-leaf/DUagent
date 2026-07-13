from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from inspect import isasyncgen
from time import perf_counter
from typing import Any

from agentscope.middleware import MiddlewareBase

from agent_service_v2.observability.agent_log_emitter import (
    AgentLogEmitter,
    elapsed_ms,
    model_call_attributes,
    tool_call_attributes,
    tool_result_attributes,
)
from agent_service_v2.observability.logging import (
    LogSink,
    new_span_id,
)


class AgentRunLoggingMiddleware(MiddlewareBase):
    def __init__(
        self,
        *,
        run_id: str,
        conversation_id: str | None,
        user_id: str,
        course_id: str | None,
        sink: LogSink,
    ) -> None:
        self.run_id = run_id
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.course_id = course_id
        self.trace_id = run_id
        self.agent_span_id = f"span_{run_id}_agent_reply"
        self._log = AgentLogEmitter(
            run_id=run_id,
            conversation_id=conversation_id,
            user_id=user_id,
            course_id=course_id,
            sink=sink,
        )

    async def on_reply(
        self,
        agent,
        input_kwargs: dict,
        next_handler: Callable[..., AsyncGenerator],
    ) -> AsyncGenerator:
        started_at = perf_counter()
        self._log.emit(
            "reply.start",
            agent=agent,
            span_id=self.agent_span_id,
            span_kind="agent",
            name=f"agent.reply {getattr(agent, 'name', 'unknown')}",
            phase="start",
        )
        try:
            async for item in next_handler(**input_kwargs):
                yield item
        except Exception as exc:
            self._log.emit(
                "reply.error",
                agent=agent,
                level="error",
                duration_ms=elapsed_ms(started_at),
                error=exc.__class__.__name__,
                error_message=str(exc),
                span_id=self.agent_span_id,
                span_kind="agent",
                name=f"agent.reply {getattr(agent, 'name', 'unknown')}",
                phase="error",
            )
            raise
        else:
            self._log.emit(
                "reply.end",
                agent=agent,
                duration_ms=elapsed_ms(started_at),
                span_id=self.agent_span_id,
                span_kind="agent",
                name=f"agent.reply {getattr(agent, 'name', 'unknown')}",
                phase="end",
            )

    async def on_reasoning(
        self,
        agent,
        input_kwargs: dict,
        next_handler: Callable[..., AsyncGenerator],
    ) -> AsyncGenerator:
        started_at = perf_counter()
        span_id = new_span_id(self.run_id, "reasoning")
        self._log.emit(
            "reasoning.start",
            agent=agent,
            span_id=span_id,
            parent_span_id=self.agent_span_id,
            span_kind="reasoning",
            name="agent.reasoning",
            phase="start",
        )
        try:
            async for event in next_handler(**input_kwargs):
                yield event
        except Exception as exc:
            self._log.emit(
                "reasoning.error",
                agent=agent,
                level="error",
                duration_ms=elapsed_ms(started_at),
                error=exc.__class__.__name__,
                error_message=str(exc),
                span_id=span_id,
                parent_span_id=self.agent_span_id,
                span_kind="reasoning",
                name="agent.reasoning",
                phase="error",
            )
            raise
        else:
            self._log.emit(
                "reasoning.end",
                agent=agent,
                duration_ms=elapsed_ms(started_at),
                span_id=span_id,
                parent_span_id=self.agent_span_id,
                span_kind="reasoning",
                name="agent.reasoning",
                phase="end",
            )

    async def on_model_call(
        self,
        agent,
        input_kwargs: dict,
        next_handler: Callable[..., Awaitable[Any]],
    ) -> Any:
        started_at = perf_counter()
        current_model = input_kwargs.get("current_model")
        model_name = getattr(current_model, "model_name", None) or getattr(current_model, "model", None)
        model_attributes = {
            "model": model_name,
            **model_call_attributes(agent, input_kwargs),
        }
        span_id = new_span_id(self.run_id, "model_call")
        self._log.emit(
            "model_call.start",
            agent=agent,
            span_id=span_id,
            parent_span_id=self.agent_span_id,
            span_kind="model",
            name=f"model.call {model_name or 'unknown'}",
            phase="start",
            attributes=model_attributes,
        )
        try:
            result = await next_handler(**input_kwargs)
        except Exception as exc:
            self._log.emit(
                "model_call.error",
                agent=agent,
                level="error",
                duration_ms=elapsed_ms(started_at),
                error=exc.__class__.__name__,
                error_message=str(exc),
                span_id=span_id,
                parent_span_id=self.agent_span_id,
                span_kind="model",
                name=f"model.call {model_name or 'unknown'}",
                phase="error",
            )
            raise
        if isasyncgen(result):
            return self._wrap_model_stream(
                result,
                agent,
                started_at,
                span_id=span_id,
                model_name=model_name,
            )
        self._log.emit(
            "model_call.end",
            agent=agent,
            duration_ms=elapsed_ms(started_at),
            span_id=span_id,
            parent_span_id=self.agent_span_id,
            span_kind="model",
            name=f"model.call {model_name or 'unknown'}",
            phase="end",
            attributes={"model": model_name},
        )
        return result

    async def _wrap_model_stream(
        self,
        stream: AsyncGenerator[Any],
        agent,
        started_at: float,
        *,
        span_id: str,
        model_name: str | None,
    ) -> AsyncGenerator[Any]:
        try:
            async for item in stream:
                yield item
        except Exception as exc:
            self._log.emit(
                "model_call.error",
                agent=agent,
                level="error",
                duration_ms=elapsed_ms(started_at),
                error=exc.__class__.__name__,
                error_message=str(exc),
                span_id=span_id,
                parent_span_id=self.agent_span_id,
                span_kind="model",
                name=f"model.call {model_name or 'unknown'}",
                phase="error",
            )
            raise
        else:
            self._log.emit(
                "model_call.end",
                agent=agent,
                duration_ms=elapsed_ms(started_at),
                span_id=span_id,
                parent_span_id=self.agent_span_id,
                span_kind="model",
                name=f"model.call {model_name or 'unknown'}",
                phase="end",
                attributes={"model": model_name},
            )

    async def on_acting(
        self,
        agent,
        input_kwargs: dict,
        next_handler: Callable[..., AsyncGenerator],
    ) -> AsyncGenerator:
        started_at = perf_counter()
        tool_call = input_kwargs.get("tool_call")
        tool_extra = tool_call_attributes(tool_call)
        tool_name = tool_extra.get("tool_name") or "unknown"
        if tool_name in {"search_memory", "add_memory"}:
            tool_extra.pop("tool_input_preview", None)
            tool_extra["memory_content_redacted"] = True
        tool_call_id = tool_extra.get("tool_call_id") or new_span_id(self.run_id, "tool_call")
        span_id = f"span_{self.run_id}_tool_{tool_call_id}"
        self._log.emit(
            "tool.call.start",
            agent=agent,
            span_id=span_id,
            parent_span_id=self.agent_span_id,
            span_kind="tool",
            name=f"execute_tool {tool_name}",
            phase="start",
            attributes=tool_extra,
        )
        last_item = None
        try:
            async for event in next_handler(**input_kwargs):
                last_item = event
                yield event
        except Exception as exc:
            self._log.emit(
                "tool.call.error",
                agent=agent,
                level="error",
                duration_ms=elapsed_ms(started_at),
                error=exc.__class__.__name__,
                error_message=str(exc),
                span_id=span_id,
                parent_span_id=self.agent_span_id,
                span_kind="tool",
                name=f"execute_tool {tool_name}",
                phase="error",
                attributes={
                    **tool_extra,
                    "error_message": str(exc),
                },
            )
            raise
        else:
            self._log.emit(
                "tool.call.end",
                agent=agent,
                duration_ms=elapsed_ms(started_at),
                span_id=span_id,
                parent_span_id=self.agent_span_id,
                span_kind="tool",
                name=f"execute_tool {tool_name}",
                phase="end",
                attributes={
                    **tool_extra,
                    **(
                        {"tool_output_redacted": True}
                        if tool_name in {"search_memory", "add_memory"}
                        else tool_result_attributes(last_item)
                    ),
                },
            )
