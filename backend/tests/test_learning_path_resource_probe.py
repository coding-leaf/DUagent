import os
import sys
from datetime import datetime

import pytest
import pytest_asyncio

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:////tmp/learning_path_resource_probe.db",
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import Base
from app.db.session import async_session_factory, engine
from app.models.course import Course
from app.models.others import CourseKnowledgeGraph, LearningPath, Resource
from app.models.quiz import QuizQuestion
from app.models.user import User
from app.services.learning_path_resource_probe import build_learning_path_resource_report


@pytest_asyncio.fixture(autouse=True)
async def _reset_db():
    await engine.dispose()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


async def _seed_learning_path_probe_data() -> None:
    async with async_session_factory() as db:
        db.add_all(
            [
                User(
                    id="teacher_probe",
                    email="teacher_probe@example.com",
                    username="teacher_probe",
                    password_hash="x",
                    role="teacher",
                ),
                User(
                    id="student_probe",
                    email="student_probe@example.com",
                    username="student_probe",
                    password_hash="x",
                    role="student",
                ),
            ]
        )
        await db.commit()

        db.add(
            Course(
                id="course_probe",
                name="Probe Course",
                course_code="PROBE001",
                teacher_id="teacher_probe",
            )
        )
        await db.commit()

        db.add(
            CourseKnowledgeGraph(
                id="kg_active_probe",
                course_id="course_probe",
                version=2,
                is_active=True,
                source_type="route_a_body_grounded",
                generation_strategy="route_a_prune_usable_060",
                nodes=[
                    {"id": "node_1", "name": "指针", "chapter": "第5章 指针与数组"},
                    {"id": "node_2", "name": "结构", "chapter": "第6章 结构"},
                ],
                edges=[],
                metrics={"support_band_counts": {"good": 2}},
            )
        )
        db.add(
            CourseKnowledgeGraph(
                id="kg_inactive_probe",
                course_id="course_probe",
                version=1,
                is_active=False,
                nodes=[{"id": "node_1", "name": "旧指针", "chapter": "旧章节"}],
                edges=[],
            )
        )
        db.add(
            LearningPath(
                id="lp_probe",
                user_id="student_probe",
                course_id="course_probe",
                nodes=[
                    {"id": "node_1", "name": "指针", "status": "in_progress"},
                    {"id": "node_2", "name": "结构", "status": "locked"},
                    {"id": "lp_only", "name": "路径独有", "status": "locked"},
                ],
                edges=[{"source": "node_1", "target": "node_2"}],
                current_node_id="node_1",
                current_node_name="指针",
                generated_at=datetime(2026, 6, 11, 10, 0, 0),
            )
        )
        db.add_all(
            [
                Resource(
                    id="res_pointer_exact",
                    course_id="course_probe",
                    title="指针讲解",
                    type="document",
                    chapter="第5章 指针与数组",
                    knowledge_point="指针",
                    content="指针讲解正文",
                    tags=["kg_node:node_1"],
                ),
                Resource(
                    id="res_pointer_chapter",
                    course_id="course_probe",
                    title="指针章节材料",
                    type="reading",
                    chapter="第5章 指针与数组",
                    knowledge_point="数组",
                    content="章节正文",
                ),
                Resource(
                    id="res_structure_chapter",
                    course_id="course_probe",
                    title="结构章节材料",
                    type="reading",
                    chapter="第6章 结构",
                    knowledge_point="其他",
                    content="结构章节正文",
                    tags=["kg_node:node_2"],
                ),
                Resource(
                    id="res_deleted",
                    course_id="course_probe",
                    title="已删除",
                    type="document",
                    chapter="第5章 指针与数组",
                    knowledge_point="指针",
                    content="不应出现",
                    is_deleted=True,
                ),
            ]
        )
        db.add(
            QuizQuestion(
                id="quiz_pointer",
                course_id="course_probe",
                chapter="第5章 指针与数组",
                knowledge_point="指针",
                type="single_choice",
                content="指针题",
                correct_answer="A",
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_learning_path_resource_probe_reports_path_node_resource_coverage():
    await _seed_learning_path_probe_data()

    async with async_session_factory() as db:
        report = await build_learning_path_resource_report(
            db,
            catalog_id="catalog_probe",
            course_id="course_probe",
            user_id="student_probe",
        )

    assert report["catalog_id"] == "catalog_probe"
    assert report["course_id"] == "course_probe"
    assert report["learning_path_id"] == "lp_probe"
    assert report["active_kg_id"] == "kg_active_probe"
    assert report["summary"]["learning_path_node_count"] == 3
    assert report["summary"]["matched_active_kg_node_count"] == 2
    assert report["summary"]["nodes_with_any_resource_count"] == 2
    assert report["summary"]["empty_node_count"] == 1
    assert report["summary"]["node_resource_coverage_ratio"] == pytest.approx(2 / 3)
    assert report["summary"]["kg_match_ratio"] == pytest.approx(2 / 3)
    assert report["summary"]["kg_tagged_resource_count"] == 2

    rows = {row["node_id"]: row for row in report["nodes"]}
    assert rows["node_1"]["matched_active_kg"] is True
    assert rows["node_1"]["chapter"] == "第5章 指针与数组"
    assert rows["node_1"]["weak_point_resource_ids"] == ["res_pointer_exact"]
    assert rows["node_1"]["chapter_resource_ids"] == ["res_pointer_chapter", "res_pointer_exact"]
    assert rows["node_1"]["exercise_ids"] == ["quiz_pointer"]
    assert rows["node_1"]["candidate_count"] == 3

    assert rows["node_2"]["matched_active_kg"] is True
    assert rows["node_2"]["candidate_count"] == 1
    assert rows["node_2"]["chapter_resource_ids"] == ["res_structure_chapter"]

    assert rows["lp_only"]["matched_active_kg"] is False
    assert rows["lp_only"]["candidate_count"] == 0
