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
        retrieval = await retrieve_course_context(
            query=knowledge_point,
            course_id=course_id,
            limit=4,
        )
        context = str(retrieval.get("context_text") or "").strip()
        prompt = build_public_resource_prompt(
            resource_type,
            chapter,
            knowledge_point,
            context,
            course_title=course_title,
        )
        response = await self._model(
            [UserMsg(name="public_resource_generator", content=prompt)]
        )
        payload = json.loads(_strip_json_fence(_response_text(response)))
        return normalize_public_asset(
            resource_type,
            payload,
            chapter=chapter,
            knowledge_point=knowledge_point,
            sources=retrieval.get("sources") or [],
        )


def build_public_resource_prompt(
    resource_type: str,
    chapter: str,
    knowledge_point: str,
    course_context: str,
    course_title: str | None = None,
) -> str:
    if resource_type not in PUBLIC_RESOURCE_TYPES:
        raise ValueError(f"unsupported_public_resource_type:{resource_type}")

    course_info = f"课程名称：{course_title}" if course_title else "课程：通用课程"

    instructions = {
        "lesson": (
            "生成标准课程讲义，使用 Markdown，包含概念、原理、易错点、"
            "小结和课程范围内的示例。整个讲义、示例和语法细节必须完全针对该课程所使用的编程语言或技术环境。"
        ),
        "diagram": (
            "选择 flowchart、sequence、mindmap、class 或 state 中最适合的一种 "
            "Mermaid 图。content 只放 Mermaid 源码，并返回 diagram_kind。注意：Mermaid 节点的文本绝不能直接包含中括号 `[`、`]`、圆括号 `()` 或双引号等 Mermaid 的语法保留操作符；如果文本中必须带有空格、数组中括号（例如 arr[i]）或特殊标点符号，必须将整个节点标签文本用双引号包围（例如 ID[\"label text with arr['i']\"]），并将所有内部双引号替换为单引号 `'`，严禁产生未转义、未包裹的括号嵌套冲突。图表的结构、术语和概念表达必须与课程技术环境（如C语言）完美契合。"
        ),
        "example": (
            "生成讲解型代码示例 Markdown，包含目标、完整代码、运行结果、"
            "逐段解释和常见错误；不要生成可判题练习。生成的代码示例和说明文字必须完全使用课程对应的主流编程语言（例如C语言），绝对不要使用其他不相干语言（如 Python）。"
        ),
    }[resource_type]
    return f"""你是课程公共资源生成器。

{course_info}
章节：{chapter}
知识点：{knowledge_point}

课程原文：
{course_context or '没有检索到可用课程原文；不要编造超出课程范围的事实。在没有检索到原文时，必须严格基于课程名称的主题环境（例如：若课程名称为“C语言”，则所有代码示例、图表、讲义概念必须 100% 使用C语言编写和讲解，绝对不能使用 Python、Java 等其他编程语言的任何内容）来进行合理的基础教学资源生成。'}

任务：{instructions}

只输出 JSON：
{{
  "title": "中文标题",
  "content": "完整内容",
  "description": "一句话说明",
  "tags": ["标签"],
  "diagram_kind": null
}}
非 diagram 类型的 diagram_kind 必须为 null。不要输出 Markdown JSON 围栏。
"""


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
