from __future__ import annotations

import csv
import io
import json
from collections import Counter
from typing import Any

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CourseCatalog, CourseOffering
from app.models.others import CourseKnowledgeGraph, LearningPath, Resource
from app.models.quiz import QuizQuestion


MISMATCH_TYPES = {
    "exact_match_ok": "精确字段匹配命中，且人工认为合理",
    "semantic_text_mismatch": "语义应挂载，但字段文字不一致导致未命中",
    "chapter_mismatch": "知识点语义相关，但章节字段不一致导致章节资料未命中",
    "resource_metadata_missing": "资源存在，但缺 knowledge_point 或 chapter 等可匹配元数据",
    "kg_node_too_broad": "KG 节点过宽，人工无法稳定判断应挂哪些资源",
    "kg_node_too_narrow": "KG 节点过窄，资料里没有可对应的具体资源",
    "resource_content_irrelevant": "当前规则命中了候选，但人工认为内容不该挂该节点",
    "no_real_resource": "该节点当前确实没有对应真实资源或题目",
    "other": "以上类型无法覆盖，必须在 human_judgement_note 写原因",
}


NODE_ROW_FIELDS = [
    "catalog_id",
    "course_id",
    "node_id",
    "node_name",
    "chapter",
    "candidate_resource_ids",
    "candidate_quiz_ids",
    "candidate_count",
    "expected_correct_ids",
    "expected_correct_count",
    "actual_matched_correct_ids",
    "actual_matched_correct_count",
    "matched",
    "mismatch_type",
    "human_judgement_note",
    "node_source",
    "coverage_signal_count",
    "candidate_titles",
    "candidate_quiz_preview",
]


def _as_node_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _split_ids(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, list):
        return {str(item).strip() for item in value if str(item).strip()}
    return {part.strip() for part in str(value).split("|") if part.strip()}


def _join_ids(values: list[str]) -> str:
    return "|".join(values)


def _not_deleted(model: Any) -> Any:
    return model.is_deleted.is_(False)


def _matchable_resource_conditions(course_id: str) -> tuple[Any, ...]:
    return (
        Resource.course_id == course_id,
        _not_deleted(Resource),
    )


async def _count_rows(db: AsyncSession, model: Any, *conditions: Any) -> int:
    result = await db.execute(select(func.count()).select_from(model).where(*conditions))
    return int(result.scalar() or 0)


async def _count_distinct_nonempty(db: AsyncSession, column: Any, *conditions: Any) -> int:
    result = await db.execute(
        select(func.count(distinct(column))).where(column.is_not(None), column != "", *conditions)
    )
    return int(result.scalar() or 0)


async def _knowledge_graph(db: AsyncSession, course_id: str) -> CourseKnowledgeGraph | None:
    result = await db.execute(
        select(CourseKnowledgeGraph)
        .where(
            CourseKnowledgeGraph.course_id == course_id,
            _not_deleted(CourseKnowledgeGraph),
        )
        .order_by(CourseKnowledgeGraph.update_time.desc(), CourseKnowledgeGraph.create_time.desc())
    )
    return result.scalars().first()


async def _latest_learning_path(
    db: AsyncSession,
    course_id: str,
    user_id: str | None,
) -> LearningPath | None:
    query = select(LearningPath).where(
        LearningPath.course_id == course_id,
        _not_deleted(LearningPath),
    )
    if user_id:
        query = query.where(LearningPath.user_id == user_id)
    query = query.order_by(
        LearningPath.generated_at.desc(),
        LearningPath.update_time.desc(),
        LearningPath.create_time.desc(),
    )
    result = await db.execute(query)
    return result.scalars().first()


async def inventory_catalog_courses(db: AsyncSession) -> list[dict[str, Any]]:
    result = await db.execute(
        select(CourseCatalog, CourseOffering)
        .join(CourseOffering, CourseOffering.catalog_id == CourseCatalog.id)
        .where(_not_deleted(CourseCatalog), _not_deleted(CourseOffering))
        .order_by(CourseCatalog.create_time.desc(), CourseOffering.create_time.desc())
    )

    rows: list[dict[str, Any]] = []
    for catalog, offering in result.all():
        course_id = offering.id
        kg = await _knowledge_graph(db, course_id)
        latest_path = await _latest_learning_path(db, course_id, user_id=None)
        kg_node_count = len(_as_node_list(kg.nodes if kg else []))
        learning_path_node_count = len(_as_node_list(latest_path.nodes if latest_path else []))
        resource_conditions = _matchable_resource_conditions(course_id)
        quiz_conditions = (
            QuizQuestion.course_id == course_id,
            _not_deleted(QuizQuestion),
        )

        resource_count = await _count_rows(db, Resource, *resource_conditions)
        quiz_count = await _count_rows(db, QuizQuestion, *quiz_conditions)
        distinct_resource_knowledge_point_count = await _count_distinct_nonempty(
            db,
            Resource.knowledge_point,
            *resource_conditions,
        )
        distinct_resource_chapter_count = await _count_distinct_nonempty(
            db,
            Resource.chapter,
            *resource_conditions,
        )
        distinct_quiz_knowledge_point_count = await _count_distinct_nonempty(
            db,
            QuizQuestion.knowledge_point,
            *quiz_conditions,
        )
        has_metadata = (
            distinct_resource_knowledge_point_count > 0
            or distinct_resource_chapter_count > 0
            or distinct_quiz_knowledge_point_count > 0
        )

        rows.append(
            {
                "catalog_id": catalog.id,
                "catalog_title": catalog.title,
                "course_id": course_id,
                "offering_name": offering.name,
                "chunk_count": catalog.chunk_count or 0,
                "kg_node_count": kg_node_count,
                "learning_path_node_count": learning_path_node_count,
                "resource_count": resource_count,
                "distinct_resource_knowledge_point_count": distinct_resource_knowledge_point_count,
                "distinct_resource_chapter_count": distinct_resource_chapter_count,
                "quiz_count": quiz_count,
                "distinct_quiz_knowledge_point_count": distinct_quiz_knowledge_point_count,
                "eligible_for_formal_probe": (
                    max(kg_node_count, learning_path_node_count) >= 10
                    and (resource_count > 0 or quiz_count > 0)
                    and has_metadata
                ),
            }
        )
    return rows


def _merge_nodes(
    kg_nodes: list[dict[str, Any]],
    learning_path_nodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for source_name, nodes in (
        ("kg", kg_nodes),
        ("learning_path", learning_path_nodes),
    ):
        for node in nodes:
            node_id = str(node.get("id") or node.get("node_id") or node.get("name") or "").strip()
            if not node_id:
                continue
            existing = merged.setdefault(
                node_id,
                {
                    "node_id": node_id,
                    "node_name": "",
                    "chapter": "",
                    "sources": set(),
                },
            )
            existing["sources"].add(source_name)
            if not existing["node_name"]:
                existing["node_name"] = str(node.get("name") or node.get("label") or node_id)
            if not existing["chapter"] and node.get("chapter"):
                existing["chapter"] = str(node.get("chapter") or "")

    return [
        {
            "node_id": item["node_id"],
            "node_name": item["node_name"] or item["node_id"],
            "chapter": item["chapter"],
            "node_source": "+".join(sorted(item["sources"])),
        }
        for item in merged.values()
    ]


async def _resource_candidates(
    db: AsyncSession,
    course_id: str,
    node_name: str,
    chapter: str,
) -> list[Resource]:
    conditions = _matchable_resource_conditions(course_id)
    exact_match_condition = Resource.knowledge_point == node_name
    if chapter:
        exact_match_condition = exact_match_condition | (Resource.chapter == chapter)
    result = await db.execute(
        select(Resource).where(
            *conditions,
            exact_match_condition,
        )
    )
    resources = result.scalars().all()
    return sorted({resource.id: resource for resource in resources}.values(), key=lambda item: item.id)


async def _quiz_candidates(
    db: AsyncSession,
    course_id: str,
    node_name: str,
) -> list[QuizQuestion]:
    result = await db.execute(
        select(QuizQuestion).where(
            QuizQuestion.course_id == course_id,
            QuizQuestion.knowledge_point == node_name,
            _not_deleted(QuizQuestion),
        )
    )
    return sorted(result.scalars().all(), key=lambda item: item.id)


def _coverage_signal_count(
    node_name: str,
    chapter: str,
    resources: list[Resource],
    quizzes: list[QuizQuestion],
) -> int:
    needles = [value for value in (node_name, chapter) if value]
    if not needles:
        return 0

    count = 0
    for resource in resources:
        text = " ".join(
            [
                resource.title or "",
                resource.description or "",
                resource.content or "",
                resource.knowledge_point or "",
                resource.chapter or "",
            ]
        )
        if any(needle in text for needle in needles):
            count += 1
    for quiz in quizzes:
        text = " ".join([quiz.content or "", quiz.knowledge_point or "", quiz.chapter or ""])
        if any(needle in text for needle in needles):
            count += 1
    return count


async def build_probe_rows(
    db: AsyncSession,
    catalog_id: str,
    course_id: str,
    user_id: str | None = None,
    sample_mode: str = "all",
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if sample_mode not in {"all", "core"}:
        raise ValueError("sample_mode must be 'all' or 'core'")

    kg = await _knowledge_graph(db, course_id)
    latest_path = await _latest_learning_path(db, course_id, user_id=user_id)
    nodes = _merge_nodes(
        _as_node_list(kg.nodes if kg else []),
        _as_node_list(latest_path.nodes if latest_path else []),
    )

    all_resources_result = await db.execute(select(Resource).where(*_matchable_resource_conditions(course_id)))
    all_resources = list(all_resources_result.scalars().all())
    all_quizzes_result = await db.execute(
        select(QuizQuestion).where(QuizQuestion.course_id == course_id, _not_deleted(QuizQuestion))
    )
    all_quizzes = list(all_quizzes_result.scalars().all())

    rows: list[dict[str, Any]] = []
    for node in nodes:
        resources = await _resource_candidates(
            db,
            course_id,
            node["node_name"],
            node["chapter"],
        )
        quizzes = await _quiz_candidates(db, course_id, node["node_name"])
        resource_ids = [resource.id for resource in resources]
        quiz_ids = [quiz.id for quiz in quizzes]
        rows.append(
            {
                "catalog_id": catalog_id,
                "course_id": course_id,
                "node_id": node["node_id"],
                "node_name": node["node_name"],
                "chapter": node["chapter"],
                "candidate_resource_ids": _join_ids(resource_ids),
                "candidate_quiz_ids": _join_ids(quiz_ids),
                "candidate_count": len(resource_ids) + len(quiz_ids),
                "expected_correct_ids": "",
                "expected_correct_count": "",
                "actual_matched_correct_ids": "",
                "actual_matched_correct_count": "",
                "matched": "",
                "mismatch_type": "",
                "human_judgement_note": "",
                "node_source": node["node_source"],
                "coverage_signal_count": _coverage_signal_count(
                    node["node_name"],
                    node["chapter"],
                    all_resources,
                    all_quizzes,
                ),
                "candidate_titles": "|".join(resource.title for resource in resources),
                "candidate_quiz_preview": "|".join((quiz.content or "")[:80] for quiz in quizzes),
            }
        )

    if sample_mode == "core":
        rows.sort(
            key=lambda row: (
                int(row["coverage_signal_count"]),
                int(row["candidate_count"]),
                str(row["node_name"]),
            ),
            reverse=True,
        )
    if limit is not None:
        rows = rows[:limit]
    return rows


def _row_match_info(row: dict[str, Any]) -> tuple[set[str], set[str], set[str], bool]:
    candidate_ids = _split_ids(row.get("candidate_resource_ids")) | _split_ids(row.get("candidate_quiz_ids"))
    expected_ids = _split_ids(row.get("expected_correct_ids"))
    actual_matched_ids = candidate_ids & expected_ids
    return candidate_ids, expected_ids, actual_matched_ids, bool(actual_matched_ids)


def compute_annotation_summary(rows: list[dict[str, Any]], calibration: bool) -> dict[str, Any]:
    if not rows:
        return {
            "node_count": 0,
            "matched_node_count": 0,
            "exact_miss_rate": 0.0,
            "semantic_text_mismatch_miss_share": 0.0,
            "mismatch_type_distribution": {},
            "average_candidate_count": 0.0,
            "average_expected_correct_count": 0.0,
            "average_actual_matched_correct_count": 0.0,
            "largest_non_semantic_blocker_type": "",
            "largest_non_semantic_blocker_share": 0.0,
            "decision": "calibration-only" if calibration else "no-go",
            "decision_reasons": (
                ["calibration catalog does not produce go/no-go"] if calibration else ["no annotated rows"]
            ),
        }

    annotated_rows: list[dict[str, Any]] = []
    for row in rows:
        mismatch_type = str(row.get("mismatch_type") or "").strip()
        if mismatch_type not in MISMATCH_TYPES:
            raise ValueError(f"unknown mismatch_type for node {row.get('node_id')}: {mismatch_type}")
        if not str(row.get("human_judgement_note") or "").strip():
            raise ValueError(f"human_judgement_note is required for node {row.get('node_id')}")
        candidate_ids, expected_ids, actual_matched_ids, matched = _row_match_info(row)
        annotated_rows.append(
            {
                **row,
                "candidate_count": len(candidate_ids),
                "expected_correct_count": len(expected_ids),
                "actual_matched_correct_ids": _join_ids(sorted(actual_matched_ids)),
                "actual_matched_correct_count": len(actual_matched_ids),
                "matched": matched,
            }
        )

    node_count = len(annotated_rows)
    matched_node_count = sum(1 for row in annotated_rows if row["matched"])
    miss_rows = [row for row in annotated_rows if not row["matched"]]
    miss_count = len(miss_rows)
    exact_miss_rate = miss_count / node_count if node_count else 0.0
    mismatch_type_distribution = Counter(str(row["mismatch_type"]) for row in annotated_rows)
    miss_type_distribution = Counter(str(row["mismatch_type"]) for row in miss_rows)
    semantic_text_mismatch_miss_share = (
        miss_type_distribution["semantic_text_mismatch"] / miss_count if miss_count else 0.0
    )

    largest_non_semantic_blocker_type = ""
    largest_non_semantic_blocker_share = 0.0
    for mismatch_type, count in miss_type_distribution.items():
        if mismatch_type == "semantic_text_mismatch":
            continue
        share = count / miss_count if miss_count else 0.0
        if share > largest_non_semantic_blocker_share:
            largest_non_semantic_blocker_type = mismatch_type
            largest_non_semantic_blocker_share = share

    if calibration:
        decision = "calibration-only"
        decision_reasons = ["calibration catalog does not produce go/no-go"]
    else:
        decision_reasons = []
        if exact_miss_rate > 0.30:
            decision_reasons.append("exact_miss_rate > 30%")
        if semantic_text_mismatch_miss_share > 0.50:
            decision_reasons.append("semantic_text_mismatch among misses > 50%")
        if largest_non_semantic_blocker_share > 0.70:
            decision_reasons.append(f"{largest_non_semantic_blocker_type} among misses > 70%")
        decision = "no-go" if decision_reasons else "go"
        if not decision_reasons:
            decision_reasons = ["all fixed thresholds passed"]

    return {
        "node_count": node_count,
        "matched_node_count": matched_node_count,
        "exact_miss_rate": exact_miss_rate,
        "semantic_text_mismatch_miss_share": semantic_text_mismatch_miss_share,
        "mismatch_type_distribution": dict(mismatch_type_distribution),
        "average_candidate_count": sum(row["candidate_count"] for row in annotated_rows) / node_count,
        "average_expected_correct_count": (
            sum(row["expected_correct_count"] for row in annotated_rows) / node_count
        ),
        "average_actual_matched_correct_count": (
            sum(row["actual_matched_correct_count"] for row in annotated_rows) / node_count
        ),
        "largest_non_semantic_blocker_type": largest_non_semantic_blocker_type,
        "largest_non_semantic_blocker_share": largest_non_semantic_blocker_share,
        "decision": decision,
        "decision_reasons": decision_reasons,
    }


def serialize_rows_csv(rows: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=NODE_ROW_FIELDS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def serialize_rows_jsonl(rows: list[dict[str, Any]]) -> str:
    return "".join(f"{json.dumps(row, ensure_ascii=False)}\n" for row in rows)


def parse_csv_rows(csv_text: str) -> list[dict[str, Any]]:
    return list(csv.DictReader(io.StringIO(csv_text)))
