#!/usr/bin/env python3
"""CourseKnowledgeGraph 智能生成与导入工具（单课程临时运维工具）。

用法：
  LLM_API_KEY=your_key python tools/generate_knowledge_graph.py --course-id <id> --file <outline_path>
  LLM_API_KEY=your_key python tools/generate_knowledge_graph.py --course-id <id> --outline "大纲内容文本"
"""
import argparse
import asyncio
import sys
from pathlib import Path

# 将 backend 加入 sys.path，支持从任意目录运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import engine
from app.services.kg_generation import (
    generate_kg_from_llm,
    load_kg_json_file,
    prune_kg_with_grounding_file,
    route_a_generation_strategy_for_threshold,
    save_knowledge_graph_version,
    validate_kg_json_payload,
)
from app.services.kg_body_grounding import (
    USABLE_SUPPORT_THRESHOLD,
)


validate_and_clean_kg = validate_kg_json_payload
load_kg_json = load_kg_json_file


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CourseKnowledgeGraph 智能生成与导入运维工具")
    parser.add_argument("--course-id", required=True, help="课程 ID")
    parser.add_argument("--auto", action="store_true", help="跳过用户命令行交互，直接落库")
    parser.add_argument("--grounding-file", type=Path, help="Agent kg_body_grounding JSON output for Route A pruning")
    parser.add_argument(
        "--grounding-threshold",
        type=float,
        default=USABLE_SUPPORT_THRESHOLD,
        help="Route A body grounding score threshold",
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", "-f", help="课程大纲文本文档路径")
    src.add_argument("--outline", "-o", help="直接传入课程大纲文本")
    src.add_argument("--kg-json", type=Path, help="直接读取现有 KG JSON，跳过 LLM 生成")
    return parser


async def main_async():
    parser = build_arg_parser()
    args = parser.parse_args()

    course_id = args.course_id

    if args.kg_json:
        try:
            nodes, edges = load_kg_json_file(args.kg_json)
        except Exception as e:
            print(f"ERROR: KG JSON validation failed: {e}", file=sys.stderr)
            sys.exit(1)
        source_type = "manual_import"
        generation_strategy = "manual_kg_json"
        metrics = {"node_count": len(nodes), "edge_count": len(edges)}
    else:
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
            nodes, edges = validate_kg_json_payload(raw_data)
        except Exception as e:
            print(f"ERROR: Generated data format validation failed: {e}", file=sys.stderr)
            sys.exit(1)
        source_type = "outline_llm"
        generation_strategy = "legacy_outline"
        metrics = {"node_count": len(nodes), "edge_count": len(edges)}

    if not nodes:
        print("ERROR: No valid nodes extracted from LLM response.", file=sys.stderr)
        sys.exit(1)

    if args.grounding_file:
        try:
            nodes, edges, metrics = prune_kg_with_grounding_file(
                nodes,
                edges,
                args.grounding_file,
                threshold=args.grounding_threshold,
            )
        except Exception as e:
            print(f"ERROR: Failed to prune KG with grounding file: {e}", file=sys.stderr)
            sys.exit(1)

        if not nodes:
            print("ERROR: Route A pruning removed all nodes; refusing to create an active KG.", file=sys.stderr)
            sys.exit(1)

        source_type = "route_a_body_grounded"
        generation_strategy = route_a_generation_strategy_for_threshold(args.grounding_threshold)

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
    result = await save_knowledge_graph_version(
        course_id,
        nodes,
        edges,
        source_type=source_type,
        generation_strategy=generation_strategy,
        metrics=metrics,
    )
    print(
        "\nSUCCESS: Created version "
        f"{result['version']} knowledge graph {result['graph_id']} for course {course_id} "
        f"({result['node_count']} nodes, {result['edge_count']} edges, "
        f"activated={result['activated']})."
    )


async def _run_cli() -> None:
    try:
        await main_async()
    finally:
        await engine.dispose()


def main():
    asyncio.run(_run_cli())


if __name__ == "__main__":
    main()
