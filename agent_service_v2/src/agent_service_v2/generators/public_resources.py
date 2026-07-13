from __future__ import annotations

import json
from typing import Any

from agentscope.message import UserMsg

from agent_service_v2.schemas.resources import (
    PublicResourceAsset,
    PublicResourceDraft,
)
from agent_service_v2.tools.rag import retrieve_course_context


PUBLIC_RESOURCE_TYPES = {"lesson", "diagram", "example"}
PUBLIC_RESOURCE_INSTRUCTIONS = {
    "lesson": (
        "lesson：标准 Markdown 讲义，包含概念、原理、易错点、课程范围内示例和小结。"
    ),
    "diagram": (
        "diagram：选择最适合的 Mermaid 图；content 只放 Mermaid 源码，并填写 "
        "diagram_kind。节点标签含括号、引号、数组下标或特殊标点时必须整体用双引号包裹，"
        "内部双引号改为单引号，避免 Mermaid 语法冲突。"
    ),
    "example": (
        "example：讲解型代码示例 Markdown，包含目标、完整代码、运行结果、逐段解释和常见错误；"
        "不要生成可判题练习。代码语言必须与课程一致，不得默认使用 Python。"
    ),
}


class PublicResourceGenerator:
    def __init__(self, *, model: Any) -> None:
        if model is None:
            raise ValueError("model_required")
        self._model = model

    async def generate(
        self,
        resource_type: str,
        *,
        chapter: str,
        knowledge_point: str,
        course_id: str,
        course_title: str | None = None,
    ) -> dict[str, Any]:
        resources = await self.generate_many(
            [resource_type],
            chapter=chapter,
            knowledge_point=knowledge_point,
            course_id=course_id,
            course_title=course_title,
        )
        return resources[0]

    async def generate_many(
        self,
        resource_types: list[str],
        *,
        chapter: str,
        knowledge_point: str,
        course_id: str,
        course_title: str | None = None,
    ) -> list[dict[str, Any]]:
        requested_types = _validate_requested_types(resource_types)
        retrieval = await retrieve_course_context(
            query=knowledge_point,
            course_id=course_id,
            limit=4,
        )
        context = str(retrieval.get("context_text") or "").strip()
        prompt = build_public_resources_prompt(
            requested_types,
            chapter,
            knowledge_point,
            context,
            course_title=course_title,
        )
        for attempt in range(2):
            response = await self._model(
                [UserMsg(name="public_resource_generator", content=prompt)]
            )
            try:
                payload = json.loads(_strip_json_fence(_response_text(response)))
                return normalize_public_assets(
                    requested_types,
                    payload,
                    chapter=chapter,
                    knowledge_point=knowledge_point,
                    sources=retrieval.get("sources") or [],
                )
            except (json.JSONDecodeError, ValueError) as exc:
                if attempt == 1:
                    raise
                prompt = (
                    f"{prompt}\n\n上一次输出未通过结构校验（{type(exc).__name__}）。"
                    "重新生成完整 JSON；不要解释、不要使用代码围栏。"
                )

        raise RuntimeError("public_resource_generation_unreachable")


def build_public_resource_prompt(
    resource_type: str,
    chapter: str,
    knowledge_point: str,
    course_context: str,
    course_title: str | None = None,
) -> str:
    return build_public_resources_prompt(
        [resource_type],
        chapter,
        knowledge_point,
        course_context,
        course_title=course_title,
    )


def build_public_resources_prompt(
    resource_types: list[str],
    chapter: str,
    knowledge_point: str,
    course_context: str,
    course_title: str | None = None,
) -> str:
    requested_types = _validate_requested_types(resource_types)

    course_info = f"课程名称：{course_title}" if course_title else "课程：通用课程"
    requested_instructions = "\n".join(
        f"- {PUBLIC_RESOURCE_INSTRUCTIONS[resource_type]}"
        for resource_type in requested_types
    )
    requested_json = ", ".join(f'"{item}"' for item in requested_types)
    return f"""你是课程公共资源生成器。

{course_info}
章节：{chapter}
知识点：{knowledge_point}

课程原文：
{course_context or '没有检索到课程原文。只生成课程名称与知识点能确定的基础内容，明确避免无法从上下文确认的细节。'}

生成类型：[{requested_json}]
{requested_instructions}

质量要求：
1. 只依据课程原文、课程名称、章节和知识点，不扩展无依据事实。
2. 术语、代码语言和技术环境必须与课程一致。
3. resources 必须只包含请求类型，每种类型恰好返回一项，不得缺失或重复。
4. title、description、tags 使用简洁中文；content 提供可直接展示的完整内容。

只输出 JSON：
{{
  "resources": [
    {{
      "type": "lesson | diagram | example",
      "title": "中文标题",
      "content": "完整内容",
      "description": "一句话说明",
      "tags": ["标签"],
      "diagram_kind": null
    }}
  ]
}}
非 diagram 类型的 diagram_kind 必须为 null。不要输出 Markdown JSON 围栏。
"""


def normalize_public_assets(
    resource_types: list[str],
    payload: dict[str, Any],
    *,
    chapter: str,
    knowledge_point: str,
    sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    requested_types = _validate_requested_types(resource_types)
    raw_resources = payload.get("resources") if isinstance(payload, dict) else None
    if not isinstance(raw_resources, list):
        raise ValueError("public_resources_list_required")

    resources_by_type: dict[str, dict[str, Any]] = {}
    for raw_resource in raw_resources:
        if not isinstance(raw_resource, dict):
            raise ValueError("public_resource_object_required")
        resource_type = str(raw_resource.get("type") or "")
        if resource_type in resources_by_type:
            raise ValueError("public_resource_type_duplicated")
        resources_by_type[resource_type] = raw_resource

    if set(resources_by_type) != set(requested_types):
        raise ValueError("public_resource_types_mismatch")

    return [
        normalize_public_asset(
            resource_type,
            resources_by_type[resource_type],
            chapter=chapter,
            knowledge_point=knowledge_point,
            sources=sources,
        )
        for resource_type in requested_types
    ]


def normalize_public_asset(
    resource_type: str,
    payload: dict[str, Any],
    *,
    chapter: str,
    knowledge_point: str,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    if resource_type not in PUBLIC_RESOURCE_TYPES:
        raise ValueError(f"unsupported_public_resource_type:{resource_type}")
    draft = PublicResourceDraft.model_validate(payload)
    asset = PublicResourceAsset(
        title=draft.title,
        type=resource_type,
        format="mermaid" if resource_type == "diagram" else "markdown",
        content=draft.content,
        description=draft.description,
        chapter=chapter,
        knowledge_point=knowledge_point,
        tags=draft.tags or [chapter, knowledge_point, resource_type],
        sources=sources,
        diagram_kind=draft.diagram_kind,
    )
    return asset.model_dump()


def _validate_requested_types(resource_types: list[str]) -> list[str]:
    if not resource_types:
        raise ValueError("public_resource_types_required")
    if len(set(resource_types)) != len(resource_types):
        raise ValueError("public_resource_type_duplicated")
    unsupported = set(resource_types) - PUBLIC_RESOURCE_TYPES
    if unsupported:
        raise ValueError(
            f"unsupported_public_resource_type:{sorted(unsupported)[0]}"
        )
    return list(resource_types)


def _response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text.strip()
    blocks = getattr(response, "content", [])
    return "".join(
        block.text
        for block in blocks
        if isinstance(getattr(block, "text", None), str)
    ).strip()


def _strip_json_fence(value: str) -> str:
    stripped = value.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()
