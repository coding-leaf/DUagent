from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from inspect import isasyncgen
from time import perf_counter
from typing import Any

from agentscope.middleware import MiddlewareBase

from agent_service_v2.observability.logging import LogSink, build_log_record


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
        self._emit("acting.start", agent=agent)
        try:
            async for event in next_handler(**input_kwargs):
                yield event
        except Exception as exc:
            self._emit(
                "acting.error",
                agent=agent,
                level="error",
                duration_ms=_elapsed_ms(started_at),
                error=exc.__class__.__name__,
            )
            raise
        else:
            self._emit(
                "acting.end",
                agent=agent,
                duration_ms=_elapsed_ms(started_at),
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
