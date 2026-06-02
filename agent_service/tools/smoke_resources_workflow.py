"""Resources workflow smoke.

Default mode uses a deterministic fake LLM provider to prove the multi-agent
path is reachable without Backend. Use --live to exercise configured providers.

Usage:
  ./.venv/bin/python -m agent_service.tools.smoke_resources_workflow
  ./.venv/bin/python -m agent_service.tools.smoke_resources_workflow --live
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Sequence

from agent_service.core.ai import ChatMessage, get_ai_providers
from agent_service.schemas.resources import ResourceGenerateRequest


class _FakeResourcesChatProvider:
    """Fake AgentScope-style chat provider that hits the multi-agent gate."""

    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, messages: Sequence[ChatMessage], **kwargs) -> str:
        self.calls += 1
        text = "\n".join(message.content for message in messages)
        if "ResourcePlan" in text or "tasks" in text or "资源规划师" in text:
            return _json({
                "overview": "一次函数资源生成计划",
                "knowledge_summary": "一次函数 y = kx + b，核心是斜率和截距。",
                "tasks": [
                    _task("document", "markdown"),
                    _task("mindmap", "Mermaid mindmap 语法"),
                    _task("reading", "markdown"),
                    _task("code", "markdown code"),
                ],
            })
        if "Mermaid mindmap" in text:
            return _json({
                "title": "一次函数知识导图",
                "description": "一次函数核心结构",
                "content": "mindmap\n  root((一次函数))\n    定义\n      y = kx + b\n    性质\n      图像是一条直线",
            })
        if "拓展阅读" in text:
            return _json({
                "title": "一次函数拓展阅读",
                "description": "线性模型拓展",
                "content": "## 拓展阅读\n一次函数是最基础的线性模型。",
            })
        if "代码示例" in text or "C 语言" in text:
            return _json({
                "title": "一次函数代码示例",
                "description": "C 语言计算一次函数",
                "content": "## 代码\n```c\n#include <stdio.h>\nint main(){ return 0; }\n```",
            })
        return _json({
            "title": "一次函数知识讲解",
            "description": "一次函数基础讲解",
            "content": "## 一次函数\n形如 y = kx + b 的函数称为一次函数。",
        })


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use configured real providers from .env instead of fake providers.",
    )
    args = parser.parse_args()
    return asyncio.run(_main_async(live=args.live))


async def _main_async(live: bool) -> int:
    from agent_service.agents.resources_workflow import run_multi_agent_resource_workflow

    request = ResourceGenerateRequest(
        task_id="smoke-resources-workflow",
        user_id="smoke",
        course_id="smoke-course",
        webhook_url="http://localhost:9999/webhook",
        chapter="函数",
        knowledge_point="一次函数",
        resource_types=["document", "mindmap", "reading", "code"],
    )
    if live:
        providers = get_ai_providers()
        chat_provider = providers.chat
        embedding_provider = providers.embedding
        if chat_provider is None:
            print(json.dumps({
                "status": "SKIP",
                "reason": "LLM provider is not configured",
                "mode": "live",
            }, ensure_ascii=False, indent=2))
            return 0
    else:
        chat_provider = _FakeResourcesChatProvider()
        embedding_provider = None

    payload = await run_multi_agent_resource_workflow(
        request,
        chat_provider,
        embedding_provider,
    )
    result = _evaluate_payload(payload)
    result["mode"] = "live" if live else "fake"
    result["path"] = "multi_agent" if payload is not None else "fallback_required"
    if isinstance(chat_provider, _FakeResourcesChatProvider):
        result["llm_calls"] = chat_provider.calls

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


def _evaluate_payload(payload) -> dict:
    if payload is None:
        return {"status": "FAIL", "reason": "workflow returned None"}
    resources = payload.get("result", {}).get("resources", [])
    types = [resource.get("type") for resource in resources]
    required = {"document", "mindmap", "reading", "code"}
    missing = sorted(required - set(types))
    leaked_fields = [
        key
        for resource in resources
        for key in ("generated_by", "fallback_reason", "is_skeleton")
        if key in resource
    ]
    empty_content = [
        resource.get("type")
        for resource in resources
        if not isinstance(resource.get("content"), str) or not resource["content"].strip()
    ]
    mindmap = next((r for r in resources if r.get("type") == "mindmap"), {})
    mindmap_content = mindmap.get("content", "")
    mindmap_ok = (
        isinstance(mindmap_content, str)
        and (mindmap_content.strip().startswith("mindmap") or mindmap_content.strip().startswith("- "))
    )
    passed = (
        payload.get("status") == "completed"
        and not missing
        and not leaked_fields
        and not empty_content
        and mindmap_ok
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "resource_count": len(resources),
        "resource_types": types,
        "missing_types": missing,
        "leaked_internal_fields": leaked_fields,
        "empty_content_types": empty_content,
        "mindmap_format_ok": mindmap_ok,
    }


def _task(resource_type: str, output_format_hint: str) -> dict:
    return {
        "resource_type": resource_type,
        "focus_points": ["一次函数"],
        "suggested_structure": "概念 → 性质 → 应用",
        "output_format_hint": output_format_hint,
    }


def _json(data: dict) -> str:
    return "```json\n" + json.dumps(data, ensure_ascii=False) + "\n```"


if __name__ == "__main__":
    raise SystemExit(main())
