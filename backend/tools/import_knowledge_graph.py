#!/usr/bin/env python3
"""CourseKnowledgeGraph 手工导入工具。

用法：
  python tools/import_knowledge_graph.py --course-id <id> --file <path>
  python tools/import_knowledge_graph.py --course-id <id> --stdin < <path>

行为：upsert course_knowledge_graphs 表。
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# 将 backend 加入 sys.path，支持从任意目录运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.db.session import async_session_factory
from app.models.others import CourseKnowledgeGraph


async def upsert_knowledge_graph(course_id: str, nodes: list, edges: list) -> dict:
    """Upsert 课程知识图谱，返回 {course_id, updated, node_count, edge_count}。"""
    async with async_session_factory() as db:
        result = await db.execute(
            select(CourseKnowledgeGraph).where(
                CourseKnowledgeGraph.course_id == course_id,
                CourseKnowledgeGraph.is_deleted == False,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.nodes = nodes
            existing.edges = edges
            existing.update_time = datetime.now(timezone.utc)
            updated = True
        else:
            kg = CourseKnowledgeGraph(
                course_id=course_id, nodes=nodes, edges=edges,
            )
            db.add(kg)
            updated = False

        await db.commit()
        return {
            "course_id": course_id,
            "updated": updated,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }


def main():
    parser = argparse.ArgumentParser(description="导入 CourseKnowledgeGraph")
    parser.add_argument("--course-id", required=True, help="课程 ID")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="JSON 文件路径")
    src.add_argument("--stdin", action="store_true", help="从 stdin 读取 JSON")
    args = parser.parse_args()

    if args.file:
        data = json.loads(Path(args.file).read_text())
    else:
        data = json.loads(sys.stdin.read())

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        print("ERROR: nodes/edges must be arrays", file=sys.stderr)
        sys.exit(1)

    result = asyncio.run(upsert_knowledge_graph(args.course_id, nodes, edges))
    action = "updated" if result["updated"] else "created"
    print(f"{action} KG for course {result['course_id']}: "
          f"{result['node_count']} nodes, {result['edge_count']} edges")


if __name__ == "__main__":
    main()
