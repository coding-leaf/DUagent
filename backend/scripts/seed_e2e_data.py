#!/usr/bin/env python3
"""Seed E2E test data into a dedicated test database.

Usage:
  ALLOW_E2E_SEED=true DATABASE_URL='mysql+aiomysql://root:123456@localhost:3306/duagent_test?charset=utf8mb4' python scripts/seed_e2e_data.py
"""
import asyncio
import os
import sys
from urllib.parse import urlparse

# ---- guards ----
if os.environ.get("ALLOW_E2E_SEED") != "true":
    print("ERROR: ALLOW_E2E_SEED must be set to 'true'. Refusing to run.")
    sys.exit(1)

from app.core.config import settings
db_name = urlparse(settings.resolved_database_url).path.lstrip("/")
if "test" not in db_name.lower():
    print(f"ERROR: Database name '{db_name}' does not contain 'test'. Refusing to run.")
    sys.exit(1)

print(f"Seeding test database: {db_name}")

# ---- imports ----
from sqlalchemy import select
from app.db.session import async_session_factory, init_db
from app.core.security import hash_password
from app.models.user import User
from app.models.course import Course, CourseEnrollment
from app.models.quiz import QuizQuestion, QuizSession
from app.models.others import Resource, UserProfile, Evaluation


async def upsert(session, model, lookup: dict, defaults: dict):
    """Insert or skip — return existing or new instance."""
    stmt = select(model)
    for k, v in lookup.items():
        stmt = stmt.where(getattr(model, k) == v)
    result = await session.execute(stmt)
    instance = result.scalars().first()
    if instance is None:
        instance = model(**{**lookup, **defaults})
        session.add(instance)
        await session.flush()
        print(f"  Created {model.__name__}: {lookup}")
    else:
        print(f"  Skipped {model.__name__}: {lookup} (exists)")
    return instance


async def seed_users(session):
    """Create teacher and student accounts."""
    print("\n-- Users --")
    teacher = await upsert(session, User, {"email": "t@t.com"}, {
        "username": "teacher_e2e",
        "password_hash": hash_password("Abc12345"),
        "real_name": "Teacher E2E",
        "role": "teacher",
    })
    student = await upsert(session, User, {"email": "s@t.com"}, {
        "username": "student_e2e",
        "password_hash": hash_password("Abc12345"),
        "real_name": "Student E2E",
        "student_id": "S20260001",
        "role": "student",
        "major": "计算机科学与技术",
        "grade": "2026级",
    })
    return teacher, student


async def seed_courses(session, teacher, student):
    """Create 2 courses, enroll student in both."""
    print("\n-- Courses --")
    course1 = await upsert(session, Course, {"course_code": "CS101-E2E"}, {
        "name": "数据结构与算法",
        "description": "E2E test course 1",
        "teacher_id": teacher.id,
    })
    course2 = await upsert(session, Course, {"course_code": "CS102-E2E"}, {
        "name": "操作系统原理",
        "description": "E2E test course 2",
        "teacher_id": teacher.id,
    })
    for course in [course1, course2]:
        await upsert(session, CourseEnrollment,
            {"student_id": student.id, "course_id": course.id}, {})
    return course1, course2


async def seed_resources(session, course1, course2):
    """Create sample resources for each course."""
    print("\n-- Resources --")
    resource_types = ["document", "mindmap", "reading", "code", "video"]
    i = 0
    for course in [course1, course2]:
        for rt in resource_types:
            i += 1
            await upsert(session, Resource,
                {"course_id": course.id, "title": f"E2E {rt.title()} #{i}"},
                {"type": rt, "description": f"E2E test {rt}", "chapter": "第1章",
                 "knowledge_point": f"知识点-{i}", "tags": ["e2e", "test"],
                 "url": f"https://example.com/e2e/{i}", "view_count": i * 10})


async def seed_quiz_questions(session, course1, course2):
    """Create sample quiz questions."""
    print("\n-- QuizQuestions --")
    for j, course in enumerate([course1, course2]):
        for i in range(3):
            await upsert(session, QuizQuestion,
                {"course_id": course.id, "content": f"E2E Question {j}-{i}: What is {i}+{i}?"},
                {"type": "single_choice", "chapter": f"第{i+1}章",
                 "knowledge_point": f"KP-{j}-{i}",
                 "correct_answer": "A",
                 "options": [{"key": "A", "text": str(i+i)}, {"key": "B", "text": str(i+i+1)},
                             {"key": "C", "text": str(i+i+2)}, {"key": "D", "text": str(i+i+3)}],
                 "explanation": f"Because {i}+{i}={i+i}"})


async def seed_student_data(session, student, course1, course2):
    """Create student profiles, evaluations, and quiz sessions."""
    print("\n-- StudentData --")
    for course in [course1, course2]:
        await upsert(session, UserProfile,
            {"user_id": student.id, "course_id": course.id},
            {"modal_preference": ["visual", "code"],
             "guidance_level_current": "L2",
             "knowledge_mastered": 5, "knowledge_weak": 2})

        await upsert(session, Evaluation,
            {"user_id": student.id, "course_id": course.id},
            {"progress_table": {"overall": 0.75},
             "mastery_table": {"algorithm": 0.8, "structure": 0.7},
             "summary_text": "E2E evaluation summary"})

    await upsert(session, QuizSession,
        {"user_id": student.id, "course_id": course1.id, "score": 85.0},
        {"correct_count": 8, "total_count": 10, "time_spent": 600,
         "chapter": "第1章", "status": "submitted",
         "diagnosis_json": {"suggestions": ["Review trees", "Practice graphs"]}})


async def main():
    await init_db()
    async with async_session_factory() as session:
        async with session.begin():
            teacher, student = await seed_users(session)
            course1, course2 = await seed_courses(session, teacher, student)
            await seed_resources(session, course1, course2)
            await seed_quiz_questions(session, course1, course2)
            await seed_student_data(session, student, course1, course2)
    print("\nSeed complete.")


if __name__ == "__main__":
    asyncio.run(main())
