#!/usr/bin/env python3
"""CourseKnowledgeGraph 手工导入工具。

用法：
  python tools/import_knowledge_graph.py --course-id <id> --file <path>
  python tools/import_knowledge_graph.py --course-id <id> --stdin < <path>
  python tools/import_knowledge_graph.py --course-id <id> --activate-version <version>
  python tools/import_knowledge_graph.py --course-id <id> --activate-id <graph_id>

行为：创建或激活 course_knowledge_graphs 版本。
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

# 将 backend 加入 sys.path，支持从任意目录运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def build_import_result(graph) -> dict:
    """Build a stable CLI result payload from a CourseKnowledgeGraph instance."""
    return {
        "course_id": graph.course_id,
        "graph_id": graph.id,
        "version": graph.version,
        "node_count": len(graph.nodes or []),
        "edge_count": len(graph.edges or []),
        "source_type": graph.source_type,
        "generation_strategy": graph.generation_strategy,
        "metrics": graph.metrics,
        "activated": graph.is_active,
    }


async def import_knowledge_graph_version(
    course_id: str,
    nodes: list,
    edges: list,
    *,
    activate: bool = True,
    source_type: str = "manual_import",
    generation_strategy: str = "legacy_outline",
) -> dict:
    """Create a new imported KG version."""
    from app.db.session import async_session_factory
    from app.services.course_knowledge_graphs import (
        create_knowledge_graph_version,
        get_active_knowledge_graph,
    )

    async with async_session_factory() as db:
        active_graph = await get_active_knowledge_graph(db, course_id)
        metrics = {"node_count": len(nodes), "edge_count": len(edges)}
        graph = await create_knowledge_graph_version(
            db,
            course_id=course_id,
            nodes=nodes,
            edges=edges,
            source_type=source_type,
            generation_strategy=generation_strategy,
            metrics=metrics,
            activate=activate,
            parent_graph_id=active_graph.id if active_graph else None,
        )
        await db.commit()
        return build_import_result(graph)


async def activate_existing_version(
    course_id: str,
    *,
    graph_id: str | None = None,
    version: int | None = None,
) -> dict:
    """Switch active KG to an existing version."""
    from app.db.session import async_session_factory
    from app.services.course_knowledge_graphs import activate_knowledge_graph_version

    async with async_session_factory() as db:
        graph = await activate_knowledge_graph_version(
            db,
            course_id,
            graph_id=graph_id,
            version=version,
        )
        await db.commit()
        return build_import_result(graph)


def main():
    parser = argparse.ArgumentParser(description="导入 CourseKnowledgeGraph")
    parser.add_argument("--course-id", required=True, help="课程 ID")
    parser.add_argument("--no-activate", action="store_true", help="只创建历史版本，不切换 active")
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--file", help="JSON 文件路径")
    src.add_argument("--stdin", action="store_true", help="从 stdin 读取 JSON")
    src.add_argument("--activate-version", type=int, help="激活已有 KG version，不读取 JSON")
    src.add_argument("--activate-id", help="激活已有 KG graph id，不读取 JSON")
    args = parser.parse_args()

    if args.activate_version is not None or args.activate_id:
        result = asyncio.run(
            activate_existing_version(
                args.course_id,
                graph_id=args.activate_id,
                version=args.activate_version,
            )
        )
        print(
            f"Activated version {result['version']} KG {result['graph_id']} "
            f"for course {result['course_id']}"
        )
        return

    if not args.file and not args.stdin:
        parser.error("one of --file, --stdin, --activate-version, or --activate-id is required")

    if args.file:
        data = json.loads(Path(args.file).read_text())
    else:
        data = json.loads(sys.stdin.read())

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        print("ERROR: nodes/edges must be arrays", file=sys.stderr)
        sys.exit(1)

    result = asyncio.run(
        import_knowledge_graph_version(
            args.course_id,
            nodes,
            edges,
            activate=not args.no_activate,
        )
    )
    print(
        f"Created version {result['version']} KG {result['graph_id']} "
        f"for course {result['course_id']}: "
        f"{result['node_count']} nodes, {result['edge_count']} edges, "
        f"activated={result['activated']}"
    )


if __name__ == "__main__":
    main()
