"""通用课程大纲规划智能体 (Course Curriculum Planner).

该模块是 Agent Service 唯一的知识图谱规划入口，取代了旧版 ``leader_team.py`` 中
写死 "C Programming" 的课程提示词实现：

- 学科自适应：课程标题 (``course_title``) 动态注入提示词，可规划任意课程
  （数据结构、计算机网络、Python、数学、通识课等）。
- 结构化契约：严格输出 ``nodes``（``id`` / ``name`` / ``chapter`` / ``level``）
  与 ``edges``（``from`` / ``to``），与 Backend ``validate_kg_json_payload`` 契约一致。
- 拓扑自检：规划结果在返回前统一做去重、悬空边剔除与前驱环路拆除，
  保证输出必然是标准有向无环图 (DAG)。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, AsyncIterator

from agentscope.message import UserMsg
from agentscope.model import ChatResponse

from agent_service_v2.agents.model_provider import (
    AgentModelSettings,
    build_chat_model_from_settings,
)
from agent_service_v2.tools.outline_extractor import (
    extract_markdown_outline,
    summarize_outline_for_planning,
)


logger = logging.getLogger(__name__)

# 课程材料上下文上限，避免超长教材切片挤爆单次规划请求。
MAX_CONTEXT_CHARS = 24000

# 缺失章节信息时的兜底章节名，避免节点被 Backend 校验当作缺字段剔除。
_FALLBACK_CHAPTER = "课程总览"

_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)
_ID_SANITIZER_RE = re.compile(r"[^0-9a-zA-Z_\u4e00-\u9fff]+")


def text_from_chat_response(response: ChatResponse) -> str:
    """Extract plain text from an AgentScope ``ChatResponse``."""
    parts: list[str] = []
    for block in response.content:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


async def collect_model_text(
    response: ChatResponse | AsyncIterator[ChatResponse] | Any,
) -> str:
    """Normalize both streaming and non-streaming AgentScope model output to text."""
    if isinstance(response, ChatResponse):
        return text_from_chat_response(response).strip()
    if hasattr(response, "__aiter__"):
        fallback_parts: list[str] = []
        async for chunk in response:
            text = text_from_chat_response(chunk)
            if chunk.is_last:
                return text.strip()
            fallback_parts.append(text)
        return "".join(fallback_parts).strip()
    text = getattr(response, "text", "")
    return text.strip() if isinstance(text, str) else ""


def build_curriculum_prompt(
    context_text: str,
    course_title: str | None = None,
    *,
    outline_hint: str = "",
) -> str:
    """Build the discipline-agnostic curriculum planning prompt.

    Oversized material is truncated to :data:`MAX_CONTEXT_CHARS` so a huge
    textbook dump cannot blow up a single planning request. ``outline_hint`` is
    the deterministic outline produced by the built-in document extractor; it is
    injected as a structural anchor so the model follows the real table of
    contents instead of inventing chapters.
    """
    title = (course_title or "").strip()
    context = (context_text or "").strip()[:MAX_CONTEXT_CHARS]
    course_line = (
        f'Course under design: "{title}"'
        if title
        else "Course under design: infer the subject from the material below"
    )
    hint_block = ""
    if outline_hint.strip():
        hint_block = f"""
Pre-extracted outline (authoritative chapter/section skeleton, keep its order):
{outline_hint.strip()}
"""
    return f"""You are a senior curriculum architect and instructional designer.
Your job is to turn any course syllabus, textbook table of contents, or material excerpt
into a clean, teachable knowledge structure with explicit prerequisite relations.

{course_line}

Input course material:
\"\"\"
{context}
\"\"\"
{hint_block}
Design rules:
1. Infer the discipline from the course title and the material, then adapt the chapter and
   knowledge-point granularity to that discipline (programming, mathematics, engineering,
   language, humanities and general-education courses are all equally supported).
2. Order the material the way it should actually be taught. Build the structure as
   chapter -> section -> core knowledge point; every knowledge point must be teachable on its own.
3. "nodes" holds one entry per knowledge point. Each node MUST contain:
   - "id": unique short lowercase identifier built from ascii words (e.g. "pointers_basics")
   - "name": concise knowledge-point name
   - "chapter": the chapter (add the section when useful) the node belongs to
   - "level": integer teaching depth, 1 = foundational, 2 = core, 3 = advanced
4. "edges" holds prerequisite relations. Each edge MUST contain:
   - "from": id of the prerequisite node
   - "to": id of the dependent node
5. The edges MUST form a directed acyclic graph: no cycles, no self references, and both ends
   must be ids that exist in "nodes".
6. Write "name" and "chapter" in the same language as the input material (Simplified Chinese
   for Chinese material). Keep ids in ascii lowercase.
7. Do not invent topics that are absent from the material, and do not merge unrelated chapters.

Output MUST be a strict raw JSON object without markdown fences or commentary:
{{
  "nodes": [
    {{"id": "course_intro", "name": "课程导论", "chapter": "第一章 导论", "level": 1}},
    {{"id": "core_concept", "name": "核心概念", "chapter": "第一章 导论", "level": 2}}
  ],
  "edges": [
    {{"from": "course_intro", "to": "core_concept"}}
  ]
}}"""


def _load_json_object(content: str) -> dict[str, Any]:
    """Parse the model answer into a JSON object, tolerating stray markdown fences."""
    cleaned = _JSON_FENCE_RE.sub("", content or "").strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("curriculum planner did not return a JSON object")
        try:
            data = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(f"curriculum planner returned invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("curriculum planner response must be a JSON object")
    return data


def _normalize_id(raw: Any, index: int) -> str:
    text = _ID_SANITIZER_RE.sub("_", str(raw or "").strip()).strip("_").lower()
    return text or f"node_{index + 1}"


def _normalize_level(raw: Any) -> int:
    try:
        level = int(raw)
    except (TypeError, ValueError):
        return 1
    return max(1, min(level, 5))


def _normalize_edges(
    raw_edges: Any,
    node_ids: set[str],
    id_remap: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    """Keep only edges whose endpoints resolve to real nodes.

    ``id_remap`` maps the raw (pre-sanitization) node ids to their normalized
    form so a model that labels nodes ``"1.1"`` or ``"Ch-1"`` does not silently
    lose every dependency edge that references the un-sanitized id.
    """
    if not isinstance(raw_edges, list):
        return []
    remap = id_remap or {}

    def resolve(raw: Any) -> str:
        text = str(raw or "").strip()
        if not text:
            return ""
        if text in node_ids:
            return text
        return remap.get(text, "")

    edges: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw_edge in raw_edges:
        if not isinstance(raw_edge, dict):
            continue
        from_id = resolve(raw_edge.get("from"))
        to_id = resolve(raw_edge.get("to"))
        if not from_id or not to_id or from_id == to_id:
            continue
        key = (from_id, to_id)
        if key in seen:
            continue
        seen.add(key)
        edges.append({"from": from_id, "to": to_id})
    return edges


def _find_back_edge(
    node_ids: list[str],
    edges: list[dict[str, str]],
) -> tuple[str, str] | None:
    """Return the first DFS back edge (a cycle-closing dependency), if any."""
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for edge in edges:
        adjacency.setdefault(edge["from"], []).append(edge["to"])

    white, gray, black = 0, 1, 2
    color: dict[str, int] = {node_id: white for node_id in node_ids}
    for start in node_ids:
        if color.get(start, black) != white:
            continue
        color[start] = gray
        stack: list[tuple[str, Any]] = [(start, iter(adjacency.get(start, [])))]
        while stack:
            node, children = stack[-1]
            advanced = False
            for child in children:
                child_color = color.get(child, black)
                if child_color == gray:
                    return (node, child)
                if child_color == white:
                    color[child] = gray
                    stack.append((child, iter(adjacency.get(child, []))))
                    advanced = True
                    break
            if not advanced:
                color[node] = black
                stack.pop()
    return None


def graph_is_acyclic(nodes: list[dict[str, Any]], edges: list[dict[str, str]]) -> bool:
    """Whether the prerequisite graph contains no dependency cycle."""
    node_ids = [str(node.get("id") or "") for node in nodes]
    return _find_back_edge(node_ids, edges) is None


def break_cycles(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Drop the minimal set of cycle-closing edges so the graph becomes a DAG."""
    node_ids = [str(node.get("id") or "") for node in nodes]
    remaining = list(edges)
    while True:
        back_edge = _find_back_edge(node_ids, remaining)
        if back_edge is None:
            return remaining
        logger.warning(
            "Curriculum planner produced a cyclic dependency %s -> %s; dropping it",
            back_edge[0],
            back_edge[1],
        )
        remaining = [
            edge
            for edge in remaining
            if (edge["from"], edge["to"]) != back_edge
        ]


def normalize_knowledge_graph(payload: Any) -> dict[str, Any]:
    """Normalize a raw planner payload into a clean, acyclic curriculum graph.

    Raises:
        ValueError: when the payload has no usable node.
    """
    if not isinstance(payload, dict):
        raise ValueError("curriculum graph payload must be a JSON object")

    raw_nodes = payload.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise ValueError("curriculum graph must contain a non-empty 'nodes' list")

    nodes: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    id_remap: dict[str, str] = {}
    for index, raw_node in enumerate(raw_nodes):
        if not isinstance(raw_node, dict):
            continue
        name = str(raw_node.get("name") or "").strip()
        if not name:
            continue
        node_id = _normalize_id(raw_node.get("id"), index)
        if node_id in seen_ids:
            continue
        seen_ids.add(node_id)
        raw_id = str(raw_node.get("id") or "").strip()
        if raw_id:
            id_remap.setdefault(raw_id, node_id)
        nodes.append(
            {
                "id": node_id,
                "name": name,
                "chapter": str(raw_node.get("chapter") or "").strip() or _FALLBACK_CHAPTER,
                "level": _normalize_level(raw_node.get("level")),
            }
        )

    if not nodes:
        raise ValueError("curriculum graph contains no usable nodes")

    edges = break_cycles(
        nodes,
        _normalize_edges(payload.get("edges"), seen_ids, id_remap),
    )
    return {"nodes": nodes, "edges": edges}


def extract_planning_hint(context_text: str) -> str:
    """Run the built-in outline extractor and return a compact structural hint.

    Only Markdown-style material yields a hint; plain prose returns an empty
    string so the planner falls back to reasoning over the raw context.
    """
    try:
        outline = extract_markdown_outline(context_text)
    except Exception as exc:  # pragma: no cover - defensive, extractor is pure
        logger.warning("Outline extraction failed, falling back to raw context: %s", exc)
        return ""
    if outline.get("error"):
        return ""
    return summarize_outline_for_planning(outline)


class CourseCurriculumPlanner:
    """Discipline-agnostic course curriculum planner backed by AgentScope 2.x models."""

    def __init__(
        self,
        settings: AgentModelSettings,
        *,
        model: Any | None = None,
    ) -> None:
        self.settings = settings
        self.model = (
            model
            if model is not None
            else build_chat_model_from_settings(settings, stream=False)
        )

    async def plan_curriculum(
        self,
        context_text: str,
        *,
        course_title: str | None = None,
    ) -> dict[str, Any]:
        """Plan a course knowledge graph (nodes + prerequisite DAG) from outline text."""
        context = (context_text or "").strip()
        if not context:
            raise ValueError("curriculum context must not be empty")
        if not self.model:
            raise RuntimeError("LLM Model not configured in agent_service_v2")

        prompt = build_curriculum_prompt(
            context,
            course_title,
            outline_hint=extract_planning_hint(context),
        )
        response = await self.model(
            [UserMsg(name="course_curriculum_planner", content=prompt)]
        )
        content = await collect_model_text(response)
        graph = normalize_knowledge_graph(_load_json_object(content))
        logger.info(
            "Curriculum planner produced %d nodes / %d edges for course=%s",
            len(graph["nodes"]),
            len(graph["edges"]),
            course_title or "<inferred>",
        )
        return graph


async def run_curriculum_kg_generation(
    settings: AgentModelSettings,
    context_text: str,
    *,
    course_title: str | None = None,
) -> dict[str, Any]:
    """Entry point used by the knowledge-graph generation API."""
    planner = CourseCurriculumPlanner(settings)
    return await planner.plan_curriculum(context_text, course_title=course_title)
