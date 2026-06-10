from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Awaitable, Callable, Sequence

from agent_service.core.ai import AIProviders, get_ai_providers
from agent_service.memory.kg_body_grounding import (
    DEFAULT_GROUNDING_THRESHOLD,
    DEFAULT_PREVIEW_CHARS,
    DEFAULT_SEARCH_LIMIT,
    KgBodyGroundingResult,
    score_kg_body_grounding,
)

Scorer = Callable[..., Awaitable[list[KgBodyGroundingResult]]]
ProviderFactory = Callable[[], AIProviders]


def load_nodes(kg_file: Path) -> list[dict[str, Any]]:
    data = json.loads(kg_file.read_text(encoding="utf-8"))
    nodes = data.get("nodes") if isinstance(data, dict) else data
    if not isinstance(nodes, list):
        raise ValueError("KG file must be a JSON object with nodes list or a node list")
    if not all(isinstance(node, dict) for node in nodes):
        raise ValueError("KG nodes must be JSON objects")
    return list(nodes)


def build_grounding_payload(
    *,
    course_id: str,
    threshold: float,
    limit: int,
    results: Sequence[KgBodyGroundingResult],
) -> dict[str, Any]:
    return {
        "course_id": course_id,
        "threshold": threshold,
        "limit": limit,
        "results": [asdict(result) for result in results],
    }


async def run_grounding(
    *,
    course_id: str,
    kg_file: Path,
    output_file: Path | None = None,
    threshold: float = DEFAULT_GROUNDING_THRESHOLD,
    limit: int = DEFAULT_SEARCH_LIMIT,
    preview_chars: int = DEFAULT_PREVIEW_CHARS,
    provider_factory: ProviderFactory = get_ai_providers,
    scorer: Scorer = score_kg_body_grounding,
) -> dict[str, Any]:
    """运行 KG 节点正文支撑探针，输入 KG JSON 文件，输出可被 Backend 裁剪工具读取的 JSON。"""
    nodes = load_nodes(kg_file)
    providers = provider_factory()
    if providers.embedding is None:
        raise RuntimeError("embedding provider is required for KG body grounding")

    results = await scorer(
        course_id,
        nodes,
        providers.embedding,
        limit=limit,
        threshold=threshold,
        preview_chars=preview_chars,
    )
    payload = build_grounding_payload(
        course_id=course_id,
        threshold=threshold,
        limit=limit,
        results=results,
    )

    if output_file is not None:
        output_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Score KG nodes against non-TOC course body chunks in Qdrant."
    )
    parser.add_argument("--course-id", required=True, help="Qdrant course_id/catalog_id to search.")
    parser.add_argument("--kg-file", required=True, type=Path, help="KG JSON file or nodes JSON file.")
    parser.add_argument("--output", "-o", type=Path, help="Write grounding JSON to this file.")
    parser.add_argument("--threshold", type=float, default=DEFAULT_GROUNDING_THRESHOLD)
    parser.add_argument("--limit", type=int, default=DEFAULT_SEARCH_LIMIT)
    parser.add_argument("--preview-chars", type=int, default=DEFAULT_PREVIEW_CHARS)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = asyncio.run(
        run_grounding(
            course_id=args.course_id,
            kg_file=args.kg_file,
            output_file=args.output,
            threshold=args.threshold,
            limit=args.limit,
            preview_chars=args.preview_chars,
        )
    )
    if args.output is None:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
