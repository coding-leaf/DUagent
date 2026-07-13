from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from agent_service_v2.agents.model_provider import (
    AgentModelSettings,
    build_chat_model_from_settings,
)
from agent_service_v2.generators.public_resources import PublicResourceGenerator


logger = logging.getLogger(__name__)
PUBLIC_RESOURCE_GENERATION_CONCURRENCY = 2
_generation_semaphore = asyncio.Semaphore(PUBLIC_RESOURCE_GENERATION_CONCURRENCY)


async def run_public_resource_generation(
    *,
    settings: AgentModelSettings,
    task_id: str,
    course_id: str,
    course_title: str | None = None,
    chapter: str | None,
    knowledge_point: str | None,
    resource_types: list[str],
    webhook_url: str,
) -> list[dict[str, Any]]:
    model = build_chat_model_from_settings(settings, stream=False)
    generator = PublicResourceGenerator(model=model)
    normalized_chapter = chapter or ""
    normalized_knowledge_point = knowledge_point or "综合"
    try:
        async with _generation_semaphore:
            resources = await generator.generate_many(
                resource_types,
                chapter=normalized_chapter,
                knowledge_point=normalized_knowledge_point,
                course_id=course_id,
                course_title=course_title,
            )
        await _post_webhook(
            webhook_url,
            settings,
            {
                "task_id": task_id,
                "task_type": "resource_generation",
                "status": "completed",
                "progress": 100,
                "result": {"resources": resources},
            },
        )
        return resources
    except Exception as exc:
        logger.exception("Public resource generation failed: task_id=%s", task_id)
        await _post_failed_webhook(
            webhook_url,
            settings,
            task_id=task_id,
            error_message=str(exc)[:500],
        )
        raise


async def _post_failed_webhook(
    url: str,
    settings: AgentModelSettings,
    *,
    task_id: str,
    error_message: str,
) -> None:
    await _post_webhook(
        url,
        settings,
        {
            "task_id": task_id,
            "task_type": "resource_generation",
            "status": "failed",
            "progress": 100,
            "error_code": "resource_gen_failed",
            "error_message": error_message,
        },
    )


async def _post_webhook(
    url: str,
    settings: AgentModelSettings,
    payload: dict[str, Any],
) -> None:
    if not url:
        return
    headers = (
        {"X-Webhook-Secret": settings.WEBHOOK_SECRET}
        if settings.WEBHOOK_SECRET
        else {}
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
