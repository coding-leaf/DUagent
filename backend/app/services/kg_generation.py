from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.db.session import async_session_factory
from app.services.course_knowledge_graphs import (
    create_knowledge_graph_version,
    get_active_knowledge_graph,
)
from app.services.kg_body_grounding import (
    GroundingMatch,
    USABLE_SUPPORT_THRESHOLD,
    filter_supported_knowledge_graph,
)


class KGGenerationInputError(ValueError):
    """Raised when KG generation input cannot produce a valid graph."""

    def __init__(self, message: str, *, error_code: str = "kg_invalid_input"):
        self.error_code = error_code
        super().__init__(message)


def _chunk_text_from_payload(payload: dict[str, Any]) -> str:
    for key in ("content", "chunk_text", "text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _truncate_chunk(text: str, max_chars: int = 1200) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


async def build_catalog_kg_context(
    catalog_id: str,
    *,
    limit: int = 24,
    max_chars: int = 18000,
) -> str:
    """Build KG generation context from catalog knowledge chunks stored in Qdrant."""
    qdrant_url = os.environ.get("QDRANT_URL", "http://127.0.0.1:6333").rstrip("/")
    collection = os.environ.get(
        "QDRANT_COURSE_KNOWLEDGE_COLLECTION",
        "course_knowledge_v1_1024",
    )
    payload = {
        "filter": {
            "must": [
                {"key": "course_id", "match": {"value": catalog_id}},
            ],
        },
        "limit": limit,
        "with_payload": True,
        "with_vector": False,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{qdrant_url}/collections/{collection}/points/scroll",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        raise KGGenerationInputError(
            "Failed to read catalog knowledge chunks",
            error_code="kg_context_empty",
        ) from exc

    points = data.get("result", {}).get("points", [])
    if not isinstance(points, list):
        points = []

    chunks: list[str] = []
    used_chars = 0
    for point in points:
        if not isinstance(point, dict):
            continue
        point_payload = point.get("payload")
        if not isinstance(point_payload, dict):
            continue
        text = _truncate_chunk(_chunk_text_from_payload(point_payload))
        if not text:
            continue
        if used_chars + len(text) > max_chars:
            remaining = max_chars - used_chars
            if remaining <= 200:
                break
            text = _truncate_chunk(text, remaining)
        chunks.append(text)
        used_chars += len(text)
        if used_chars >= max_chars:
            break

    if not chunks:
        raise KGGenerationInputError(
            "No catalog knowledge chunks found for KG generation",
            error_code="kg_context_empty",
        )
    return "\n---\n".join(chunks)


async def generate_kg_from_llm(outline: str) -> dict[str, Any]:
    """Call the configured LLM to extract a course KG JSON payload from outline text."""
    api_key = os.environ.get("LLM_API_KEY") or settings.LLM_API_KEY
    base_url = os.environ.get("LLM_BASE_URL") or settings.LLM_BASE_URL
    model = os.environ.get("LLM_MODEL") or settings.LLM_MODEL
    if not api_key:
        raise KGGenerationInputError("LLM_API_KEY environment variable is not set")

    prompt = f"""You are a professional educational design expert.
Please extract a course knowledge graph from the given course material chunks or syllabus/outline.
Your output must be a valid JSON object containing "nodes" and "edges".

Requirements for nodes:
- Each node represents a knowledge point.
- Must contain fields: "id" (unique string identifier), "name" (string), and "chapter" (string).

Requirements for edges:
- Represent prerequisite relationships between nodes.
- Must contain fields: "from" (the prerequisite node ID) and "to" (the target node ID).

Course material context:
\"\"\"
{outline}
\"\"\"

Output JSON structure example:
{{
  "nodes": [
    {{"id": "node_a", "name": "Node A", "chapter": "Chapter 1"}},
    {{"id": "node_b", "name": "Node B", "chapter": "Chapter 1"}}
  ],
  "edges": [
    {{"from": "node_a", "to": "node_b"}}
  ]
}}

Ensure that the output contains ONLY the valid JSON object without any markdown formatting codeblocks or other explanations.
"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()

    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise KGGenerationInputError("Invalid LLM KG JSON response") from exc
    if not isinstance(data, dict):
        raise KGGenerationInputError("LLM response must be a JSON object")
    return data


def validate_kg_json_payload(
    data: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate and clean KG JSON nodes/edges, removing duplicates and dangling edges."""
    if not isinstance(data, dict):
        raise KGGenerationInputError("KG JSON must be an object containing nodes and edges")

    raw_nodes = data.get("nodes", [])
    raw_edges = data.get("edges", [])
    if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
        raise KGGenerationInputError("KG JSON must contain 'nodes' and 'edges' lists")

    cleaned_nodes: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for node in raw_nodes:
        if not isinstance(node, dict):
            continue

        node_id = str(node.get("id") or "").strip()
        name = str(node.get("name") or "").strip()
        chapter = str(node.get("chapter") or "").strip()
        if not node_id or not name or not chapter:
            continue
        if node_id in seen_ids:
            continue

        seen_ids.add(node_id)
        cleaned_nodes.append({"id": node_id, "name": name, "chapter": chapter})

    if not cleaned_nodes:
        raise KGGenerationInputError("No valid nodes found in KG JSON")

    cleaned_edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str]] = set()
    for edge in raw_edges:
        if not isinstance(edge, dict):
            continue

        from_id = str(edge.get("from") or "").strip()
        to_id = str(edge.get("to") or "").strip()
        if not from_id or not to_id:
            continue
        if from_id not in seen_ids or to_id not in seen_ids:
            continue

        edge_key = (from_id, to_id)
        if edge_key in seen_edges:
            continue

        seen_edges.add(edge_key)
        cleaned_edges.append({"from": from_id, "to": to_id})

    return cleaned_nodes, cleaned_edges


def load_kg_json_file(
    kg_file: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        data = json.loads(kg_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise KGGenerationInputError("Invalid KG JSON file") from exc
    return validate_kg_json_payload(data)


def load_grounding_matches(grounding_file: Path) -> list[GroundingMatch]:
    try:
        data = json.loads(grounding_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise KGGenerationInputError("Invalid grounding JSON file") from exc
    results = data.get("results") if isinstance(data, dict) else data
    if not isinstance(results, list):
        raise KGGenerationInputError("Grounding file must contain a results list")

    matches: list[GroundingMatch] = []
    for item in results:
        if not isinstance(item, dict):
            continue

        node_id = str(item.get("node_id") or "").strip()
        if not node_id:
            continue

        score_value = item.get("body_top1_score")
        score = float(score_value) if isinstance(score_value, (int, float)) else 0.0
        matches.append(
            GroundingMatch(
                node_id=node_id,
                score=score,
                chunk_id=str(item.get("chunk_id") or ""),
                content_preview=str(
                    item.get("preview") or item.get("content_preview") or ""
                ),
            )
        )
    return matches


def route_a_generation_strategy_for_threshold(threshold: float) -> str:
    if math.isclose(threshold, USABLE_SUPPORT_THRESHOLD, rel_tol=0.0, abs_tol=1e-9):
        return "route_a_prune_usable_060"
    return "route_a_prune_unsupported"


def prune_kg_with_grounding_file(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    grounding_file: Path,
    *,
    threshold: float = USABLE_SUPPORT_THRESHOLD,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    matches = load_grounding_matches(grounding_file)
    kept_nodes, kept_edges, metrics = filter_supported_knowledge_graph(
        nodes,
        edges,
        matches,
        threshold=threshold,
    )
    metrics["grounding_source_file"] = str(grounding_file)
    if not kept_nodes:
        raise KGGenerationInputError(
            "Route A pruning removed all nodes; refusing to create a knowledge graph"
        )
    return kept_nodes, kept_edges, metrics


def _build_generation_result(graph: Any) -> dict[str, Any]:
    return {
        "course_id": graph.course_id,
        "graph_id": graph.id,
        "version": graph.version,
        "node_count": len(graph.nodes or []),
        "edge_count": len(graph.edges or []),
        "source_type": graph.source_type,
        "generation_strategy": graph.generation_strategy,
        "metrics": graph.metrics or {},
        "activated": graph.is_active,
    }


async def save_knowledge_graph_version(
    course_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    source_type: str,
    generation_strategy: str,
    metrics: dict[str, Any] | None = None,
    activate: bool = True,
) -> dict[str, Any]:
    async with async_session_factory() as db:
        active_graph = await get_active_knowledge_graph(db, course_id)
        graph = await create_knowledge_graph_version(
            db,
            course_id=course_id,
            nodes=nodes,
            edges=edges,
            source_type=source_type,
            generation_strategy=generation_strategy,
            metrics=metrics or {},
            activate=activate,
            parent_graph_id=active_graph.id if active_graph else None,
        )
        await db.commit()
        return _build_generation_result(graph)


async def generate_knowledge_graph_version(
    *,
    course_id: str,
    source_type: str,
    catalog_id: str | None = None,
    outline_text: str | None = None,
    kg_json: dict[str, Any] | None = None,
    kg_file: Path | None = None,
    grounding_file: Path | None = None,
    grounding_threshold: float = USABLE_SUPPORT_THRESHOLD,
    activate: bool = True,
) -> dict[str, Any]:
    if source_type == "catalog_chunks":
        source_catalog_id = (catalog_id or "").strip()
        if not source_catalog_id:
            raise KGGenerationInputError("catalog_id is required for catalog_chunks")
        context = await build_catalog_kg_context(source_catalog_id)
        nodes, edges = validate_kg_json_payload(await generate_kg_from_llm(context))
        graph_source_type = "catalog_chunks"
        generation_strategy = "catalog_chunks_llm"
        metrics: dict[str, Any] = {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "context_char_count": len(context),
        }
    elif source_type == "outline_text":
        outline = (outline_text or "").strip()
        if not outline:
            raise KGGenerationInputError("outline_text is required")
        nodes, edges = validate_kg_json_payload(await generate_kg_from_llm(outline))
        graph_source_type = "outline_llm"
        generation_strategy = "legacy_outline"
        metrics: dict[str, Any] = {"node_count": len(nodes), "edge_count": len(edges)}
    elif source_type == "kg_json":
        if kg_json is not None:
            nodes, edges = validate_kg_json_payload(kg_json)
        elif kg_file is not None:
            nodes, edges = load_kg_json_file(kg_file)
        else:
            raise KGGenerationInputError("kg_json or kg_file is required")
        graph_source_type = "manual_import"
        generation_strategy = "manual_kg_json"
        metrics = {"node_count": len(nodes), "edge_count": len(edges)}
    else:
        raise KGGenerationInputError(f"Unsupported source_type: {source_type}")

    if grounding_file is not None:
        nodes, edges, metrics = prune_kg_with_grounding_file(
            nodes,
            edges,
            grounding_file,
            threshold=grounding_threshold,
        )
        graph_source_type = "route_a_body_grounded"
        generation_strategy = route_a_generation_strategy_for_threshold(
            grounding_threshold
        )

    return await save_knowledge_graph_version(
        course_id,
        nodes,
        edges,
        source_type=graph_source_type,
        generation_strategy=generation_strategy,
        metrics=metrics,
        activate=activate,
    )
