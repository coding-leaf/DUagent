"""Local multi-agent workflow for resources/generate.

Phase 5: Planner -> ResourceAgent fan-out -> Aggregator orchestration.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from typing import Any

from agentscope.agent import AgentBase

from agent_service.agents.resources_aggregator import aggregate_resource_results
from agent_service.agents.resources_agents import (
    CodeAgent,
    DocumentAgent,
    MindmapAgent,
    ReadingAgent,
    ResourceAgent,
    ResourceResult,
    _build_skeleton_result,
)
from agent_service.agents.resources_plan import (
    ResourcePlan,
    ResourceTaskSpec,
    build_rule_based_plan,
    generate_plan_with_llm,
)
from agent_service.core.logging import get_logger
from agent_service.schemas.resources import ResourceGenerateRequest

WebhookPayload = dict[str, Any]

logger = get_logger(__name__)

_V1_RESOURCE_TYPES = {"document", "mindmap", "reading", "code"}


async def run_multi_agent_resource_workflow(
    request: ResourceGenerateRequest,
    chat_provider,
    embedding_provider,
) -> WebhookPayload | None:
    """Run the local multi-agent resource workflow.

    Returns a webhook payload on success, or None when the caller should fall
    back to the existing LLM parallel path.
    """
    logger.info(
        "Multi-agent workflow started: task_id=%s resource_types=%s",
        request.task_id,
        request.resource_types or ["document", "mindmap", "reading", "code"],
    )
    requested_types = request.resource_types or ["document", "mindmap", "reading", "code"]
    if not set(requested_types).issubset(_V1_RESOURCE_TYPES):
        return None

    from agent_service.agents.resources import _build_course_knowledge_context

    course_knowledge_context = await _build_course_knowledge_context(
        request,
        embedding_provider,
    )
    plan = await _run_planner_with_fallback(
        request,
        chat_provider,
        course_knowledge_context,
    )
    results = await _run_resource_agents_parallel(
        request,
        plan,
        course_knowledge_context,
        chat_provider,
    )
    return aggregate_resource_results(request, plan, results)


async def _run_planner_with_fallback(
    request: ResourceGenerateRequest,
    chat_provider,
    course_knowledge_context: str,
) -> ResourcePlan:
    """Run LLM Planner and fall back to the rule-based planner on failure."""
    try:
        if chat_provider is not None:
            plan = await generate_plan_with_llm(
                request,
                chat_provider,
                course_knowledge_context,
            )
            if plan is not None:
                logger.info(
                    "LLM Planner succeeded: task_id=%s task_count=%d",
                    request.task_id,
                    len(plan.tasks),
                )
                return plan
    except Exception:
        logger.warning(
            "LLM Planner failed: task_id=%s",
            request.task_id,
            exc_info=True,
        )
    return build_rule_based_plan(request)


async def _run_resource_agents_parallel(
    request: ResourceGenerateRequest,
    plan: ResourcePlan,
    course_knowledge_context: str,
    chat_provider,
) -> list[ResourceResult]:
    """Run ResourceAgents with AgentScope fanout pipeline, then local fallback."""
    if not plan.tasks:
        return []
    try:
        return await _run_resource_agents_with_agentscope_pipeline(
            request,
            plan,
            course_knowledge_context,
            chat_provider,
        )
    except Exception:
        logger.warning(
            "AgentScope fanout pipeline failed, falling back to asyncio gather: task_id=%s",
            request.task_id,
            exc_info=True,
        )
        return await _run_resource_agents_with_asyncio_gather(
            request,
            plan,
            course_knowledge_context,
            chat_provider,
        )


async def _run_resource_agents_with_agentscope_pipeline(
    request: ResourceGenerateRequest,
    plan: ResourcePlan,
    course_knowledge_context: str,
    chat_provider,
) -> list[ResourceResult]:
    """Run ResourceAgents through AgentScope's native fanout orchestration."""
    from agentscope.message import Msg
    from agentscope.pipeline import fanout_pipeline

    agents = [
        _PipelineResourceAgent(
            _get_agent_for_type(task_spec.resource_type),
            request,
            task_spec,
            course_knowledge_context,
            chat_provider,
        )
        for task_spec in plan.tasks
    ]
    input_msg = Msg(
        name="resource_workflow",
        role="user",
        content=plan.overview or "resource generation",
        metadata={"task_id": request.task_id},
    )
    messages = await fanout_pipeline(agents, input_msg, enable_gather=True)
    return [_resource_result_from_pipeline_message(message) for message in messages]


async def _run_resource_agents_with_asyncio_gather(
    request: ResourceGenerateRequest,
    plan: ResourcePlan,
    course_knowledge_context: str,
    chat_provider,
) -> list[ResourceResult]:
    """Fallback runner used if AgentScope pipeline is unavailable."""
    tasks = [
        _run_single_agent_with_fallback(
            _get_agent_for_type(task_spec.resource_type),
            request,
            task_spec,
            course_knowledge_context,
            chat_provider,
        )
        for task_spec in plan.tasks
    ]
    return list(await asyncio.gather(*tasks))


async def _run_single_agent_with_fallback(
    agent: ResourceAgent,
    request: ResourceGenerateRequest,
    task_spec: ResourceTaskSpec,
    course_knowledge_context: str,
    chat_provider,
) -> ResourceResult:
    """Run one ResourceAgent and convert unexpected failure to skeleton."""
    try:
        result = await agent.generate(
            request,
            task_spec,
            course_knowledge_context,
            chat_provider,
        )
        if result is not None and isinstance(result.content, str) and result.content.strip():
            logger.info(
                "ResourceAgent succeeded: type=%s task_id=%s",
                agent.resource_type,
                request.task_id,
            )
            return result
    except Exception:
        logger.warning(
            "ResourceAgent failed: type=%s task_id=%s",
            agent.resource_type,
            request.task_id,
            exc_info=True,
        )
    return _build_skeleton_result(
        request,
        agent.resource_type,
        fallback_reason="agent_failed",
    )


def _get_agent_for_type(resource_type: str) -> ResourceAgent:
    """Return the ResourceAgent implementation for a v1 resource type."""
    agents: dict[str, ResourceAgent] = {
        "document": DocumentAgent(),
        "mindmap": MindmapAgent(),
        "reading": ReadingAgent(),
        "code": CodeAgent(),
    }
    try:
        return agents[resource_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported resource type: {resource_type}") from exc


class _PipelineResourceAgent(AgentBase):
    """AgentScope AgentBase adapter for existing ResourceAgent implementations."""

    def __init__(
        self,
        resource_agent: ResourceAgent,
        request: ResourceGenerateRequest,
        task_spec: ResourceTaskSpec,
        course_knowledge_context: str,
        chat_provider,
    ) -> None:
        super().__init__()
        self.resource_agent = resource_agent
        self.resource_type = resource_agent.resource_type
        self.request = request
        self.task_spec = task_spec
        self.course_knowledge_context = course_knowledge_context
        self.chat_provider = chat_provider

    async def observe(self, msg) -> None:
        return None

    async def reply(self, *args: Any, **kwargs: Any):
        from agentscope.message import Msg

        result = await _run_single_agent_with_fallback(
            self.resource_agent,
            self.request,
            self.task_spec,
            self.course_knowledge_context,
            self.chat_provider,
        )
        return Msg(
            name=self.resource_type,
            role="assistant",
            content=json.dumps(asdict(result), ensure_ascii=False),
        )


def _resource_result_from_pipeline_message(message) -> ResourceResult:
    text = message.get_text_content()
    if not text:
        raise ValueError("AgentScope pipeline message has no text content")
    data = json.loads(text)
    return ResourceResult(**data)
