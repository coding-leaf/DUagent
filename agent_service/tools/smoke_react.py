"""ReActAgent LLM smoke — 验证真实 LLM 下 TutorReActAgent → JSON parse 主路径。"""

import sys
import time

from agent_service.agents.tutoring_react_flow import generate_tutoring_react_response
from agent_service.core.ai import get_ai_providers
from agent_service.core.config import settings
from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext
from agent_service.schemas.tutoring import TutoringChatRequest, TutoringUserProfile


def main() -> None:
    _print_banner()

    providers = get_ai_providers()
    chat_provider = providers.chat
    if not (hasattr(chat_provider, "model") and hasattr(chat_provider, "formatter")):
        print("FAIL: chat provider has no model/formatter — check LLM_PROVIDER in .env")
        sys.exit(1)

    request = TutoringChatRequest(
        user_id="smoke-user",
        course_id="data-structures",
        message="线性表和链表有什么区别？",
        user_profile=TutoringUserProfile(
            guidance_level="L2",
            knowledge_weak=["链表"],
            knowledge_mastered=["顺序表"],
        ),
    )
    context = TutoringRetrievalContext(
        user_id="smoke-user",
        course_id="data-structures",
        query_text="线性表和链表有什么区别？",
        include_course_knowledge=True,
        knowledge_points=["线性表", "链表"],
        user_memory_facts=["用户刚学完顺序表，容易混淆数组和链表。"],
        course_knowledge_chunks=["线性表是相同类型数据元素的有限序列，链表用指针表示逻辑关系。"],
    )

    started_at = time.monotonic()
    response = _run_sync(request, context, chat_provider)
    elapsed = time.monotonic() - started_at

    if response is None:
        print(f"Elapsed: {elapsed:.2f}s")
        print("FAIL: generate_tutoring_react_response returned None — ReAct path did not execute")
        print("Check LLM configuration and model compatibility.")
        sys.exit(1)

    print(f"Model: {getattr(settings, 'LLM_MODEL', 'unknown')}")
    print(f"Elapsed: {elapsed:.2f}s")
    print()

    if not response.model_text:
        print("FAIL: model_text is empty — ReAct output could not be parsed")
        sys.exit(1)

    print(f"model_text: {response.model_text}")
    print(f"knowledge_points: {response.knowledge_point_names}")
    print(f"suggestion: {response.suggestion_text}")
    print()

    if not response.knowledge_point_names:
        print("WARNING: knowledge_points empty — model may not have followed JSON format")
    if not response.suggestion_text:
        print("WARNING: suggestion empty — model may not have followed JSON format")

    print("OK — ReAct response parsed successfully")


def _run_sync(request, context, chat_provider):
    import asyncio

    try:
        return asyncio.run(
            generate_tutoring_react_response(request, context, chat_provider)
        )
    except Exception:
        import traceback

        print("FAIL: unhandled exception in ReActAgent smoke")
        traceback.print_exc()
        sys.exit(1)


def _print_banner() -> None:
    print("=== ReActAgent LLM Smoke ===")
    provider = getattr(settings, "LLM_PROVIDER", "unknown")
    print(f"Provider: {provider}")


if __name__ == "__main__":
    main()
