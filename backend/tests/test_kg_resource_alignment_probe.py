import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import delete, update

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_kg_resource_probe.db",
)

from app.db.session import async_session_factory, engine, init_db
from app.models.catalog import CourseCatalog, CourseCatalogMaterial, CourseOffering
from app.models.course import Course, CourseEnrollment
from app.models.others import AsyncTask, CourseKnowledgeGraph, LearningPath, Resource
from app.models.quiz import QuizQuestion
from app.models.user import User
from app.services.kg_resource_alignment_probe import (
    MISMATCH_TYPES,
    NODE_ROW_FIELDS,
    build_probe_rows,
    compute_annotation_summary,
    inventory_catalog_courses,
    parse_csv_rows,
    serialize_rows_csv,
    serialize_rows_jsonl,
)
import tools.probe_kg_resource_alignment as probe_cli
from tools.probe_kg_resource_alignment import build_parser, render_inventory_output, render_output

asyncio.run(init_db())
asyncio.run(engine.dispose())


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    await engine.dispose()
    async with async_session_factory() as db:
        await db.execute(update(CourseKnowledgeGraph).values(parent_graph_id=None))
        for model in [
            QuizQuestion,
            Resource,
            LearningPath,
            CourseKnowledgeGraph,
            CourseOffering,
            CourseCatalogMaterial,
            CourseCatalog,
            CourseEnrollment,
            AsyncTask,
            Course,
            User,
        ]:
            await db.execute(delete(model))
        await db.commit()
    await engine.dispose()
    yield
    await engine.dispose()
    async with async_session_factory() as db:
        await db.execute(update(CourseKnowledgeGraph).values(parent_graph_id=None))
        for model in [
            QuizQuestion,
            Resource,
            LearningPath,
            CourseKnowledgeGraph,
            CourseOffering,
            CourseCatalogMaterial,
            CourseCatalog,
            CourseEnrollment,
            AsyncTask,
            Course,
            User,
        ]:
            await db.execute(delete(model))
        await db.commit()
    await engine.dispose()


async def seed_probe_data():
    kg_nodes = [
        {"id": "node_1", "name": "AVL树旋转", "chapter": "平衡树"},
        {"id": "node_2", "name": "红黑树性质", "chapter": "平衡树"},
        {"id": "node_3", "name": "B树索引", "chapter": "数据库索引"},
    ]
    kg_nodes.extend(
        {
            "id": f"node_{index}",
            "name": f"补充知识点{index}",
            "chapter": "补充章节",
        }
        for index in range(4, 11)
    )

    async with async_session_factory() as db:
        teacher = User(
            id="teacher_probe",
            username="teacher_probe",
            email="teacher_probe@example.com",
            password_hash="hash",
            role="teacher",
        )
        student = User(
            id="student_probe",
            username="student_probe",
            email="student_probe@example.com",
            password_hash="hash",
            role="student",
        )
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
        db.add_all([teacher, student, catalog])
        await db.commit()

        db.add(course)
        await db.commit()

        db.add(offering)
        await db.commit()

        db.add_all(
            [
                CourseKnowledgeGraph(
                    id="kg_probe_active",
                    course_id="course_probe",
                    version=1,
                    is_active=True,
                    nodes=kg_nodes,
                    edges=[],
                    create_time=datetime(2026, 1, 1, 10, 0, 0),
                    update_time=datetime(2026, 1, 1, 10, 0, 0),
                ),
                CourseKnowledgeGraph(
                    id="kg_probe_inactive",
                    course_id="course_probe",
                    version=2,
                    is_active=False,
                    nodes=[
                        {"id": "node_1", "name": "废弃AVL节点", "chapter": "废弃章节"},
                        {"id": "inactive_only", "name": "废弃独有节点", "chapter": "废弃章节"},
                    ],
                    edges=[],
                    create_time=datetime(2026, 1, 2, 10, 0, 0),
                    update_time=datetime(2026, 1, 2, 10, 0, 0),
                ),
                LearningPath(
                    id="lp_probe",
                    user_id="student_probe",
                    course_id="course_probe",
                    nodes=[
                        {"id": "node_1", "name": "AVL树旋转", "status": "in_progress"},
                        {"id": "node_2", "name": "红黑树性质", "status": "locked"},
                        {"id": "lp_only", "name": "学习路径独有节点", "status": "locked"},
                    ],
                    edges=[],
                    current_node_id="node_1",
                    current_node_name="AVL树旋转",
                ),
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
                    id="res_full_set",
                    course_id="course_probe",
                    title="整套练习",
                    type="full_exercise_set",
                    chapter="平衡树",
                    knowledge_point="AVL树旋转",
                    content="当前规则会按字段精确命中 Resource，不按 type 过滤。",
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
                Resource(
                    id="res_empty_chapter",
                    course_id="course_probe",
                    title="空章节无关资料",
                    type="document",
                    chapter="",
                    knowledge_point="其他知识点",
                    content="不应被无章节节点按 chapter 空字符串命中。",
                    is_deleted=False,
                ),
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
        )
        await db.commit()


@pytest.mark.asyncio
async def test_inventory_catalog_courses_counts_bound_catalog_data():
    await seed_probe_data()

    async with async_session_factory() as db:
        rows = await inventory_catalog_courses(db)

    row = next(item for item in rows if item["catalog_id"] == "catalog_probe")
    assert row["course_id"] == "course_probe"
    assert row["chunk_count"] == 12
    assert row["kg_node_count"] == 10
    assert row["learning_path_node_count"] == 3
    assert row["resource_count"] == 4
    assert row["distinct_resource_knowledge_point_count"] == 2
    assert row["distinct_resource_chapter_count"] == 1
    assert row["quiz_count"] == 1
    assert row["distinct_quiz_knowledge_point_count"] == 1
    assert row["eligible_for_formal_probe"] is True


@pytest.mark.asyncio
async def test_build_probe_rows_uses_exact_candidates_and_excludes_deleted_rows():
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
    assert set(node_1["candidate_resource_ids"].split("|")) == {"res_exact", "res_chapter", "res_full_set"}
    assert node_1["candidate_quiz_ids"] == "quiz_exact"
    assert node_1["candidate_count"] == 4
    assert "quiz_deleted" not in node_1["candidate_quiz_ids"]
    assert "res_deleted" not in node_1["candidate_resource_ids"]

    lp_only = by_id["lp_only"]
    assert lp_only["node_source"] == "learning_path"
    assert lp_only["chapter"] == ""
    assert lp_only["candidate_resource_ids"] == ""
    assert lp_only["candidate_count"] == 0

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


def test_compute_annotation_summary_requires_human_judgement_note():
    rows = [
        {
            "node_id": "n1",
            "candidate_resource_ids": "",
            "candidate_quiz_ids": "",
            "expected_correct_ids": "res_1",
            "mismatch_type": "semantic_text_mismatch",
            "human_judgement_note": "",
        }
    ]

    with pytest.raises(ValueError, match="human_judgement_note is required"):
        compute_annotation_summary(rows, calibration=False)


def test_serialize_rows_csv_contains_annotation_columns_and_round_trips():
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
            "node_source": "kg+learning_path",
            "coverage_signal_count": 3,
            "candidate_titles": "AVL旋转讲解|平衡树章节材料",
            "candidate_quiz_preview": "AVL 树什么时候需要旋转？",
        }
    ]

    csv_text = serialize_rows_csv(rows)
    parsed = parse_csv_rows(csv_text)

    assert csv_text.splitlines()[0].split(",") == NODE_ROW_FIELDS
    assert "expected_correct_ids" in csv_text
    assert "mismatch_type" in csv_text
    assert "res_exact|res_chapter" in csv_text
    assert "AVL树旋转" in csv_text
    assert parsed[0]["candidate_quiz_ids"] == "quiz_exact"
    assert MISMATCH_TYPES["exact_match_ok"] == "精确字段匹配命中，且人工认为合理"


def test_serialize_rows_jsonl_emits_one_json_object_per_row():
    rows = [
        {
            "catalog_id": "catalog_probe",
            "course_id": "course_probe",
            "node_id": "node_1",
            "node_name": "AVL树旋转",
        },
        {
            "catalog_id": "catalog_probe",
            "course_id": "course_probe",
            "node_id": "node_2",
            "node_name": "红黑树性质",
        },
    ]

    jsonl_text = serialize_rows_jsonl(rows)

    assert jsonl_text.count("\n") == 2
    assert '"node_name": "AVL树旋转"' in jsonl_text


def test_cli_parser_probe_defaults_to_all_csv():
    parser = build_parser()
    args = parser.parse_args(
        [
            "probe",
            "--catalog-id",
            "catalog_probe",
            "--course-id",
            "course_probe",
            "--out",
            "/tmp/probe.csv",
        ]
    )

    assert args.command == "probe"
    assert args.catalog_id == "catalog_probe"
    assert args.course_id == "course_probe"
    assert args.sample_mode == "all"
    assert args.format == "csv"
    assert args.calibration is False


def test_cli_parser_supports_calibration_core_jsonl():
    parser = build_parser()
    args = parser.parse_args(
        [
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
        ]
    )

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


def test_render_inventory_output_preserves_inventory_csv_fields():
    rows = [
        {
            "catalog_id": "catalog_probe",
            "catalog_title": "Probe Catalog",
            "course_id": "course_probe",
            "offering_name": "Probe Course",
            "chunk_count": 12,
            "kg_node_count": 10,
            "learning_path_node_count": 3,
            "resource_count": 4,
            "distinct_resource_knowledge_point_count": 2,
            "distinct_resource_chapter_count": 1,
            "quiz_count": 1,
            "distinct_quiz_knowledge_point_count": 1,
            "eligible_for_formal_probe": True,
        }
    ]

    csv_text = render_inventory_output(rows, "csv")

    header = csv_text.splitlines()[0].split(",")
    assert "catalog_title" in header
    assert "chunk_count" in header
    assert "eligible_for_formal_probe" in header
    assert "Probe Catalog" in csv_text
    assert "True" in csv_text


@pytest.mark.asyncio
async def test_async_main_disposes_engine_after_command(monkeypatch):
    calls = []

    async def fake_run_inventory(args):
        calls.append(args.command)

    class FakeEngine:
        async def dispose(self):
            calls.append("disposed")

    monkeypatch.setattr(probe_cli, "run_inventory", fake_run_inventory)
    monkeypatch.setattr(probe_cli, "engine", FakeEngine(), raising=False)

    await probe_cli.async_main(["inventory"])

    assert calls == ["inventory", "disposed"]
