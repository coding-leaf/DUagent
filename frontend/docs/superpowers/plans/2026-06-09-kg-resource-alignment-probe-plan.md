# KG-Resource Alignment Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only backend probe that inventories real catalog/course data, exports KG/LearningPath node candidate matches, and summarizes human annotations into a fixed go/no-go decision for the current exact-match resource mounting rule.

**Architecture:** Add a backend-only service plus CLI under `../backend` with no API route, no OpenAPI change, no frontend UI change, and no production mock data. The probe reads existing SQLAlchemy models, emits CSV/JSONL artifacts for human review, and validates summary thresholds after annotation. Tests use SQLite fixtures and cover inventory, exact candidate extraction, annotation validation, and go/no-go math.

**Tech Stack:** Python 3.12, FastAPI backend package imports, SQLAlchemy async sessions, argparse, csv/json standard library, pytest.

---

## Pre-Modification Review Required By AGENTS.md

### 1. Problem Analysis

The spec says the next step is not `KG ready gate` and not a matching algorithm change. Current code proves `GET /api/v1/learning-path/nodes/{node_id}/resources` mounts content through exact field equality:

- `Resource.knowledge_point == node_name`
- `QuizQuestion.knowledge_point == node_name`
- `Resource.chapter == chapter`

There is no `rank`, `score`, `similarity`, or explicit ordering contract. Therefore the implementation must produce an alignment probe for the current exact-match rule, not a top-k ranking evaluation and not a semantic search feature.

The probe has three required phases:

- inventory real catalog/course data and decide whether a second formal catalog has enough data;
- export node-level candidate rows for `89f51dfbdedc4995` and a second catalog;
- summarize human annotations with fixed thresholds: exact miss rate `<= 30%`, semantic-text mismatch among misses `<= 50%`, and no non-semantic single blocker type over `70%` of misses.

### 2. Planned File Changes

- Create `../backend/app/services/kg_resource_alignment_probe.py`
  - Pure read-only probe functions.
  - SQLAlchemy queries for inventory and node candidate extraction.
  - CSV/JSONL serialization helpers.
  - Annotation validation and go/no-go summary calculation.
- Create `../backend/tools/probe_kg_resource_alignment.py`
  - CLI entry point with `inventory`, `probe`, and `summarize` subcommands.
  - Uses `async_session_factory`.
  - Writes reports only to explicit output paths.
- Create `../backend/tests/test_kg_resource_alignment_probe.py`
  - SQLite-backed tests for service behavior and CLI-safe summary logic.
- Modify `WORKFLOW.md`
  - Record implementation, verification commands, OpenAPI non-drift, and commit info after execution.

### 3. Modification Approach

- Keep all implementation inside backend service/tool files; do not add routes, schemas, frontend calls, or Agent calls.
- Query existing tables only: `course_catalogs`, `course_offerings`, `course_knowledge_graphs`, `learning_paths`, `resources`, `quiz_questions`.
- Treat `full_exercise_set` as out of scope for candidate matching, matching the spec.
- Export node rows with the exact spec fields plus small diagnostic fields that make manual annotation easier: `node_source`, `coverage_signal_count`, `candidate_titles`, and `candidate_quiz_preview`.
- Require humans to fill `expected_correct_ids`, `mismatch_type`, and `human_judgement_note` before `summarize` produces go/no-go.
- Validate `mismatch_type` against the closed list; fail fast on unknown labels.
- Keep 89f51 calibration separate from formal summary: the CLI supports `--calibration` and refuses go/no-go summary when `--calibration` is set.

### 4. Possibly Affected Features

- No runtime feature should change. This is a read-only tool.
- Backend imports may be affected if the new service imports models incorrectly; tests cover importability.
- Database load may increase during live probing; the CLI uses bounded queries and explicit catalog/course filters.
- Report files may contain resource titles/content previews; write them under an explicit local path such as `/tmp/kg-resource-probe/` or a user-approved report directory.

### 5. Planned Test Commands

Run from `/home/yezisama/workspace/workflow/EDUagent/backend`:

```bash
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/kg_resource_probe_test.db pytest tests/test_kg_resource_alignment_probe.py -q
python tools/probe_kg_resource_alignment.py --help
python tools/probe_kg_resource_alignment.py inventory --format json --out /tmp/kg-resource-probe-inventory.json
python tools/probe_kg_resource_alignment.py probe --catalog-id 89f51dfbdedc4995 --calibration --format csv --out /tmp/kg-resource-probe-89f51.csv
```

Run from `/home/yezisama/workspace/workflow/EDUagent/frontend` after only docs/plan changes:

```bash
git status --short
```

No `npm run lint` or `npm run build` is required for this plan document itself. If implementation touches frontend later, run those commands then.

## Scope

In scope:

- A read-only backend probe service.
- A backend CLI for inventory, node candidate export, and annotation summary.
- SQLite tests with seeded catalog/course/KG/LearningPath/resource/quiz data.
- CSV and JSONL output formats.
- Fixed mismatch labels and go/no-go thresholds from the spec.
- Calibration handling for `89f51dfbdedc4995`.
- `WORKFLOW.md` update after implementation.
- One concise Chinese commit after each completed implementation batch.

Out of scope:

- New semantic matching.
- New ranking score.
- New LearningPath refresh UI.
- New KG ready gate.
- New API routes or OpenAPI updates.
- Backend node resource endpoint behavior changes.
- Agent Service changes.
- Frontend page changes.
- Production mocks or fake task/resource states.

## Contract Facts To Preserve

- Node resource mounting remains exact equality in current production endpoint.
- `full_exercise_set` is a course-level fallback and is excluded from node-level `candidate_count`.
- `89f51dfbdedc4995` is calibration only: export rows, but do not produce formal hit-rate summary or go/no-go.
- Formal go/no-go comes only from a second catalog with enough nodes/resources.
- A node counts as `matched=true` when at least one manually expected correct item is in the exact candidates.
- Partial hit information must remain visible through `expected_correct_count` and `actual_matched_correct_count`.

## File Structure

Backend:

- Create `../backend/app/services/kg_resource_alignment_probe.py`
  - Responsibility: all reusable probe logic, model queries, row construction, serialization, and summary math.
- Create `../backend/tools/probe_kg_resource_alignment.py`
  - Responsibility: CLI parsing, session creation, command dispatch, stdout/file output.
- Create `../backend/tests/test_kg_resource_alignment_probe.py`
  - Responsibility: focused regression tests for probe behavior.

Frontend docs:

- Modify `WORKFLOW.md`
  - Responsibility: record what was implemented and verified.

---

### Task 1: Backend Probe Service

**Files:**
- Create: `../backend/app/services/kg_resource_alignment_probe.py`
- Test: `../backend/tests/test_kg_resource_alignment_probe.py`

- [ ] **Step 1: Write failing tests for inventory, candidate extraction, and summary thresholds**

Create `../backend/tests/test_kg_resource_alignment_probe.py` with this content:

```python
import asyncio
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import delete

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_kg_resource_probe.db",
)

from app.db.session import async_session_factory, init_db
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.course import Course
from app.models.others import CourseKnowledgeGraph, LearningPath, Resource
from app.models.quiz import QuizQuestion
from app.services.kg_resource_alignment_probe import (
    MISMATCH_TYPES,
    build_probe_rows,
    compute_annotation_summary,
    inventory_catalog_courses,
    serialize_rows_csv,
)

asyncio.run(init_db())


@pytest.fixture(autouse=True)
async def clean_db():
    async with async_session_factory() as db:
        for model in [
            QuizQuestion,
            Resource,
            LearningPath,
            CourseKnowledgeGraph,
            CourseOffering,
            CourseCatalog,
            Course,
        ]:
            await db.execute(delete(model))
        await db.commit()
    yield
    async with async_session_factory() as db:
        for model in [
            QuizQuestion,
            Resource,
            LearningPath,
            CourseKnowledgeGraph,
            CourseOffering,
            CourseCatalog,
            Course,
        ]:
            await db.execute(delete(model))
        await db.commit()


async def seed_probe_data():
    async with async_session_factory() as db:
        catalog = CourseCatalog(
            id="catalog_probe",
            title="Probe Catalog",
            status="ready",
            knowledge_status="ready",
            material_count=2,
            chunk_count=12,
        )
        course = Course(
            id="course_probe",
            name="Probe Course",
            description="Probe Course",
            teacher_id="teacher_probe",
            course_code="PROBE1",
        )
        offering = CourseOffering(
            id="course_probe",
            name="Probe Course",
            catalog_id="catalog_probe",
            teacher_id="teacher_probe",
            class_code="PROBE1",
        )
        kg = CourseKnowledgeGraph(
            id="kg_probe",
            course_id="course_probe",
            nodes=[
                {"id": "node_1", "name": "AVL树旋转", "chapter": "平衡树"},
                {"id": "node_2", "name": "红黑树性质", "chapter": "平衡树"},
                {"id": "node_3", "name": "B树索引", "chapter": "数据库索引"},
            ],
            edges=[],
        )
        lp = LearningPath(
            id="lp_probe",
            user_id="student_probe",
            course_id="course_probe",
            nodes=[
                {"id": "node_1", "name": "AVL树旋转", "status": "in_progress"},
                {"id": "node_2", "name": "红黑树性质", "status": "locked"},
            ],
            edges=[],
            current_node_id="node_1",
            current_node_name="AVL树旋转",
        )
        resources = [
            Resource(
                id="res_exact",
                course_id="course_probe",
                title="AVL旋转讲解",
                type="document",
                chapter="平衡树",
                knowledge_point="AVL树旋转",
                content="AVL树旋转需要 LL、RR、LR、RL 四类处理。",
                is_deleted=False,
            ),
            Resource(
                id="res_chapter",
                course_id="course_probe",
                title="平衡树章节材料",
                type="reading",
                chapter="平衡树",
                knowledge_point="",
                content="平衡树包含 AVL 树和红黑树。",
                is_deleted=False,
            ),
            Resource(
                id="res_deleted",
                course_id="course_probe",
                title="已删除资料",
                type="document",
                chapter="平衡树",
                knowledge_point="AVL树旋转",
                content="不应出现在候选中。",
                is_deleted=True,
            ),
        ]
        quizzes = [
            QuizQuestion(
                id="quiz_exact",
                course_id="course_probe",
                chapter="平衡树",
                knowledge_point="AVL树旋转",
                type="single_choice",
                content="AVL 树什么时候需要旋转？",
                correct_answer="失衡时",
                is_deleted=False,
            ),
            QuizQuestion(
                id="quiz_deleted",
                course_id="course_probe",
                chapter="平衡树",
                knowledge_point="AVL树旋转",
                type="single_choice",
                content="删除题不应出现",
                correct_answer="A",
                is_deleted=True,
            ),
        ]
        db.add_all([catalog, course, offering, kg, lp, *resources, *quizzes])
        await db.commit()


@pytest.mark.asyncio
async def test_inventory_catalog_courses_counts_bound_catalog_data():
    await seed_probe_data()

    async with async_session_factory() as db:
        rows = await inventory_catalog_courses(db)

    row = next(item for item in rows if item["catalog_id"] == "catalog_probe")
    assert row["course_id"] == "course_probe"
    assert row["chunk_count"] == 12
    assert row["kg_node_count"] == 3
    assert row["learning_path_node_count"] == 2
    assert row["resource_count"] == 2
    assert row["distinct_resource_knowledge_point_count"] == 1
    assert row["distinct_resource_chapter_count"] == 1
    assert row["quiz_count"] == 1
    assert row["distinct_quiz_knowledge_point_count"] == 1
    assert row["eligible_for_formal_probe"] is True


@pytest.mark.asyncio
async def test_build_probe_rows_uses_exact_candidates_and_excludes_full_exercise_set():
    await seed_probe_data()

    async with async_session_factory() as db:
        rows = await build_probe_rows(
            db,
            catalog_id="catalog_probe",
            course_id="course_probe",
            user_id="student_probe",
            sample_mode="all",
            limit=None,
        )

    by_id = {row["node_id"]: row for row in rows}
    node_1 = by_id["node_1"]
    assert node_1["node_name"] == "AVL树旋转"
    assert node_1["chapter"] == "平衡树"
    assert set(node_1["candidate_resource_ids"].split("|")) == {"res_exact", "res_chapter"}
    assert node_1["candidate_quiz_ids"] == "quiz_exact"
    assert node_1["candidate_count"] == 3
    assert "quiz_deleted" not in node_1["candidate_quiz_ids"]
    assert "res_deleted" not in node_1["candidate_resource_ids"]

    node_3 = by_id["node_3"]
    assert node_3["node_source"] == "kg"
    assert node_3["candidate_resource_ids"] == ""
    assert node_3["candidate_quiz_ids"] == ""
    assert node_3["candidate_count"] == 0


def test_compute_annotation_summary_applies_fixed_no_go_thresholds():
    rows = [
        {
            "node_id": "n1",
            "candidate_resource_ids": "res_1",
            "candidate_quiz_ids": "",
            "expected_correct_ids": "res_1",
            "mismatch_type": "exact_match_ok",
            "human_judgement_note": "精确匹配合理",
        },
        {
            "node_id": "n2",
            "candidate_resource_ids": "",
            "candidate_quiz_ids": "",
            "expected_correct_ids": "res_2",
            "mismatch_type": "semantic_text_mismatch",
            "human_judgement_note": "语义上应挂但字段文字不同",
        },
        {
            "node_id": "n3",
            "candidate_resource_ids": "",
            "candidate_quiz_ids": "",
            "expected_correct_ids": "res_3",
            "mismatch_type": "resource_metadata_missing",
            "human_judgement_note": "资源缺知识点元数据",
        },
    ]

    summary = compute_annotation_summary(rows, calibration=False)

    assert summary["node_count"] == 3
    assert summary["matched_node_count"] == 1
    assert summary["exact_miss_rate"] == pytest.approx(2 / 3)
    assert summary["semantic_text_mismatch_miss_share"] == pytest.approx(0.5)
    assert summary["decision"] == "no-go"
    assert summary["decision_reasons"] == ["exact_miss_rate > 30%"]


def test_compute_annotation_summary_refuses_calibration_go_no_go():
    rows = [
        {
            "node_id": "n1",
            "candidate_resource_ids": "res_1",
            "candidate_quiz_ids": "",
            "expected_correct_ids": "res_1",
            "mismatch_type": "exact_match_ok",
            "human_judgement_note": "校准样本",
        }
    ]

    summary = compute_annotation_summary(rows, calibration=True)

    assert summary["decision"] == "calibration-only"
    assert summary["decision_reasons"] == ["calibration catalog does not produce go/no-go"]


def test_compute_annotation_summary_rejects_unknown_mismatch_type():
    rows = [
        {
            "node_id": "n1",
            "candidate_resource_ids": "",
            "candidate_quiz_ids": "",
            "expected_correct_ids": "res_1",
            "mismatch_type": "自由发挥标签",
            "human_judgement_note": "不应通过",
        }
    ]

    with pytest.raises(ValueError, match="unknown mismatch_type"):
        compute_annotation_summary(rows, calibration=False)


def test_serialize_rows_csv_contains_annotation_columns():
    rows = [
        {
            "catalog_id": "catalog_probe",
            "course_id": "course_probe",
            "node_id": "node_1",
            "node_name": "AVL树旋转",
            "chapter": "平衡树",
            "candidate_resource_ids": "res_exact|res_chapter",
            "candidate_quiz_ids": "quiz_exact",
            "candidate_count": 3,
            "expected_correct_ids": "",
            "expected_correct_count": "",
            "actual_matched_correct_ids": "",
            "actual_matched_correct_count": "",
            "matched": "",
            "mismatch_type": "",
            "human_judgement_note": "",
            "node_source": "learning_path+kg",
            "coverage_signal_count": 3,
            "candidate_titles": "AVL旋转讲解|平衡树章节材料",
            "candidate_quiz_preview": "AVL 树什么时候需要旋转？",
        }
    ]

    csv_text = serialize_rows_csv(rows)

    assert "expected_correct_ids" in csv_text
    assert "mismatch_type" in csv_text
    assert "res_exact|res_chapter" in csv_text
    assert "AVL树旋转" in csv_text
    assert MISMATCH_TYPES["exact_match_ok"] == "精确字段匹配命中，且人工认为合理"
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run from `/home/yezisama/workspace/workflow/EDUagent/backend`:

```bash
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/kg_resource_probe_test.db pytest tests/test_kg_resource_alignment_probe.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.kg_resource_alignment_probe'`.

- [ ] **Step 3: Implement the read-only probe service**

Create `../backend/app/services/kg_resource_alignment_probe.py`:

```python
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


async def _count_distinct_nonempty(db: AsyncSession, column: Any, *conditions: Any) -> int:
    result = await db.execute(
        select(func.count(distinct(column))).where(column != "", *conditions)
    )
    return int(result.scalar() or 0)


async def _count_rows(db: AsyncSession, model: Any, *conditions: Any) -> int:
    result = await db.execute(select(func.count()).select_from(model).where(*conditions))
    return int(result.scalar() or 0)


async def _latest_learning_path(db: AsyncSession, course_id: str, user_id: str | None) -> LearningPath | None:
    query = select(LearningPath).where(
        LearningPath.course_id == course_id,
        LearningPath.is_deleted == False,
    )
    if user_id:
        query = query.where(LearningPath.user_id == user_id)
    query = query.order_by(LearningPath.generated_at.desc(), LearningPath.create_time.desc())
    result = await db.execute(query)
    return result.scalars().first()


async def _knowledge_graph(db: AsyncSession, course_id: str) -> CourseKnowledgeGraph | None:
    result = await db.execute(
        select(CourseKnowledgeGraph).where(
            CourseKnowledgeGraph.course_id == course_id,
            CourseKnowledgeGraph.is_deleted == False,
        )
    )
    return result.scalars().first()


async def inventory_catalog_courses(db: AsyncSession) -> list[dict[str, Any]]:
    result = await db.execute(
        select(CourseCatalog, CourseOffering)
        .join(CourseOffering, CourseOffering.catalog_id == CourseCatalog.id)
        .where(CourseCatalog.is_deleted == False, CourseOffering.is_deleted == False)
        .order_by(CourseCatalog.create_time.desc(), CourseOffering.create_time.desc())
    )
    pairs = result.all()
    rows: list[dict[str, Any]] = []
    for catalog, offering in pairs:
        course_id = offering.id
        kg = await _knowledge_graph(db, course_id)
        lp = await _latest_learning_path(db, course_id, user_id=None)
        resource_count = await _count_rows(
            db,
            Resource,
            Resource.course_id == course_id,
            Resource.is_deleted == False,
        )
        quiz_count = await _count_rows(
            db,
            QuizQuestion,
            QuizQuestion.course_id == course_id,
            QuizQuestion.is_deleted == False,
        )
        kg_node_count = len(_as_node_list(kg.nodes if kg else []))
        learning_path_node_count = len(_as_node_list(lp.nodes if lp else []))
        distinct_resource_kp_count = await _count_distinct_nonempty(
            db,
            Resource.knowledge_point,
            Resource.course_id == course_id,
            Resource.is_deleted == False,
        )
        distinct_resource_chapter_count = await _count_distinct_nonempty(
            db,
            Resource.chapter,
            Resource.course_id == course_id,
            Resource.is_deleted == False,
        )
        distinct_quiz_kp_count = await _count_distinct_nonempty(
            db,
            QuizQuestion.knowledge_point,
            QuizQuestion.course_id == course_id,
            QuizQuestion.is_deleted == False,
        )
        node_count_for_sampling = max(kg_node_count, learning_path_node_count)
        has_matchable_metadata = (
            distinct_resource_kp_count > 0
            or distinct_resource_chapter_count > 0
            or distinct_quiz_kp_count > 0
        )
        rows.append({
            "catalog_id": catalog.id,
            "course_id": course_id,
            "catalog_title": catalog.title,
            "offering_name": offering.name,
            "chunk_count": catalog.chunk_count or 0,
            "kg_node_count": kg_node_count,
            "learning_path_node_count": learning_path_node_count,
            "resource_count": resource_count,
            "distinct_resource_knowledge_point_count": distinct_resource_kp_count,
            "distinct_resource_chapter_count": distinct_resource_chapter_count,
            "quiz_count": quiz_count,
            "distinct_quiz_knowledge_point_count": distinct_quiz_kp_count,
            "eligible_for_formal_probe": (
                node_count_for_sampling >= 10
                and (resource_count > 0 or quiz_count > 0)
                and has_matchable_metadata
            ),
        })
    return rows


def _merge_nodes(kg_nodes: list[dict[str, Any]], lp_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for source_name, nodes in [("kg", kg_nodes), ("learning_path", lp_nodes)]:
        for node in nodes:
            node_id = str(node.get("id") or node.get("node_id") or node.get("name") or "").strip()
            if not node_id:
                continue
            existing = merged.setdefault(node_id, {
                "node_id": node_id,
                "node_name": "",
                "chapter": "",
                "sources": set(),
            })
            existing["sources"].add(source_name)
            if not existing["node_name"]:
                existing["node_name"] = str(node.get("name") or node.get("label") or node_id)
            if source_name == "kg" and node.get("chapter"):
                existing["chapter"] = str(node.get("chapter") or "")
    result: list[dict[str, Any]] = []
    for item in merged.values():
        result.append({
            "node_id": item["node_id"],
            "node_name": item["node_name"] or item["node_id"],
            "chapter": item["chapter"],
            "node_source": "+".join(sorted(item["sources"])),
        })
    return result


async def _resources_by_knowledge_point(db: AsyncSession, course_id: str, node_name: str) -> list[Resource]:
    result = await db.execute(
        select(Resource).where(
            Resource.course_id == course_id,
            Resource.knowledge_point == node_name,
            Resource.is_deleted == False,
        )
    )
    return list(result.scalars().all())


async def _resources_by_chapter(db: AsyncSession, course_id: str, chapter: str) -> list[Resource]:
    if not chapter:
        return []
    result = await db.execute(
        select(Resource).where(
            Resource.course_id == course_id,
            Resource.chapter == chapter,
            Resource.is_deleted == False,
        )
    )
    return list(result.scalars().all())


async def _quizzes_by_knowledge_point(db: AsyncSession, course_id: str, node_name: str) -> list[QuizQuestion]:
    result = await db.execute(
        select(QuizQuestion).where(
            QuizQuestion.course_id == course_id,
            QuizQuestion.knowledge_point == node_name,
            QuizQuestion.is_deleted == False,
        )
    )
    return list(result.scalars().all())


def _coverage_signal(node_name: str, chapter: str, resources: list[Resource], quizzes: list[QuizQuestion]) -> int:
    needle_values = [value for value in [node_name, chapter] if value]
    count = 0
    for resource in resources:
        text = " ".join([
            resource.title or "",
            resource.description or "",
            resource.content or "",
            resource.knowledge_point or "",
            resource.chapter or "",
        ])
        if any(needle in text for needle in needle_values):
            count += 1
    for quiz in quizzes:
        text = " ".join([
            quiz.content or "",
            quiz.knowledge_point or "",
            quiz.chapter or "",
        ])
        if any(needle in text for needle in needle_values):
            count += 1
    return count


async def build_probe_rows(
    db: AsyncSession,
    *,
    catalog_id: str,
    course_id: str,
    user_id: str | None = None,
    sample_mode: str = "all",
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if sample_mode not in {"all", "core"}:
        raise ValueError("sample_mode must be 'all' or 'core'")

    kg = await _knowledge_graph(db, course_id)
    lp = await _latest_learning_path(db, course_id, user_id=user_id)
    nodes = _merge_nodes(
        _as_node_list(kg.nodes if kg else []),
        _as_node_list(lp.nodes if lp else []),
    )

    all_resources_result = await db.execute(
        select(Resource).where(Resource.course_id == course_id, Resource.is_deleted == False)
    )
    all_resources = list(all_resources_result.scalars().all())
    all_quizzes_result = await db.execute(
        select(QuizQuestion).where(QuizQuestion.course_id == course_id, QuizQuestion.is_deleted == False)
    )
    all_quizzes = list(all_quizzes_result.scalars().all())

    rows: list[dict[str, Any]] = []
    for node in nodes:
        kp_resources = await _resources_by_knowledge_point(db, course_id, node["node_name"])
        chapter_resources = await _resources_by_chapter(db, course_id, node["chapter"])
        quizzes = await _quizzes_by_knowledge_point(db, course_id, node["node_name"])

        resource_by_id = {resource.id: resource for resource in [*kp_resources, *chapter_resources]}
        resource_ids = sorted(resource_by_id.keys())
        quiz_ids = sorted({quiz.id for quiz in quizzes})
        candidate_titles = [resource_by_id[resource_id].title for resource_id in resource_ids]
        quiz_preview = [(quiz.content or "")[:80] for quiz in quizzes]
        coverage_signal_count = _coverage_signal(
            node["node_name"],
            node["chapter"],
            all_resources,
            all_quizzes,
        )
        rows.append({
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
            "coverage_signal_count": coverage_signal_count,
            "candidate_titles": "|".join(candidate_titles),
            "candidate_quiz_preview": "|".join(quiz_preview),
        })

    if sample_mode == "core":
        rows.sort(
            key=lambda row: (
                int(row["coverage_signal_count"]),
                int(row["candidate_count"]),
                row["node_name"],
            ),
            reverse=True,
        )
        if limit is not None:
            rows = rows[:limit]
    elif limit is not None:
        rows = rows[:limit]
    return rows


def _row_match_info(row: dict[str, Any]) -> tuple[set[str], set[str], set[str], bool]:
    candidate_ids = _split_ids(row.get("candidate_resource_ids")) | _split_ids(row.get("candidate_quiz_ids"))
    expected_ids = _split_ids(row.get("expected_correct_ids"))
    matched_ids = candidate_ids & expected_ids
    return candidate_ids, expected_ids, matched_ids, bool(matched_ids)


def compute_annotation_summary(rows: list[dict[str, Any]], *, calibration: bool) -> dict[str, Any]:
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
            "decision": "calibration-only" if calibration else "no-go",
            "decision_reasons": ["no annotated rows"],
        }

    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        mismatch_type = str(row.get("mismatch_type") or "").strip()
        if mismatch_type not in MISMATCH_TYPES:
            raise ValueError(f"unknown mismatch_type for node {row.get('node_id')}: {mismatch_type}")
        if not str(row.get("human_judgement_note") or "").strip():
            raise ValueError(f"human_judgement_note is required for node {row.get('node_id')}")
        candidate_ids, expected_ids, matched_ids, matched = _row_match_info(row)
        normalized = dict(row)
        normalized["candidate_count"] = len(candidate_ids)
        normalized["expected_correct_count"] = len(expected_ids)
        normalized["actual_matched_correct_count"] = len(matched_ids)
        normalized["matched"] = matched
        normalized_rows.append(normalized)

    node_count = len(normalized_rows)
    matched_count = sum(1 for row in normalized_rows if row["matched"])
    miss_rows = [row for row in normalized_rows if not row["matched"]]
    miss_count = len(miss_rows)
    exact_miss_rate = miss_count / node_count if node_count else 0.0
    mismatch_counter = Counter(str(row["mismatch_type"]) for row in normalized_rows)
    miss_counter = Counter(str(row["mismatch_type"]) for row in miss_rows)
    semantic_miss_share = (
        miss_counter["semantic_text_mismatch"] / miss_count
        if miss_count
        else 0.0
    )
    non_semantic_blocker_share = 0.0
    non_semantic_blocker_type = ""
    for mismatch_type, count in miss_counter.items():
        if mismatch_type == "semantic_text_mismatch":
            continue
        share = count / miss_count if miss_count else 0.0
        if share > non_semantic_blocker_share:
            non_semantic_blocker_share = share
            non_semantic_blocker_type = mismatch_type

    if calibration:
        decision = "calibration-only"
        reasons = ["calibration catalog does not produce go/no-go"]
    else:
        reasons = []
        if exact_miss_rate > 0.30:
            reasons.append("exact_miss_rate > 30%")
        if semantic_miss_share > 0.50:
            reasons.append("semantic_text_mismatch among misses > 50%")
        if non_semantic_blocker_share > 0.70:
            reasons.append(f"{non_semantic_blocker_type} among misses > 70%")
        decision = "no-go" if reasons else "go"
        if not reasons:
            reasons = ["all fixed thresholds passed"]

    return {
        "node_count": node_count,
        "matched_node_count": matched_count,
        "exact_miss_rate": exact_miss_rate,
        "semantic_text_mismatch_miss_share": semantic_miss_share,
        "mismatch_type_distribution": dict(mismatch_counter),
        "average_candidate_count": sum(row["candidate_count"] for row in normalized_rows) / node_count,
        "average_expected_correct_count": sum(row["expected_correct_count"] for row in normalized_rows) / node_count,
        "average_actual_matched_correct_count": (
            sum(row["actual_matched_correct_count"] for row in normalized_rows) / node_count
        ),
        "largest_non_semantic_blocker_type": non_semantic_blocker_type,
        "largest_non_semantic_blocker_share": non_semantic_blocker_share,
        "decision": decision,
        "decision_reasons": reasons,
    }


def serialize_rows_csv(rows: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=NODE_ROW_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def serialize_rows_jsonl(rows: list[dict[str, Any]]) -> str:
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else "")


def parse_csv_rows(csv_text: str) -> list[dict[str, Any]]:
    return list(csv.DictReader(io.StringIO(csv_text)))
```

- [ ] **Step 4: Run focused tests and verify service behavior passes**

Run from `/home/yezisama/workspace/workflow/EDUagent/backend`:

```bash
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/kg_resource_probe_test.db pytest tests/test_kg_resource_alignment_probe.py -q
```

Expected: PASS for all tests in `tests/test_kg_resource_alignment_probe.py`.

- [ ] **Step 5: Commit Task 1**

Run from `/home/yezisama/workspace/workflow/EDUagent`:

```bash
git add backend/app/services/kg_resource_alignment_probe.py backend/tests/test_kg_resource_alignment_probe.py
git commit -m "新增KG资源对齐探针服务"
```

---

### Task 2: Backend Probe CLI

**Files:**
- Create: `../backend/tools/probe_kg_resource_alignment.py`
- Modify: `../backend/tests/test_kg_resource_alignment_probe.py`

- [ ] **Step 1: Add failing tests for CLI parser defaults and format writing**

Append these tests to `../backend/tests/test_kg_resource_alignment_probe.py`:

```python
from tools.probe_kg_resource_alignment import build_parser, render_output


def test_cli_parser_probe_defaults_to_all_csv():
    parser = build_parser()
    args = parser.parse_args([
        "probe",
        "--catalog-id",
        "catalog_probe",
        "--course-id",
        "course_probe",
        "--out",
        "/tmp/probe.csv",
    ])

    assert args.command == "probe"
    assert args.catalog_id == "catalog_probe"
    assert args.course_id == "course_probe"
    assert args.sample_mode == "all"
    assert args.format == "csv"
    assert args.calibration is False


def test_cli_parser_supports_calibration_core_jsonl():
    parser = build_parser()
    args = parser.parse_args([
        "probe",
        "--catalog-id",
        "89f51dfbdedc4995",
        "--calibration",
        "--sample-mode",
        "core",
        "--limit",
        "15",
        "--format",
        "jsonl",
        "--out",
        "/tmp/probe.jsonl",
    ])

    assert args.command == "probe"
    assert args.catalog_id == "89f51dfbdedc4995"
    assert args.course_id is None
    assert args.calibration is True
    assert args.sample_mode == "core"
    assert args.limit == 15
    assert args.format == "jsonl"


def test_render_output_supports_json_csv_and_jsonl():
    rows = [{"catalog_id": "catalog_probe", "course_id": "course_probe", "node_id": "node_1"}]

    assert render_output(rows, "json").startswith("[")
    assert "catalog_probe" in render_output(rows, "csv")
    assert render_output(rows, "jsonl").strip().startswith("{")
```

- [ ] **Step 2: Run focused tests and verify they fail**

Run from `/home/yezisama/workspace/workflow/EDUagent/backend`:

```bash
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/kg_resource_probe_test.db pytest tests/test_kg_resource_alignment_probe.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'tools.probe_kg_resource_alignment'`.

- [ ] **Step 3: Implement the CLI**

Create `../backend/tools/probe_kg_resource_alignment.py`:

```python
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
    compute_annotation_summary,
    inventory_catalog_courses,
    parse_csv_rows,
    serialize_rows_csv,
    serialize_rows_jsonl,
    build_probe_rows,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KG-Resource 对齐探针，只读盘点和节点候选导出工具"
    )
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
    write_text(args.out, render_output(rows, args.format))


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
    elif args.command == "probe":
        await run_probe(args)
    elif args.command == "summarize":
        await run_summarize(args)
    else:
        parser.error(f"unsupported command: {args.command}")


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run focused tests and CLI help**

Run from `/home/yezisama/workspace/workflow/EDUagent/backend`:

```bash
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/kg_resource_probe_test.db pytest tests/test_kg_resource_alignment_probe.py -q
python tools/probe_kg_resource_alignment.py --help
python tools/probe_kg_resource_alignment.py probe --help
python tools/probe_kg_resource_alignment.py summarize --help
```

Expected:

- pytest PASS.
- Each help command exits `0` and prints the expected subcommand/options.

- [ ] **Step 5: Commit Task 2**

Run from `/home/yezisama/workspace/workflow/EDUagent`:

```bash
git add backend/tools/probe_kg_resource_alignment.py backend/tests/test_kg_resource_alignment_probe.py
git commit -m "新增KG资源对齐探针命令行工具"
```

---

### Task 3: 89f51 Calibration Run

**Files:**
- Runtime output only: `/tmp/kg-resource-probe/89f51-calibration.csv`
- Modify: `WORKFLOW.md`

- [ ] **Step 1: Run inventory on the live configured database**

Run from `/home/yezisama/workspace/workflow/EDUagent/backend`:

```bash
python tools/probe_kg_resource_alignment.py inventory --format json --out /tmp/kg-resource-probe/inventory.json
```

Expected:

- Command exits `0`.
- `/tmp/kg-resource-probe/inventory.json` exists.
- The JSON contains a row for `catalog_id` `89f51dfbdedc4995` if the live database from the smoke test is still present.

- [ ] **Step 2: Export the 89f51 calibration rows**

Run from `/home/yezisama/workspace/workflow/EDUagent/backend`:

```bash
python tools/probe_kg_resource_alignment.py probe --catalog-id 89f51dfbdedc4995 --calibration --sample-mode all --format csv --out /tmp/kg-resource-probe/89f51-calibration.csv
```

Expected:

- Command exits `0`.
- stderr contains `wrote <N> calibration probe rows`.
- The file contains all actual KG/LearningPath nodes available for that catalog/course.
- If `N < 5`, keep it as valid calibration; do not compute formal percentages or go/no-go.

- [ ] **Step 3: Inspect calibration output for required columns**

Run:

```bash
python - <<'PY'
from pathlib import Path
path = Path('/tmp/kg-resource-probe/89f51-calibration.csv')
header = path.read_text(encoding='utf-8').splitlines()[0].split(',')
required = {
    'catalog_id',
    'course_id',
    'node_id',
    'node_name',
    'chapter',
    'candidate_resource_ids',
    'candidate_quiz_ids',
    'candidate_count',
    'expected_correct_ids',
    'mismatch_type',
    'human_judgement_note',
}
missing = sorted(required - set(header))
print({'row_count': len(path.read_text(encoding='utf-8').splitlines()) - 1, 'missing': missing})
raise SystemExit(1 if missing else 0)
PY
```

Expected: prints `missing: []` and exits `0`.

- [ ] **Step 4: Update WORKFLOW.md with calibration result**

Add an entry under the current date in `WORKFLOW.md`:

```markdown
### KG-Resource 对齐探针校准

- 新增只读 KG-Resource 对齐探针 service/CLI，用于盘点 catalog/course 数据、导出节点候选、汇总人工标注。
- 已对 `89f51dfbdedc4995` 执行 calibration 导出：`/tmp/kg-resource-probe/89f51-calibration.csv`。
- `89f51dfbdedc4995` 仅用于流程校准，不输出汇总命中率，不产生 go/no-go。
- OpenAPI/前端/Agent 未修改，无契约漂移。
- 已运行：
  - `TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/kg_resource_probe_test.db pytest tests/test_kg_resource_alignment_probe.py -q`
  - `python tools/probe_kg_resource_alignment.py --help`
  - `python tools/probe_kg_resource_alignment.py inventory --format json --out /tmp/kg-resource-probe/inventory.json`
  - `python tools/probe_kg_resource_alignment.py probe --catalog-id 89f51dfbdedc4995 --calibration --sample-mode all --format csv --out /tmp/kg-resource-probe/89f51-calibration.csv`
```

- [ ] **Step 5: Commit Task 3**

Run from `/home/yezisama/workspace/workflow/EDUagent`:

```bash
git add frontend/WORKFLOW.md
git commit -m "记录KG资源对齐探针校准结果"
```

---

### Task 4: Formal Second-Catalog Export and Summary Flow

**Files:**
- Runtime output:
  - `/tmp/kg-resource-probe/second-catalog.csv`
  - `/tmp/kg-resource-probe/second-catalog-summary.json`
- Modify: `WORKFLOW.md`

- [ ] **Step 1: Select the second catalog from inventory**

Open `/tmp/kg-resource-probe/inventory.json` and choose the first row where:

- `catalog_id != "89f51dfbdedc4995"`
- `eligible_for_formal_probe == true`
- `kg_node_count >= 10` or `learning_path_node_count >= 10`
- `resource_count > 0` or `quiz_count > 0`

If no row satisfies these conditions, stop this task and add this exact conclusion to `WORKFLOW.md`:

```markdown
### KG-Resource 对齐探针正式样本阻塞

- 已完成数据底盘盘点，但未发现满足正式探针条件的第二个 catalog。
- 当前不能输出 KG-Resource 对齐 go/no-go。
- 上线前置条件：补充或构造足量真实样本，要求 KG/LearningPath 节点可抽取 10-15 个核心节点，且资源或题目存在可匹配的 `knowledge_point` 或 `chapter` 元数据。
```

Then commit:

```bash
git add frontend/WORKFLOW.md
git commit -m "记录KG资源对齐探针正式样本阻塞"
```

- [ ] **Step 2: Export 10-15 core rows for the selected catalog**

Replace `<CATALOG_ID>` and `<COURSE_ID>` with the selected inventory row values.

Run from `/home/yezisama/workspace/workflow/EDUagent/backend`:

```bash
python tools/probe_kg_resource_alignment.py probe --catalog-id <CATALOG_ID> --course-id <COURSE_ID> --sample-mode core --limit 15 --format csv --out /tmp/kg-resource-probe/second-catalog.csv
```

Expected:

- Command exits `0`.
- stderr contains `wrote <N> formal probe rows`.
- `N` is between `10` and `15` when enough nodes exist.
- If `N < 10`, record the sample as insufficient and do not run formal go/no-go.

- [ ] **Step 3: Human annotation of second catalog rows**

Open `/tmp/kg-resource-probe/second-catalog.csv` and fill these columns for each row:

- `expected_correct_ids`: pipe-separated resource or quiz ids that a human believes should attach to the node, such as `res_a|quiz_b`. Leave empty only when the correct judgement is no real resource exists.
- `mismatch_type`: one of:
  - `exact_match_ok`
  - `semantic_text_mismatch`
  - `chapter_mismatch`
  - `resource_metadata_missing`
  - `kg_node_too_broad`
  - `kg_node_too_narrow`
  - `resource_content_irrelevant`
  - `no_real_resource`
  - `other`
- `human_judgement_note`: a short reason, such as `语义应挂 AVL 旋转资料，但资源 knowledge_point 写成 AVL 平衡调整`.

For a row where exact candidates already include at least one correct item, use:

```text
mismatch_type=exact_match_ok
human_judgement_note=精确匹配命中，人工认为候选合理
```

For a row with no true corresponding resource or quiz, use:

```text
expected_correct_ids=
mismatch_type=no_real_resource
human_judgement_note=当前资料和题库没有可挂到该节点的真实内容
```

- [ ] **Step 4: Summarize annotated rows**

Run from `/home/yezisama/workspace/workflow/EDUagent/backend`:

```bash
python tools/probe_kg_resource_alignment.py summarize --annotation-file /tmp/kg-resource-probe/second-catalog.csv --out /tmp/kg-resource-probe/second-catalog-summary.json
```

Expected:

- Command exits `0` only if every annotated row has a closed-list `mismatch_type` and non-empty `human_judgement_note`.
- Summary JSON contains:
  - `node_count`
  - `matched_node_count`
  - `exact_miss_rate`
  - `semantic_text_mismatch_miss_share`
  - `mismatch_type_distribution`
  - `average_candidate_count`
  - `average_expected_correct_count`
  - `average_actual_matched_correct_count`
  - `decision`
  - `decision_reasons`

- [ ] **Step 5: Record formal summary**

Add an entry to `WORKFLOW.md`:

```markdown
### KG-Resource 对齐探针正式样本

- 第二 catalog：`<CATALOG_ID>`，course：`<COURSE_ID>`。
- 节点记录表：`/tmp/kg-resource-probe/second-catalog.csv`。
- 汇总结果：`/tmp/kg-resource-probe/second-catalog-summary.json`。
- 判定：`<decision>`。
- 关键指标：
  - node_count：`<node_count>`
  - matched_node_count：`<matched_node_count>`
  - exact_miss_rate：`<exact_miss_rate>`
  - semantic_text_mismatch_miss_share：`<semantic_text_mismatch_miss_share>`
  - mismatch_type_distribution：`<mismatch_type_distribution>`
- 下一步分支：
  - `go`：再写 KG ready gate spec。
  - `no-go` 且 semantic_text_mismatch 为主：先设计挂载策略改造。
  - `no-go` 且数据质量类问题为主：先处理 KG 或资源元数据质量。
```

Use actual values from `/tmp/kg-resource-probe/second-catalog-summary.json`.

- [ ] **Step 6: Commit Task 4**

Run from `/home/yezisama/workspace/workflow/EDUagent`:

```bash
git add frontend/WORKFLOW.md
git commit -m "记录KG资源对齐探针正式样本结果"
```

---

### Task 5: Final Verification and Handoff

**Files:**
- Verify only unless `WORKFLOW.md` was not updated in Task 3 or Task 4.

- [ ] **Step 1: Run backend regression for the probe**

Run from `/home/yezisama/workspace/workflow/EDUagent/backend`:

```bash
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/kg_resource_probe_test.db pytest tests/test_kg_resource_alignment_probe.py -q
```

Expected: PASS.

- [ ] **Step 2: Run existing node-resource regression**

Run from `/home/yezisama/workspace/workflow/EDUagent/backend`:

```bash
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/node_resources_probe_regression.db pytest tests/test_node_resources.py -q
```

Expected: PASS. This verifies the probe did not require changing the production node resource endpoint.

- [ ] **Step 3: Confirm OpenAPI was not touched**

Run from `/home/yezisama/workspace/workflow/EDUagent`:

```bash
git diff -- docs/10-client-api/Client-API.openapi.json
```

Expected: no output.

- [ ] **Step 4: Confirm git status contains only intentional files**

Run from `/home/yezisama/workspace/workflow/EDUagent/frontend`:

```bash
git status --short
```

Expected:

- No uncommitted changes in `backend/app/services/kg_resource_alignment_probe.py`, `backend/tools/probe_kg_resource_alignment.py`, `backend/tests/test_kg_resource_alignment_probe.py`, or `frontend/WORKFLOW.md`.
- Pre-existing unrelated untracked files may remain; do not add or remove them.

- [ ] **Step 5: Final response content**

Report these items to the user:

```text
当前完成 / 实现状态：已新增只读 KG-Resource 对齐探针 service/CLI，已完成 89f51 校准导出；如果存在第二 catalog，则已输出正式 summary 和 go/no-go。
修改文件：列出实际变更文件。
测试结果：列出实际运行命令和 PASS/FAIL。
OpenAPI/契约是否漂移：未修改 OpenAPI，未新增接口，生产节点资源匹配逻辑未改。
git commit 信息：列出本轮新增提交。
剩余风险：人工标注质量影响结论；第二 catalog 不足时不能给 go/no-go；探针不代表语义匹配能力。
下一步建议：按 summary decision 进入 KG ready gate spec、挂载策略改造 spec，或数据质量修复。
```

## Self-Review

Spec coverage:

- 第 0 步数据底盘盘点：Task 1 `inventory_catalog_courses`，Task 3 inventory run.
- 89f51 校准：Task 3 uses `--calibration`, `--sample-mode all`, no go/no-go.
- 第二 catalog 正式样本：Task 4 selects eligible inventory row and exports `10-15` core rows.
- 人工标注口径：Task 4 Step 3 gives required columns and closed labels.
- 节点级记录表：Task 1 `NODE_ROW_FIELDS` includes all spec fields.
- 错配类型封闭清单：Task 1 `MISMATCH_TYPES` and validation.
- 汇总指标：Task 1 `compute_annotation_summary`.
- Go / No-Go 阈值：Task 1 `compute_annotation_summary` fixed thresholds.
- 决策分支：Task 4 Step 5 and Task 5 final response.
- 验证边界：Plan does not implement semantic matching, ready gate, API, Agent, or UI changes.

Placeholder scan:

- The plan uses concrete file paths, commands, expected outputs, and code snippets.
- Runtime values such as `<CATALOG_ID>` and `<decision>` are explicitly filled from inventory/summary at execution time, not implementation gaps.

Type consistency:

- Tests import `inventory_catalog_courses`, `build_probe_rows`, `compute_annotation_summary`, `serialize_rows_csv`, and `MISMATCH_TYPES`; Task 1 implements the same names.
- CLI tests import `build_parser` and `render_output`; Task 2 implements the same names.
- CSV annotation fields match `NODE_ROW_FIELDS` and the spec table.
