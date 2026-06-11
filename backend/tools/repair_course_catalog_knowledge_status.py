#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.db.session import async_session_factory, engine
from app.services.course_catalog_knowledge_repair import (
    CatalogKnowledgeRepairProbe,
    repair_catalog_knowledge_status,
    recheck_catalog_knowledge_status,
)

DEFAULT_COLLECTION = "course_knowledge_v1_1024"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Recheck and optionally repair CourseCatalog knowledge_status when Qdrant chunks already exist."
    )
    parser.add_argument("--catalog-id", required=True, help="CourseCatalog ID")
    parser.add_argument(
        "--collection",
        default=os.environ.get("QDRANT_COURSE_KNOWLEDGE_COLLECTION", DEFAULT_COLLECTION),
        help="Qdrant course knowledge collection",
    )
    parser.add_argument("--qdrant-url", default=os.environ.get("QDRANT_URL"))
    parser.add_argument("--qdrant-api-key", default=os.environ.get("QDRANT_API_KEY"))
    parser.add_argument("--qdrant-path", default=os.environ.get("QDRANT_PATH", "../agent_service/qdrant_data"))
    parser.add_argument("--format", choices=["json"], default="json")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", help="Only inspect repairability")
    repair = subparsers.add_parser("repair", help="Repair dirty -> ready only when all checks pass")
    repair.add_argument("--apply", action="store_true", help="Actually update the catalog")
    return parser


def _qdrant_client(args: argparse.Namespace) -> AsyncQdrantClient:
    kwargs: dict[str, Any] = {"api_key": args.qdrant_api_key} if args.qdrant_api_key else {}
    if args.qdrant_url:
        return AsyncQdrantClient(url=args.qdrant_url, **kwargs)
    return AsyncQdrantClient(path=args.qdrant_path, **kwargs)


async def _probe_qdrant_chunks(
    catalog_id: str,
    *,
    client: AsyncQdrantClient,
    collection: str,
) -> CatalogKnowledgeRepairProbe:
    try:
        response = await client.scroll(
            collection_name=collection,
            scroll_filter=Filter(
                must=[FieldCondition(key="course_id", match=MatchValue(value=catalog_id))]
            ),
            limit=1,
            with_payload=False,
            with_vectors=False,
        )
        points = response[0] if isinstance(response, tuple) else getattr(response, "points", [])
        count = len(points or [])
        return CatalogKnowledgeRepairProbe(ok=count > 0, chunk_count=count)
    except Exception as exc:
        return CatalogKnowledgeRepairProbe(ok=False, chunk_count=0, error=str(exc)[:500])


def _render(data: Any, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    raise ValueError(f"unsupported output format: {output_format}")


async def async_main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    client = _qdrant_client(args)

    async def probe(catalog_id: str) -> CatalogKnowledgeRepairProbe:
        return await _probe_qdrant_chunks(catalog_id, client=client, collection=args.collection)

    try:
        async with async_session_factory() as db:
            if args.command == "check":
                result = await recheck_catalog_knowledge_status(
                    db,
                    args.catalog_id,
                    qdrant_probe=probe,
                )
                print(_render(asdict(result), args.format), end="")
                return 0 if result.repairable else 2

            if args.command == "repair":
                result = await repair_catalog_knowledge_status(
                    db,
                    args.catalog_id,
                    qdrant_probe=probe,
                    apply=args.apply,
                )
                print(_render(asdict(result), args.format), end="")
                return 0 if result.repaired or result.dry_run else 2

            parser.error(f"unsupported command: {args.command}")
            return 2
    finally:
        await client.close()
        await engine.dispose()


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
