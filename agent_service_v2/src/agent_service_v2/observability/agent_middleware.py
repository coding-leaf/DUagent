from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from inspect import isasyncgen
from time import perf_counter
from typing import Any

from agentscope.middleware import MiddlewareBase

from agent_service_v2.observability.logging import (
    LogSink,
    build_log_record,
    enum_value,
    input_preview,
    output_preview,
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
        self._sink = sink

    async def on_reply(
        self,
        agent,
        input_kwargs: dict,
        next_handler: Callable[..., AsyncGenerator],
    ) -> AsyncGenerator:
        started_at = perf_counter()
        self._emit("reply.start", agent=agent)
        try:
            async for item in next_handler(**input_kwargs):
                yield item
        except Exception as exc:
            self._emit(
                "reply.error",
                agent=agent,
                level="error",
                duration_ms=_elapsed_ms(started_at),
                error=exc.__class__.__name__,
            )
            raise
        else:
            self._emit(
                "reply.end",
                agent=agent,
                duration_ms=_elapsed_ms(started_at),
            )

    async def on_reasoning(
        self,
        agent,
        input_kwargs: dict,
        next_handler: Callable[..., AsyncGenerator],
    ) -> AsyncGenerator:
        started_at = perf_counter()
        self._emit("reasoning.start", agent=agent)
        try:
            async for event in next_handler(**input_kwargs):
                yield event
        except Exception as exc:
            self._emit(
                "reasoning.error",
                agent=agent,
                level="error",
                duration_ms=_elapsed_ms(started_at),
                error=exc.__class__.__name__,
            )
            raise
        else:
            self._emit(
                "reasoning.end",
                agent=agent,
                duration_ms=_elapsed_ms(started_at),
            )

    async def on_model_call(
        self,
        agent,
        input_kwargs: dict,
        next_handler: Callable[..., Awaitable[Any]],
    ) -> Any:
        started_at = perf_counter()
        current_model = input_kwargs.get("current_model")
        self._emit(
            "model_call.start",
            agent=agent,
            extra={"model": getattr(current_model, "model_name", None) or getattr(current_model, "model", None)},
        )
        try:
            result = await next_handler(**input_kwargs)
        except Exception as exc:
            self._emit(
                "model_call.error",
                agent=agent,
                level="error",
                duration_ms=_elapsed_ms(started_at),
                error=exc.__class__.__name__,
            )
            raise
        if isasyncgen(result):
            return self._wrap_model_stream(result, agent, started_at)
        self._emit(
            "model_call.end",
            agent=agent,
            duration_ms=_elapsed_ms(started_at),
        )
        return result

    async def _wrap_model_stream(
        self,
        stream: AsyncGenerator[Any],
        agent,
        started_at: float,
    ) -> AsyncGenerator[Any]:
        try:
            async for item in stream:
                yield item
        except Exception as exc:
            self._emit(
                "model_call.error",
                agent=agent,
                level="error",
                duration_ms=_elapsed_ms(started_at),
                error=exc.__class__.__name__,
            )
            raise
        else:
            self._emit(
                "model_call.end",
                agent=agent,
                duration_ms=_elapsed_ms(started_at),
            )

    async def on_acting(
        self,
        agent,
        input_kwargs: dict,
        next_handler: Callable[..., AsyncGenerator],
    ) -> AsyncGenerator:
        started_at = perf_counter()
        tool_call = input_kwargs.get("tool_call")
        tool_extra = _tool_call_extra(tool_call)
        self._emit("tool.call.start", agent=agent, extra=tool_extra)
        last_item = None
        try:
            async for event in next_handler(**input_kwargs):
                last_item = event
                yield event
        except Exception as exc:
            self._emit(
                "tool.call.error",
                agent=agent,
                level="error",
                duration_ms=_elapsed_ms(started_at),
                error=exc.__class__.__name__,
                extra={
                    **tool_extra,
                    "error_message": str(exc),
                },
            )
            raise
        else:
            self._emit(
                "tool.call.end",
                agent=agent,
                duration_ms=_elapsed_ms(started_at),
                extra={
                    **tool_extra,
                    **_tool_result_extra(last_item),
                },
            )

    def _emit(
        self,
        event: str,
        *,
        agent,
        level: str = "info",
        duration_ms: float | None = None,
        error: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self._sink(
            build_log_record(
                event=event,
                level=level,
                run_id=self.run_id,
                conversation_id=self.conversation_id,
                user_id=self.user_id,
                course_id=self.course_id,
                agent=getattr(agent, "name", "unknown"),
                duration_ms=duration_ms,
                error=error,
                extra=extra,
            )
        )


def _elapsed_ms(started_at: float) -> float:
    return (perf_counter() - started_at) * 1000


def _tool_call_extra(tool_call: Any) -> dict[str, Any]:
    if tool_call is None:
        return {}
    return {
        "tool_call_id": getattr(tool_call, "id", None),
        "tool_name": getattr(tool_call, "name", None),
        "input_preview": input_preview(getattr(tool_call, "input", None)),
    }


def _tool_result_extra(result: Any) -> dict[str, Any]:
    if result is None:
        return {}
    return {
        "state": enum_value(getattr(result, "state", None)),
        "output_preview": output_preview(result),
    }
