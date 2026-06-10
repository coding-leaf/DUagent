#!/usr/bin/env python3
"""CourseKnowledgeGraph 智能生成与导入工具（单课程临时运维工具）。

用法：
  LLM_API_KEY=your_key python tools/generate_knowledge_graph.py --course-id <id> --file <outline_path>
  LLM_API_KEY=your_key python tools/generate_knowledge_graph.py --course-id <id> --outline "大纲内容文本"
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# 将 backend 加入 sys.path，支持从任意目录运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from app.db.session import async_session_factory
from app.services.course_knowledge_graphs import (
    create_knowledge_graph_version,
    get_active_knowledge_graph,
)


async def generate_kg_from_llm(outline: str) -> dict:
    """调用大模型，利用 outline 提取 nodes 和 edges。"""
    api_key = os.environ.get("LLM_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
    model = os.environ.get("LLM_MODEL", "deepseek-chat")

    if not api_key:
        print("ERROR: LLM_API_KEY environment variable is not set.", file=sys.stderr)
        print("Please set LLM_API_KEY, LLM_BASE_URL, and LLM_MODEL in your environment.", file=sys.stderr)
        sys.exit(1)

    prompt = f"""You are a professional educational design expert.
Please extract a course knowledge graph from the given syllabus/outline.
Your output must be a valid JSON object containing "nodes" and "edges".

Requirements for nodes:
- Each node represents a knowledge point.
- Must contain fields: "id" (unique string identifier, e.g., "binary_tree_traversal"), "name" (string, the name of the knowledge point), and "chapter" (string, the chapter it belongs to).

Requirements for edges:
- Represent prerequisite relationships between nodes.
- Must contain fields: "from" (the prerequisite node ID) and "to" (the target node ID).

Outline text:
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
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }

    url = f"{base_url.rstrip('/')}/chat/completions"
    print(f"Calling LLM ({model}) via {base_url} to extract knowledge graph...")
    
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        result = resp.json()
        content = result["choices"][0]["message"]["content"].strip()
        
        # 尝试清洗 markdown 代码块（以防模型忽略 response_format 仍然返回 markdown 围栏）
        if content.startswith("```"):
            lines = content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()
            
        return json.loads(content)


def validate_and_clean_kg(data: dict) -> tuple[list[dict], list[dict]]:
    """业务校验与去重：
    1. nodes[].id/name/chapter 必填
    2. edges[].from/to 必须引用已存在的 node id
    3. 剔除重复的节点和边，去除悬空边
    """
    raw_nodes = data.get("nodes", [])
    raw_edges = data.get("edges", [])

    if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
        raise ValueError("JSON must contain 'nodes' and 'edges' lists.")

    # 1. 校验与去重 nodes
    cleaned_nodes = []
    seen_ids = set()
    for index, node in enumerate(raw_nodes):
        if not isinstance(node, dict):
            print(f"WARNING: Skipping node at index {index} because it is not a dictionary.")
            continue
        
        node_id = node.get("id")
        name = node.get("name")
        chapter = node.get("chapter")

        if not node_id or not name or not chapter:
            print(f"WARNING: Skipping node {node} because 'id', 'name', or 'chapter' is missing/empty.")
            continue

        node_id = str(node_id).strip()
        name = str(name).strip()
        chapter = str(chapter).strip()

        if node_id in seen_ids:
            print(f"WARNING: Skipping duplicate node ID: {node_id}")
            continue

        seen_ids.add(node_id)
        cleaned_nodes.append({
            "id": node_id,
            "name": name,
            "chapter": chapter
        })

    # 2. 校验 edges 并去除悬空边
    cleaned_edges = []
    seen_edges = set()
    for index, edge in enumerate(raw_edges):
        if not isinstance(edge, dict):
            print(f"WARNING: Skipping edge at index {index} because it is not a dictionary.")
            continue

        from_id = edge.get("from")
        to_id = edge.get("to")

        if not from_id or not to_id:
            print(f"WARNING: Skipping edge {edge} because 'from' or 'to' is missing/empty.")
            continue

        from_id = str(from_id).strip()
        to_id = str(to_id).strip()

        if from_id not in seen_ids or to_id not in seen_ids:
            print(f"WARNING: Skipping dangling edge: {from_id} -> {to_id} (referenced node ID does not exist)")
            continue

        edge_key = (from_id, to_id)
        if edge_key in seen_edges:
            print(f"WARNING: Skipping duplicate edge: {from_id} -> {to_id}")
            continue

        seen_edges.add(edge_key)
        cleaned_edges.append({
            "from": from_id,
            "to": to_id
        })

    return cleaned_nodes, cleaned_edges


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


async def save_knowledge_graph_version(
    course_id: str,
    nodes: list,
    edges: list,
    *,
    source_type: str = "outline_llm",
    generation_strategy: str = "legacy_outline",
    metrics: dict | None = None,
    activate: bool = True,
) -> dict:
    """Create a new versioned course knowledge graph."""
    async with async_session_factory() as db:
        active_graph = await get_active_knowledge_graph(db, course_id)
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


async def main_async():
    parser = argparse.ArgumentParser(description="CourseKnowledgeGraph 智能生成与导入运维工具")
    parser.add_argument("--course-id", required=True, help="课程 ID")
    parser.add_argument("--auto", action="store_true", help="跳过用户命令行交互，直接落库")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", "-f", help="课程大纲文本文档路径")
    src.add_argument("--outline", "-o", help="直接传入课程大纲文本")
    args = parser.parse_args()

    course_id = args.course_id

    # 读取输入大纲
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"ERROR: Outline file does not exist: {file_path}", file=sys.stderr)
            sys.exit(1)
        outline = file_path.read_text(encoding="utf-8")
    else:
        outline = args.outline

    if not outline.strip():
        print("ERROR: Syllabus/Outline content is empty.", file=sys.stderr)
        sys.exit(1)

    # 1. 调大模型生成
    try:
        raw_data = await generate_kg_from_llm(outline)
    except Exception as e:
        print(f"ERROR: Failed to call LLM or parse response: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. 校验与去重
    try:
        nodes, edges = validate_and_clean_kg(raw_data)
    except Exception as e:
        print(f"ERROR: Generated data format validation failed: {e}", file=sys.stderr)
        sys.exit(1)

    if not nodes:
        print("ERROR: No valid nodes extracted from LLM response.", file=sys.stderr)
        sys.exit(1)

    # 3. 打印预览
    print("\n================ KG EXTRACTED PREVIEW ================")
    print(f"Course ID: {course_id}")
    print(f"Nodes count: {len(nodes)}")
    for node in nodes:
        print(f"  Node: [{node['id']}] {node['name']} (Chapter: {node['chapter']})")

    print(f"\nEdges count: {len(edges)}")
    for edge in edges:
        print(f"  Dependency: {edge['from']} -> {edge['to']}")
    print("======================================================")

    # 4. 确认落库
    if not args.auto:
        try:
            confirm = input("\nDo you want to import this knowledge graph into the database? (y/n): ").strip().lower()
        except KeyboardInterrupt:
            print("\nImport cancelled by user.")
            sys.exit(0)
        if confirm != 'y':
            print("Import cancelled by user.")
            sys.exit(0)

    # 5. 落库
    metrics = {"node_count": len(nodes), "edge_count": len(edges)}
    result = await save_knowledge_graph_version(course_id, nodes, edges, metrics=metrics)
    print(
        "\nSUCCESS: Created version "
        f"{result['version']} knowledge graph {result['graph_id']} for course {course_id} "
        f"({result['node_count']} nodes, {result['edge_count']} edges, "
        f"activated={result['activated']})."
    )


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
