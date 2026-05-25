"""API smoke — 验证 POST /agent/v1/tutoring/chat SSE 完整链路（ReAct + toolkit）。"""

import asyncio
import json
import sys
import time

import httpx

from agent_service.core.config import settings
from agent_service.main import app
from agent_service.schemas.tutoring import TutoringChatRequest, TutoringUserProfile


async def main() -> None:
    provider = getattr(settings, "LLM_PROVIDER", "unknown")
    model = getattr(settings, "LLM_MODEL", "unknown")
    print(f"=== Tutoring API Smoke ===")
    print(f"Provider: {provider}")
    print(f"Model: {model}")
    print()

    request = TutoringChatRequest(
        user_id="smoke-api-user",
        course_id="data-structures",
        message="线性表和链表有什么区别？",
        user_profile=TutoringUserProfile(
            guidance_level="L2",
            knowledge_weak=["链表"],
            knowledge_mastered=["顺序表"],
        ),
    )

    transport = httpx.ASGITransport(app=app)
    started_at = time.monotonic()

    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=30
    ) as client:
        try:
            async with client.stream(
                "POST", "/agent/v1/tutoring/chat", json=request.model_dump()
            ) as response:
                events = await _collect_events(response)
        except asyncio.TimeoutError:
            print("FAIL: request timed out after 30s")
            sys.exit(1)

    elapsed = time.monotonic() - started_at
    _report(events, elapsed, provider, model)


async def _collect_events(response) -> list[dict]:
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" not in content_type:
        print(f"FAIL: unexpected content-type: {content_type}")
        sys.exit(1)

    events: list[dict] = []
    async for line in response.aiter_lines():
        if not line.strip():
            continue
        if line.startswith("data: "):
            try:
                events.append(json.loads(line.removeprefix("data: ")))
            except json.JSONDecodeError:
                print(f"WARNING: unparseable SSE line: {line[:80]}...")
    return events


def _report(events: list[dict], elapsed: float, provider: str, model: str) -> None:
    if not events:
        print("FAIL: no SSE events received — stream was empty")
        sys.exit(1)

    types = [e.get("type", "?") for e in events]
    print(f"Model: {model}")
    print(f"Elapsed: {elapsed:.2f}s")
    print(f"Events ({len(events)}): {' → '.join(types)}")

    # ── chunk(rule) ──────────────────────────────────────────────
    rule_chunk = _find(events, "chunk")
    if rule_chunk is None:
        print("FAIL: no chunk event received")
        sys.exit(1)
    rule_content = rule_chunk.get("content", "")
    print(f"  rule chunk: {len(rule_content)} chars")

    # ── chunk(model) ─────────────────────────────────────────────
    chunks = [e for e in events if e.get("type") == "chunk"]
    model_chunk = chunks[1] if len(chunks) >= 2 else None
    if model_chunk is None:
        if events[-1].get("type") == "done":
            print(
                "FAIL: only rule chunk received — ReAct/chat path did not produce model output"
            )
            print(
                "  The API completed successfully but the model did not contribute content."
            )
        else:
            print("FAIL: stream ended without model chunk or done event")
        sys.exit(1)
    model_content = model_chunk.get("content", "")
    print(f"  model chunk: {len(model_content)} chars")

    # ── knowledge_points ─────────────────────────────────────────
    kp_event = _find(events, "knowledge_points")
    if kp_event is None:
        print("FAIL: no knowledge_points event")
        sys.exit(1)
    kps = kp_event.get("knowledge_points", [])
    if not kps:
        print("FAIL: knowledge_points is empty")
        sys.exit(1)
    print(
        f"  knowledge_points: {len(kps)} — {[kp.get('name', '?') for kp in kps]}"
    )

    # ── suggestion ───────────────────────────────────────────────
    sug_event = _find(events, "suggestion")
    if sug_event is None:
        print("FAIL: no suggestion event")
        sys.exit(1)
    sug = sug_event.get("suggestion", "")
    if not sug:
        print("FAIL: suggestion is empty")
        sys.exit(1)
    print(f"  suggestion: {len(sug)} chars")

    # ── done ─────────────────────────────────────────────────────
    done_event = events[-1] if events else None
    if done_event is None or done_event.get("type") != "done":
        print(
            f"FAIL: last event is not done"
            f" (got {done_event.get('type', '?') if done_event else 'None'})"
        )
        sys.exit(1)
    print("  done: OK")

    print()
    print("OK — tutoring/chat SSE complete with ReAct model output")


def _find(events: list[dict], event_type: str) -> dict | None:
    for e in events:
        if e.get("type") == event_type:
            return e
    return None


if __name__ == "__main__":
    asyncio.run(main())
