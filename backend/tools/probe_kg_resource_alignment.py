#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import async_session_factory
from app.services.kg_resource_alignment_probe import (
    build_probe_rows,
    compute_annotation_summary,
    inventory_catalog_courses,
    parse_csv_rows,
    serialize_rows_csv,
    serialize_rows_jsonl,
)

INVENTORY_FIELDS = [
    "catalog_id",
    "catalog_title",
    "course_id",
    "offering_name",
    "chunk_count",
    "kg_node_count",
    "learning_path_node_count",
    "resource_count",
    "distinct_resource_knowledge_point_count",
    "distinct_resource_chapter_count",
    "quiz_count",
    "distinct_quiz_knowledge_point_count",
    "eligible_for_formal_probe",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KG-Resource 对齐探针，只读盘点和节点候选导出工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory", help="盘点 catalog/course 数据底盘")
    inventory.add_argument("--format", choices=["json", "csv"], default="json")
    inventory.add_argument("--out", help="输出文件路径；不传则输出到 stdout")

    probe = subparsers.add_parser("probe", help="导出节点级候选记录表")
    probe.add_argument("--catalog-id", required=True)
    probe.add_argument("--course-id", help="教学班 course_id；不传则使用该 catalog 的第一个绑定 offering")
    probe.add_argument("--user-id", help="LearningPath 用户 id；不传则使用该课程最新 LearningPath")
    probe.add_argument("--sample-mode", choices=["all", "core"], default="all")
    probe.add_argument("--limit", type=int)
    probe.add_argument("--format", choices=["csv", "jsonl", "json"], default="csv")
    probe.add_argument("--out", required=True, help="输出 CSV/JSONL/JSON 文件路径")
    probe.add_argument("--calibration", action="store_true", help="标记 89f51 等校准样本，不用于 go/no-go")

    summarize = subparsers.add_parser("summarize", help="汇总人工标注后的节点表")
    summarize.add_argument("--annotation-file", required=True, help="人工标注后的 CSV 文件")
    summarize.add_argument("--calibration", action="store_true", help="校准样本只输出 calibration-only")
    summarize.add_argument("--out", help="输出 JSON 文件路径；不传则输出到 stdout")

    return parser


def render_output(rows: list[dict[str, Any]], output_format: str) -> str:
    if output_format == "csv":
        return serialize_rows_csv(rows)
    if output_format == "jsonl":
        return serialize_rows_jsonl(rows)
    if output_format == "json":
        return json.dumps(rows, ensure_ascii=False, indent=2) + "\n"
    raise ValueError(f"unsupported output format: {output_format}")


def render_inventory_output(rows: list[dict[str, Any]], output_format: str) -> str:
    if output_format == "csv":
        import csv
        import io

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=INVENTORY_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in INVENTORY_FIELDS})
        return output.getvalue()
    if output_format == "json":
        return json.dumps(rows, ensure_ascii=False, indent=2) + "\n"
    raise ValueError(f"unsupported inventory output format: {output_format}")


def write_text(path: str | None, text: str) -> None:
    if not path:
        print(text, end="")
        return

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")


async def resolve_course_id(catalog_id: str, course_id: str | None) -> str:
    if course_id:
        return course_id

    async with async_session_factory() as db:
        rows = await inventory_catalog_courses(db)

    for row in rows:
        if row["catalog_id"] == catalog_id:
            return str(row["course_id"])

    raise SystemExit(f"catalog has no bound course offering: {catalog_id}")


async def run_inventory(args: argparse.Namespace) -> None:
    async with async_session_factory() as db:
        rows = await inventory_catalog_courses(db)
    write_text(args.out, render_inventory_output(rows, args.format))


async def run_probe(args: argparse.Namespace) -> None:
    course_id = await resolve_course_id(args.catalog_id, args.course_id)
    async with async_session_factory() as db:
        rows = await build_probe_rows(
            db,
            catalog_id=args.catalog_id,
            course_id=course_id,
            user_id=args.user_id,
            sample_mode=args.sample_mode,
            limit=args.limit,
        )

    write_text(args.out, render_output(rows, args.format))
    label = "calibration" if args.calibration else "formal"
    print(f"wrote {len(rows)} {label} probe rows to {args.out}", file=sys.stderr)


async def run_summarize(args: argparse.Namespace) -> None:
    csv_text = Path(args.annotation_file).read_text(encoding="utf-8")
    rows = parse_csv_rows(csv_text)
    summary = compute_annotation_summary(rows, calibration=args.calibration)
    write_text(args.out, json.dumps(summary, ensure_ascii=False, indent=2) + "\n")


async def async_main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "inventory":
        await run_inventory(args)
        return
    if args.command == "probe":
        await run_probe(args)
        return
    if args.command == "summarize":
        await run_summarize(args)
        return

    parser.error(f"unsupported command: {args.command}")


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
