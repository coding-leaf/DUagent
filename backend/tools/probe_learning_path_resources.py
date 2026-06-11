#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import async_session_factory, engine
from app.models.catalog import CourseOffering
from app.services.learning_path_resource_probe import build_learning_path_resource_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LearningPath-KG 资源命中评估探针")
    parser.add_argument("--catalog-id", required=True, help="课程 catalog id")
    parser.add_argument("--course-id", help="教学班 course_id；不传则使用该 catalog 的第一个绑定 offering")
    parser.add_argument("--user-id", help="学生 user_id；不传则使用该课程最新 LearningPath")
    parser.add_argument("--out", help="输出 JSON 文件路径；不传则输出到 stdout")
    return parser


async def resolve_course_id(catalog_id: str, course_id: str | None) -> str:
    if course_id:
        return course_id

    async with async_session_factory() as db:
        result = await db.execute(
            select(CourseOffering)
            .where(CourseOffering.catalog_id == catalog_id, CourseOffering.is_deleted == False)
            .order_by(CourseOffering.create_time.desc())
        )
        offering = result.scalars().first()

    if not offering:
        raise SystemExit(f"catalog has no bound course offering: {catalog_id}")
    return offering.id


def write_json(path: str | None, payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if not path:
        print(text, end="")
        return

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")


async def async_main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        course_id = await resolve_course_id(args.catalog_id, args.course_id)
        async with async_session_factory() as db:
            report = await build_learning_path_resource_report(
                db,
                catalog_id=args.catalog_id,
                course_id=course_id,
                user_id=args.user_id,
            )

        write_json(args.out, report)
        if args.out:
            node_count = report["summary"]["learning_path_node_count"]
            coverage = report["summary"]["node_resource_coverage_ratio"]
            print(
                f"wrote LearningPath resource probe for {node_count} nodes "
                f"(coverage={coverage:.2%}) to {args.out}",
                file=sys.stderr,
            )
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
