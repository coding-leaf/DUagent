# Teaching Service Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move teacher-side reporting and class insights query logic out of `backend/app/api/v1/teaching.py` into `backend/app/services/teaching_service.py` without changing API behavior.

**Architecture:** Keep `teaching.py` as a thin FastAPI router and introduce `TeachingService(db)` as the application query boundary. Service methods keep current SQLAlchemy aggregation behavior, including existing N+1 behavior in `list_students`.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, Pytest async tests, existing `{code, message, data}` response wrappers.

---

## File Structure

- Create: `../backend/app/services/teaching_service.py`
  - Owns teacher verification, student list/detail query logic, student learning report aggregation, and class insights aggregation.
  - May contain small private item-formatting helpers.
  - Does not introduce Repository, CQRS, background tasks, or Agent calls.
- Create: `../backend/tests/test_teaching_service.py`
  - Direct service-level tests with `async_session_factory`.
  - Covers permissions, list pagination, student detail 404, student learning aggregation, and class insights aggregation.
- Modify: `../backend/app/api/v1/teaching.py`
  - Retains route definitions, `Depends`, `Query`, and response wrappers.
  - Removes inline SQLAlchemy query logic.
- Modify: `WORKFLOW.md`
  - Adds one dated entry after implementation and verification.

Do not modify frontend files, `.env`, database schema, build artifacts, uploaded files, or Agent Service.

---

### Task 1: Add Service Test Scaffolding And Low-Risk Cases

**Files:**
- Create: `../backend/tests/test_teaching_service.py`
- No production files yet.

- [ ] **Step 1: Create the test file with shared helpers**

Use the existing backend test style: set `DATABASE_URL`, call `init_db()`, then import models and service. The first import of `TeachingService` should fail until Task 2 creates the file.

```python
"""Service tests for app.services.teaching_service.TeachingService.

Run:
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/teaching_service_refactor_test.db ../.venv/bin/python -m pytest tests/test_teaching_service.py -q -p no:cacheprovider
"""
import asyncio
import os
import sys
import uuid

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_teaching_service.db",
)

from app.db.session import async_session_factory, init_db

asyncio.run(init_db())

from app.models.course import Course, CourseEnrollment
from app.models.user import User
from app.services.teaching_service import TeachingService


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _seed_user(db, role: str, username_prefix: str) -> User:
    user = User(
        email=f"{_uid(username_prefix)}@test.local",
        username=_uid(username_prefix),
        password_hash="test",
        role=role,
        real_name=f"{username_prefix} Real",
        student_id=_uid("sid") if role == "student" else "",
        major="CS" if role == "student" else "",
        grade="2026" if role == "student" else "",
    )
    db.add(user)
    await db.flush()
    return user


async def _seed_course_with_teacher(db):
    teacher = await _seed_user(db, "teacher", "teacher")
    other_teacher = await _seed_user(db, "teacher", "other_teacher")
    admin = await _seed_user(db, "admin", "admin")
    course = Course(name="Teaching Service Course", course_code=_uid("course"), teacher_id=teacher.id)
    db.add(course)
    await db.flush()
    return teacher, other_teacher, admin, course
```

- [ ] **Step 2: Add `verify_teacher` tests**

Append these tests to the same file:

```python
@pytest.mark.asyncio
async def test_verify_teacher_preserves_owner_and_403_semantics():
    async with async_session_factory() as db:
        teacher, other_teacher, admin, course = await _seed_course_with_teacher(db)
        await db.commit()

        service = TeachingService(db)
        verified = await service.verify_teacher(course.id, teacher)
        assert verified.id == course.id

        with pytest.raises(HTTPException) as other_exc:
            await service.verify_teacher(course.id, other_teacher)
        assert other_exc.value.status_code == 403
        assert other_exc.value.detail == {"code": 40300, "message": "无权访问此班级", "data": None}

        with pytest.raises(HTTPException) as admin_exc:
            await service.verify_teacher(course.id, admin)
        assert admin_exc.value.status_code == 403
        assert admin_exc.value.detail == {"code": 40300, "message": "无权访问此班级", "data": None}


@pytest.mark.asyncio
async def test_verify_teacher_raises_404_for_missing_course():
    async with async_session_factory() as db:
        teacher = await _seed_user(db, "teacher", "teacher")
        await db.commit()

        with pytest.raises(HTTPException) as exc:
            await TeachingService(db).verify_teacher("missing_course", teacher)
        assert exc.value.status_code == 404
        assert exc.value.detail == {"code": 40400, "message": "课程不存在", "data": None}
```

- [ ] **Step 3: Add `list_students` and `get_student_info` tests**

Append:

```python
@pytest.mark.asyncio
async def test_list_students_paginates_and_excludes_soft_deleted_enrollments():
    async with async_session_factory() as db:
        teacher, _other_teacher, _admin, course = await _seed_course_with_teacher(db)
        students = [await _seed_user(db, "student", f"student{i}") for i in range(3)]
        db.add_all([
            CourseEnrollment(course_id=course.id, student_id=students[0].id),
            CourseEnrollment(course_id=course.id, student_id=students[1].id),
            CourseEnrollment(course_id=course.id, student_id=students[2].id, is_deleted=True),
        ])
        await db.commit()

        data = await TeachingService(db).list_students(course.id, teacher, page=2, page_size=1)

        assert data["total"] == 2
        assert data["page"] == 2
        assert data["page_size"] == 1
        assert len(data["students"]) == 1
        returned_ids = {item["id"] for item in data["students"]}
        assert students[2].id not in returned_ids
        assert {"id", "username", "real_name", "student_id", "major", "grade", "joined_at"} <= set(data["students"][0])


@pytest.mark.asyncio
async def test_get_student_info_returns_current_fields_and_raises_404_for_missing_student():
    async with async_session_factory() as db:
        teacher, _other_teacher, _admin, course = await _seed_course_with_teacher(db)
        student = await _seed_user(db, "student", "student")
        await db.commit()

        service = TeachingService(db)
        data = await service.get_student_info(course.id, student.id, teacher)

        assert data["id"] == student.id
        assert data["username"] == student.username
        assert data["email"] == student.email
        assert data["real_name"] == student.real_name
        assert data["student_id"] == student.student_id
        assert data["role"] == "student"
        assert data["major"] == student.major
        assert data["grade"] == student.grade
        assert "created_at" in data

        with pytest.raises(HTTPException) as exc:
            await service.get_student_info(course.id, "missing_student", teacher)
        assert exc.value.status_code == 404
        assert exc.value.detail == {"code": 40400, "message": "学生不存在", "data": None}
```

- [ ] **Step 4: Run the new tests and verify red**

Run from `../backend`:

```bash
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/teaching_service_task1_red.db ../.venv/bin/python -m pytest tests/test_teaching_service.py -q -p no:cacheprovider
```

Expected: FAIL during import with `ModuleNotFoundError: No module named 'app.services.teaching_service'`.

- [ ] **Step 5: Leave red tests unstaged until Task 2 is green**

Do not commit at this point. Project rules require failing tests to be fixed before committing. Keep `backend/tests/test_teaching_service.py` in the working tree and continue directly to Task 2.

---

### Task 2: Create TeachingService For Verification, Student List, And Student Detail

**Files:**
- Create: `../backend/app/services/teaching_service.py`
- Test: `../backend/tests/test_teaching_service.py`

- [ ] **Step 1: Implement the initial service**

Create `../backend/app/services/teaching_service.py` with:

```python
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course, CourseEnrollment
from app.models.user import User


class TeachingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def verify_teacher(self, class_id: str, current_user: User) -> Course:
        result = await self.db.execute(
            select(Course).where(Course.id == class_id, Course.is_deleted == False)
        )
        course = result.scalar_one_or_none()
        if course is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 40400, "message": "课程不存在", "data": None},
            )
        if course.teacher_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": 40300, "message": "无权访问此班级", "data": None},
            )
        return course

    async def list_students(self, class_id: str, current_user: User, page: int, page_size: int) -> dict:
        await self.verify_teacher(class_id, current_user)

        count_r = await self.db.execute(
            select(func.count(CourseEnrollment.id)).where(
                CourseEnrollment.course_id == class_id,
                CourseEnrollment.is_deleted == False,
            )
        )
        total = count_r.scalar() or 0

        result = await self.db.execute(
            select(CourseEnrollment)
            .where(
                CourseEnrollment.course_id == class_id,
                CourseEnrollment.is_deleted == False,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        enrollments = result.scalars().all()

        students = []
        for enrollment in enrollments:
            user_result = await self.db.execute(select(User).where(User.id == enrollment.student_id))
            user = user_result.scalar_one_or_none()
            if user:
                students.append(_student_list_item(user, enrollment))

        return {"students": students, "total": total, "page": page, "page_size": page_size}

    async def get_student_info(self, class_id: str, student_id: str, current_user: User) -> dict:
        await self.verify_teacher(class_id, current_user)

        result = await self.db.execute(select(User).where(User.id == student_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 40400, "message": "学生不存在", "data": None},
            )
        return _student_info_item(user)


def _student_list_item(user: User, enrollment: CourseEnrollment) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name,
        "student_id": user.student_id,
        "major": user.major,
        "grade": user.grade,
        "joined_at": enrollment.create_time.isoformat() if enrollment.create_time else "",
    }


def _student_info_item(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "real_name": user.real_name,
        "student_id": user.student_id,
        "role": user.role,
        "major": user.major,
        "grade": user.grade,
        "guidance_level": user.guidance_level,
        "created_at": user.create_time.isoformat() if user.create_time else "",
    }
```

- [ ] **Step 2: Run focused tests**

Run:

```bash
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/teaching_service_task2.db ../.venv/bin/python -m pytest tests/test_teaching_service.py -q -p no:cacheprovider
```

Expected: PASS for the tests currently in the file.

- [ ] **Step 3: Commit the first green service slice**

```bash
git -C .. add backend/app/services/teaching_service.py backend/tests/test_teaching_service.py
git -C .. commit -m "refactor: 新增 teaching service 基础查询"
```

---

### Task 3: Add Student Learning Service Tests

**Files:**
- Modify: `../backend/tests/test_teaching_service.py`
- Production implementation still incomplete at the start of this task.

- [ ] **Step 1: Extend imports**

Add these imports below existing model imports:

```python
from app.models.others import Evaluation, LearningPath, UserProfile
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
```

- [ ] **Step 2: Add student learning aggregation tests**

Append:

```python
@pytest.mark.asyncio
async def test_get_student_learning_aggregates_quiz_profile_path_and_recent_activity():
    async with async_session_factory() as db:
        teacher, _other_teacher, _admin, course = await _seed_course_with_teacher(db)
        student = await _seed_user(db, "student", "student")
        db.add(CourseEnrollment(course_id=course.id, student_id=student.id))
        await db.flush()

        db.add(Evaluation(user_id=student.id, course_id=course.id, summary_text="latest summary"))
        db.add(UserProfile(
            user_id=student.id,
            course_id=course.id,
            modal_preference={"text_analysis": 80, "code_practice": 60},
            knowledge_coordinates=[
                {"knowledge_point": "A", "status": "mastered"},
                {"knowledge_point": "B", "status": "weak"},
            ],
        ))
        db.add(LearningPath(
            user_id=student.id,
            course_id=course.id,
            current_node_name="Node 2",
            nodes=[
                {"id": "n1", "status": "completed"},
                {"id": "n2", "status": "in_progress"},
            ],
        ))
        await db.flush()

        first_session = QuizSession(
            user_id=student.id,
            course_id=course.id,
            chapter="ch1",
            score=50,
            correct_count=1,
            total_count=2,
            time_spent=60,
        )
        db.add(first_session)
        await db.flush()

        q1 = QuizQuestion(course_id=course.id, chapter="ch1", knowledge_point="AVL树旋转", type="single_choice", content="Q1?", options=["A", "B"], correct_answer="A")
        q2 = QuizQuestion(course_id=course.id, chapter="ch1", knowledge_point="AVL树旋转", type="single_choice", content="Q2?", options=["A", "B"], correct_answer="A")
        q3 = QuizQuestion(course_id=course.id, chapter="ch1", knowledge_point="", type="single_choice", content="Q3?", options=["A", "B"], correct_answer="A")
        db.add_all([q1, q2, q3])
        await db.flush()
        db.add_all([
            QuizAnswer(quiz_id=first_session.id, question_id=q1.id, user_answer="B", is_correct=False, correct_answer="A"),
            QuizAnswer(quiz_id=first_session.id, question_id=q2.id, user_answer="A", is_correct=True, correct_answer="A"),
            QuizAnswer(quiz_id=first_session.id, question_id=q3.id, user_answer="B", is_correct=False, correct_answer="A"),
        ])

        for index in range(6):
            db.add(QuizSession(user_id=student.id, course_id=course.id, chapter=f"recent-{index}", score=80, correct_count=3, total_count=4, time_spent=30))
        await db.commit()

        data = await TeachingService(db).get_student_learning(course.id, student.id, teacher)

        assert data["student"] == {"id": student.id, "real_name": student.real_name, "student_id": student.student_id}
        assert data["evaluation_summary"]["overall_score"] == 75.0
        assert data["evaluation_summary"]["summary_text"] == "latest summary"
        assert data["profile_summary"]["knowledge_mastered"] == 1
        assert data["profile_summary"]["knowledge_weak"] == 1
        assert data["profile_summary"]["modal_preference"] == ["text_analysis", "code_practice"]
        assert data["path_progress"] == {"current_node": "Node 2", "completed_nodes": 1, "total_nodes": 2}

        assert data["quiz_stats"]["total_attempts"] == 7
        assert data["quiz_stats"]["mastery_breakdown"] == [{"knowledge_point": "AVL树旋转", "accuracy": 50.0}]
        assert data["weak_points"] == [{"knowledge_point": "AVL树旋转", "error_count": 1, "total_attempts": 2, "error_rate": 0.5}]
        assert len(data["recent_activity"]) == 5
        recent_dates = [item["created_at"] for item in data["recent_activity"]]
        assert all(recent_dates[i] >= recent_dates[i + 1] for i in range(len(recent_dates) - 1))


@pytest.mark.asyncio
async def test_get_student_learning_raises_404_for_non_enrolled_student():
    async with async_session_factory() as db:
        teacher, _other_teacher, _admin, course = await _seed_course_with_teacher(db)
        student = await _seed_user(db, "student", "student")
        await db.commit()

        with pytest.raises(HTTPException) as exc:
            await TeachingService(db).get_student_learning(course.id, student.id, teacher)
        assert exc.value.status_code == 404
        assert exc.value.detail == {"code": 40400, "message": "学生未入班", "data": None}
```

- [ ] **Step 3: Run tests and verify red**

Run:

```bash
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/teaching_service_task3_red.db ../.venv/bin/python -m pytest tests/test_teaching_service.py -q -p no:cacheprovider
```

Expected: FAIL with `AttributeError: 'TeachingService' object has no attribute 'get_student_learning'`.

- [ ] **Step 4: Leave red learning tests unstaged until Task 4 is green**

Do not commit at this point. Keep the red learning tests in the working tree and continue directly to Task 4.

---

### Task 4: Implement Student Learning Aggregation In TeachingService

**Files:**
- Modify: `../backend/app/services/teaching_service.py`
- Test: `../backend/tests/test_teaching_service.py`

- [ ] **Step 1: Add required imports**

Add to `teaching_service.py`:

```python
from sqlalchemy import case

from app.models.others import Evaluation, LearningPath, UserProfile
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
```

- [ ] **Step 2: Add `get_student_learning` by moving existing route logic**

Add this method to `TeachingService`. Keep the logic equivalent to current `teaching.py`; do not optimize the queries.

```python
    async def get_student_learning(self, class_id: str, student_id: str, current_user: User) -> dict:
        await self.verify_teacher(class_id, current_user)

        enrollment_check = await self.db.execute(
            select(CourseEnrollment).where(
                CourseEnrollment.student_id == student_id,
                CourseEnrollment.course_id == class_id,
                CourseEnrollment.is_deleted == False,
            )
        )
        if not enrollment_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 40400, "message": "学生未入班", "data": None},
            )

        user_result = await self.db.execute(select(User).where(User.id == student_id))
        user = user_result.scalar_one_or_none()
        student_info = {}
        if user:
            student_info = {"id": user.id, "real_name": user.real_name, "student_id": user.student_id}

        ev_result = await self.db.execute(
            select(Evaluation)
            .where(Evaluation.user_id == student_id, Evaluation.course_id == class_id, Evaluation.is_deleted == False)
            .order_by(Evaluation.generated_at.desc())
        )
        evaluation = ev_result.scalars().first()
        evaluation_summary = None
        if evaluation:
            evaluation_summary = {
                "overall_score": 75.0,
                "generated_at": evaluation.generated_at.isoformat() if evaluation.generated_at else None,
                "summary_text": evaluation.summary_text or None,
            }

        profile_result = await self.db.execute(
            select(UserProfile).where(
                UserProfile.user_id == student_id,
                UserProfile.course_id == class_id,
                UserProfile.is_deleted == False,
            )
        )
        profile = profile_result.scalar_one_or_none()
        profile_summary = None
        if profile:
            coordinates = profile.knowledge_coordinates if profile.knowledge_coordinates else []
            mastered = sum(1 for coordinate in coordinates if coordinate.get("status") == "mastered")
            weak = len(coordinates) - mastered
            profile_summary = {
                "knowledge_mastered": mastered,
                "knowledge_weak": weak,
                "modal_preference": list(profile.modal_preference.keys()) if profile.modal_preference else [],
                "knowledge_coordinates": coordinates,
            }

        path_result = await self.db.execute(
            select(LearningPath).where(
                LearningPath.user_id == student_id,
                LearningPath.course_id == class_id,
                LearningPath.is_deleted == False,
            )
        )
        learning_path = path_result.scalar_one_or_none()
        path_progress = None
        if learning_path and learning_path.nodes:
            nodes = learning_path.nodes if isinstance(learning_path.nodes, list) else []
            completed = sum(1 for node in nodes if node.get("status") == "completed")
            path_progress = {
                "current_node": learning_path.current_node_name,
                "completed_nodes": completed,
                "total_nodes": len(nodes),
            }

        quiz_sessions_result = await self.db.execute(
            select(QuizSession).where(
                QuizSession.user_id == student_id,
                QuizSession.course_id == class_id,
                QuizSession.is_deleted == False,
            )
        )
        quiz_sessions = quiz_sessions_result.scalars().all()

        mastery_breakdown = await self._mastery_breakdown(student_id, class_id)
        quiz_stats = None
        if quiz_sessions:
            total_attempts = len(quiz_sessions)
            avg_score = sum(session.score for session in quiz_sessions) / total_attempts
            avg_time = sum(session.time_spent for session in quiz_sessions) / total_attempts
            quiz_stats = {
                "total_attempts": total_attempts,
                "avg_score": round(avg_score, 1),
                "avg_time_spent": int(avg_time),
                "mastery_breakdown": mastery_breakdown,
            }

        return {
            "student": student_info,
            "evaluation_summary": evaluation_summary,
            "profile_summary": profile_summary,
            "path_progress": path_progress,
            "quiz_stats": quiz_stats,
            "weak_points": await self._weak_points(student_id, class_id),
            "recent_activity": await self._recent_activity(student_id, class_id),
        }
```

- [ ] **Step 3: Add private query helpers used by the method**

Add inside the class:

```python
    async def _mastery_breakdown(self, student_id: str, class_id: str) -> list[dict]:
        result = await self.db.execute(
            select(
                QuizQuestion.knowledge_point,
                func.count(QuizAnswer.id).label("total"),
                func.sum(case((QuizAnswer.is_correct == True, 1), else_=0)).label("correct"),
            )
            .join(QuizAnswer, QuizAnswer.question_id == QuizQuestion.id)
            .join(QuizSession, QuizSession.id == QuizAnswer.quiz_id)
            .where(
                QuizSession.user_id == student_id,
                QuizSession.course_id == class_id,
                QuizSession.is_deleted == False,
                QuizAnswer.is_deleted == False,
                QuizQuestion.is_deleted == False,
                QuizQuestion.knowledge_point != "",
            )
            .group_by(QuizQuestion.knowledge_point)
        )
        breakdown = []
        for row in result:
            total = row.total or 0
            correct = row.correct or 0
            breakdown.append({
                "knowledge_point": row.knowledge_point,
                "accuracy": round(correct / total * 100, 1) if total > 0 else 0,
            })
        return breakdown

    async def _weak_points(self, student_id: str, class_id: str) -> list[dict]:
        error_count_expr = func.sum(case((QuizAnswer.is_correct == False, 1), else_=0))
        total_attempts_expr = func.count(QuizAnswer.id)
        result = await self.db.execute(
            select(
                QuizQuestion.knowledge_point,
                total_attempts_expr.label("total_attempts"),
                error_count_expr.label("error_count"),
            )
            .join(QuizAnswer, QuizAnswer.question_id == QuizQuestion.id)
            .join(QuizSession, QuizSession.id == QuizAnswer.quiz_id)
            .where(
                QuizSession.user_id == student_id,
                QuizSession.course_id == class_id,
                QuizSession.is_deleted == False,
                QuizAnswer.is_deleted == False,
                QuizQuestion.is_deleted == False,
                QuizQuestion.knowledge_point != "",
            )
            .group_by(QuizQuestion.knowledge_point)
            .having(error_count_expr > 0)
            .order_by((error_count_expr / total_attempts_expr).desc(), error_count_expr.desc())
            .limit(5)
        )
        return [_weak_point_item(row) for row in result]

    async def _recent_activity(self, student_id: str, class_id: str) -> list[dict]:
        result = await self.db.execute(
            select(QuizSession)
            .where(
                QuizSession.user_id == student_id,
                QuizSession.course_id == class_id,
                QuizSession.is_deleted == False,
            )
            .order_by(QuizSession.create_time.desc())
            .limit(5)
        )
        return [_recent_activity_item(session) for session in result.scalars().all()]
```

Add module-level helpers:

```python
def _weak_point_item(row) -> dict:
    total = row.total_attempts
    errors = row.error_count or 0
    return {
        "knowledge_point": row.knowledge_point,
        "error_count": errors,
        "total_attempts": total,
        "error_rate": round(errors / total, 2) if total > 0 else 0,
    }


def _recent_activity_item(session: QuizSession) -> dict:
    return {
        "quiz_id": session.id,
        "chapter": session.chapter or "",
        "score": session.score,
        "correct_count": session.correct_count,
        "total_count": session.total_count,
        "time_spent": session.time_spent,
        "created_at": session.create_time.isoformat() if session.create_time else "",
    }
```

- [ ] **Step 4: Run service tests**

Run:

```bash
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/teaching_service_task4.db ../.venv/bin/python -m pytest tests/test_teaching_service.py -q -p no:cacheprovider
```

Expected: PASS for all current service tests.

- [ ] **Step 5: Commit learning service implementation and its tests**

```bash
git -C .. add backend/app/services/teaching_service.py backend/tests/test_teaching_service.py
git -C .. commit -m "refactor: 迁移教师端学生学习报告查询"
```

---

### Task 5: Add And Implement Class Insights Service Tests

**Files:**
- Modify: `../backend/tests/test_teaching_service.py`
- Modify: `../backend/app/services/teaching_service.py`

- [ ] **Step 1: Add class insights test**

Append:

```python
@pytest.mark.asyncio
async def test_get_class_insights_aggregates_quiz_weak_points_and_path_progress():
    async with async_session_factory() as db:
        teacher, _other_teacher, _admin, course = await _seed_course_with_teacher(db)
        student1 = await _seed_user(db, "student", "student1")
        student2 = await _seed_user(db, "student", "student2")
        db.add_all([
            CourseEnrollment(course_id=course.id, student_id=student1.id),
            CourseEnrollment(course_id=course.id, student_id=student2.id, is_deleted=True),
        ])
        await db.flush()

        session1 = QuizSession(user_id=student1.id, course_id=course.id, chapter="ch1", score=60, correct_count=3, total_count=5, time_spent=120)
        session2 = QuizSession(user_id=student2.id, course_id=course.id, chapter="ch1", score=100, correct_count=5, total_count=5, time_spent=90)
        db.add_all([session1, session2])
        await db.flush()

        question = QuizQuestion(course_id=course.id, chapter="ch1", knowledge_point="AVL树旋转", type="single_choice", content="Q?", options=["A", "B"], correct_answer="A")
        empty_question = QuizQuestion(course_id=course.id, chapter="ch1", knowledge_point="", type="single_choice", content="Empty?", options=["A", "B"], correct_answer="A")
        db.add_all([question, empty_question])
        await db.flush()
        db.add_all([
            QuizAnswer(quiz_id=session1.id, question_id=question.id, user_answer="B", is_correct=False, correct_answer="A"),
            QuizAnswer(quiz_id=session1.id, question_id=empty_question.id, user_answer="B", is_correct=False, correct_answer="A"),
            QuizAnswer(quiz_id=session2.id, question_id=question.id, user_answer="B", is_correct=False, correct_answer="A"),
        ])
        db.add_all([
            LearningPath(user_id=student1.id, course_id=course.id, nodes=[
                {"id": "n1", "status": "completed"},
                {"id": "n2", "status": "in_progress"},
                {"id": "n3", "status": "unknown_status"},
            ]),
            LearningPath(user_id=student2.id, course_id=course.id, nodes=[
                {"id": "n1", "status": "completed"},
            ]),
        ])
        await db.commit()

        data = await TeachingService(db).get_class_insights(course.id, teacher)

        assert data["avg_quiz_score"] == 60.0
        assert data["total_quiz_attempts"] == 1
        assert data["weak_points_top"] == [{"knowledge_point": "AVL树旋转", "error_count": 1, "total_attempts": 1, "error_rate": 1.0}]
        assert data["path_node_progress"] == {
            "completed": 1,
            "in_progress": 1,
            "recommended": 0,
            "pending": 0,
            "total_nodes": 2,
        }


@pytest.mark.asyncio
async def test_get_class_insights_returns_empty_shape_for_empty_class():
    async with async_session_factory() as db:
        teacher, _other_teacher, _admin, course = await _seed_course_with_teacher(db)
        await db.commit()

        data = await TeachingService(db).get_class_insights(course.id, teacher)

        assert data == {
            "avg_quiz_score": None,
            "total_quiz_attempts": 0,
            "weak_points_top": [],
            "path_node_progress": {
                "completed": 0,
                "in_progress": 0,
                "recommended": 0,
                "pending": 0,
                "total_nodes": 0,
            },
        }
```

- [ ] **Step 2: Run tests and verify red**

Run:

```bash
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/teaching_service_task5_red.db ../.venv/bin/python -m pytest tests/test_teaching_service.py -q -p no:cacheprovider
```

Expected: FAIL with `AttributeError: 'TeachingService' object has no attribute 'get_class_insights'`.

- [ ] **Step 3: Implement `get_class_insights`**

Add inside `TeachingService`:

```python
    async def get_class_insights(self, class_id: str, current_user: User) -> dict:
        await self.verify_teacher(class_id, current_user)

        enrolled_result = await self.db.execute(
            select(CourseEnrollment.student_id).where(
                CourseEnrollment.course_id == class_id,
                CourseEnrollment.is_deleted == False,
            )
        )
        student_ids = [row[0] for row in enrolled_result.all()]

        if not student_ids:
            return _empty_class_insights()

        quiz_result = await self.db.execute(
            select(
                func.avg(QuizSession.score).label("avg_score"),
                func.count(QuizSession.id).label("total_attempts"),
            ).where(
                QuizSession.course_id == class_id,
                QuizSession.user_id.in_(student_ids),
                QuizSession.is_deleted == False,
            )
        )
        quiz_row = quiz_result.one()
        avg_quiz_score = round(quiz_row.avg_score, 1) if quiz_row.avg_score is not None else None
        total_quiz_attempts = quiz_row.total_attempts or 0

        return {
            "avg_quiz_score": avg_quiz_score,
            "total_quiz_attempts": total_quiz_attempts,
            "weak_points_top": await self._class_weak_points_top(class_id, student_ids),
            "path_node_progress": await self._class_path_node_progress(class_id, student_ids),
        }
```

Add inside the class:

```python
    async def _class_weak_points_top(self, class_id: str, student_ids: list[str]) -> list[dict]:
        error_count_expr = func.sum(case((QuizAnswer.is_correct == False, 1), else_=0))
        total_attempts_expr = func.count(QuizAnswer.id)
        result = await self.db.execute(
            select(
                QuizQuestion.knowledge_point,
                total_attempts_expr.label("total_attempts"),
                error_count_expr.label("error_count"),
            )
            .join(QuizAnswer, QuizAnswer.question_id == QuizQuestion.id)
            .join(QuizSession, QuizSession.id == QuizAnswer.quiz_id)
            .where(
                QuizSession.course_id == class_id,
                QuizSession.user_id.in_(student_ids),
                QuizSession.is_deleted == False,
                QuizAnswer.is_deleted == False,
                QuizQuestion.is_deleted == False,
                QuizQuestion.knowledge_point != "",
            )
            .group_by(QuizQuestion.knowledge_point)
            .having(error_count_expr > 0)
            .order_by((error_count_expr / total_attempts_expr).desc(), error_count_expr.desc())
            .limit(5)
        )
        return [_weak_point_item(row) for row in result]

    async def _class_path_node_progress(self, class_id: str, student_ids: list[str]) -> dict:
        result = await self.db.execute(
            select(LearningPath).where(
                LearningPath.course_id == class_id,
                LearningPath.user_id.in_(student_ids),
                LearningPath.is_deleted == False,
            )
        )
        known_statuses = {"completed", "in_progress", "recommended", "pending"}
        progress = {status_name: 0 for status_name in known_statuses}
        for learning_path in result.scalars().all():
            nodes = learning_path.nodes if isinstance(learning_path.nodes, list) else []
            for node in nodes:
                node_status = node.get("status")
                if node_status in known_statuses:
                    progress[node_status] += 1
        return {**progress, "total_nodes": sum(progress.values())}
```

Add module-level helper:

```python
def _empty_class_insights() -> dict:
    return {
        "avg_quiz_score": None,
        "total_quiz_attempts": 0,
        "weak_points_top": [],
        "path_node_progress": {
            "completed": 0,
            "in_progress": 0,
            "recommended": 0,
            "pending": 0,
            "total_nodes": 0,
        },
    }
```

- [ ] **Step 4: Run service tests**

Run:

```bash
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/teaching_service_task5.db ../.venv/bin/python -m pytest tests/test_teaching_service.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 5: Commit class insights service implementation**

```bash
git -C .. add backend/app/services/teaching_service.py backend/tests/test_teaching_service.py
git -C .. commit -m "refactor: 迁移教师端班级洞察查询"
```

---

### Task 6: Thin The Teaching Router

**Files:**
- Modify: `../backend/app/api/v1/teaching.py`
- Test: `../backend/tests/test_api.py`, `../backend/tests/test_teacher_student_learning.py`, `../backend/tests/test_teacher_class_insights.py`

- [ ] **Step 1: Replace route internals with service calls**

Rewrite `teaching.py` to keep only imports needed by the router and the five routes:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.models.user import User
from app.services.teaching_service import TeachingService

router = APIRouter(prefix="/api/v1/teaching", tags=["teaching"])


@router.get("/classes/{class_id}/students")
async def list_students(
    class_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    data = await TeachingService(db).list_students(class_id, current_user, page, page_size)
    return {"code": 200, "message": "success", "data": data}


@router.get("/classes/{class_id}/students/{student_id}")
async def get_student_info(
    class_id: str,
    student_id: str,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    data = await TeachingService(db).get_student_info(class_id, student_id, current_user)
    return {"code": 200, "message": "success", "data": data}


@router.get("/classes/{class_id}/students/{student_id}/learning")
async def get_student_learning(
    class_id: str,
    student_id: str,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    data = await TeachingService(db).get_student_learning(class_id, student_id, current_user)
    return {"code": 200, "message": "success", "data": data}


@router.get("/classes/{class_id}/insights")
async def get_class_insights(
    class_id: str,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    data = await TeachingService(db).get_class_insights(class_id, current_user)
    return {"code": 200, "message": "success", "data": data}
```

- [ ] **Step 2: Run syntax check**

Run:

```bash
../.venv/bin/python -m py_compile app/api/v1/teaching.py app/services/teaching_service.py
```

Expected: no output and exit code 0.

- [ ] **Step 3: Run service and API regressions**

Run:

```bash
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/teaching_service_task6.db ../.venv/bin/python -m pytest tests/test_teaching_service.py -q -p no:cacheprovider
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/teacher_student_learning_task6.db ../.venv/bin/python -m pytest tests/test_teacher_student_learning.py -q -p no:cacheprovider
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/teacher_class_insights_task6.db ../.venv/bin/python -m pytest tests/test_teacher_class_insights.py -q -p no:cacheprovider
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/api_teaching_task6.db ../.venv/bin/python -m pytest tests/test_api.py -q -p no:cacheprovider
```

Expected: all PASS.

- [ ] **Step 4: Check router line count**

Run:

```bash
wc -l app/api/v1/teaching.py app/services/teaching_service.py
```

Expected: `app/api/v1/teaching.py` is close to 100-140 lines or lower. If it is slightly below 100 because imports are minimal, that is acceptable.

- [ ] **Step 5: Commit router thinning**

```bash
git -C .. add backend/app/api/v1/teaching.py backend/app/services/teaching_service.py backend/tests/test_teaching_service.py
git -C .. commit -m "refactor: 瘦身 teaching 路由"
```

---

### Task 7: Record Workflow And Final Verification

**Files:**
- Modify: `WORKFLOW.md`

- [ ] **Step 1: Append workflow entry**

Append an entry with this content shape:

```markdown
## 2026-06-18 TeachingService 分层重构

- 修改文件：
  - `backend/app/api/v1/teaching.py`
  - `backend/app/services/teaching_service.py`
  - `backend/tests/test_teaching_service.py`
- 核心改动：
  - 将教师端学生列表、学生详情、学生学习报告、班级洞察查询从胖路由迁移到 `TeachingService`。
  - `teaching.py` 保留 FastAPI route、Depends、Query 参数和标准 JSON wrapper。
  - 保持 admin 非任课教师仍 403、学生未入班 404、weak points/learning path 聚合字段不变。
  - `list_students` 的 N+1 查询按等价迁移保留，未在本次重构中优化。
- 测试结果：
  - `../.venv/bin/python -m py_compile app/api/v1/teaching.py app/services/teaching_service.py` 通过。
  - `TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/teaching_service_task6.db ../.venv/bin/python -m pytest tests/test_teaching_service.py -q -p no:cacheprovider` 通过。
  - `TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/teacher_student_learning_task6.db ../.venv/bin/python -m pytest tests/test_teacher_student_learning.py -q -p no:cacheprovider` 通过。
  - `TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/teacher_class_insights_task6.db ../.venv/bin/python -m pytest tests/test_teacher_class_insights.py -q -p no:cacheprovider` 通过。
  - `TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/api_teaching_task6.db ../.venv/bin/python -m pytest tests/test_api.py -q -p no:cacheprovider` 通过。
- 接口漂移：无。API 路径、参数、响应字段、错误 detail 和 HTTP status 保持不变。
```

If any command fails and is then fixed, record the final passing command and the fixed failure in the same entry.

- [ ] **Step 2: Run final verification**

Run again from `../backend`:

```bash
../.venv/bin/python -m py_compile app/api/v1/teaching.py app/services/teaching_service.py
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/teaching_service_final.db ../.venv/bin/python -m pytest tests/test_teaching_service.py tests/test_teacher_student_learning.py tests/test_teacher_class_insights.py tests/test_api.py -q -p no:cacheprovider
```

Expected: syntax check passes and all selected tests pass.

- [ ] **Step 3: Inspect changed files**

Run:

```bash
git -C .. diff --stat
git -C .. diff -- backend/app/api/v1/teaching.py backend/app/services/teaching_service.py backend/tests/test_teaching_service.py frontend/WORKFLOW.md
```

Expected: only intended teaching service refactor and workflow entry changes.

- [ ] **Step 4: Commit workflow and any final verification-only fixes**

```bash
git -C .. add frontend/WORKFLOW.md
git -C .. commit -m "docs: 记录 teaching service 重构"
```

If final verification required a code/test fix, include those fixed files in the same commit with message:

```bash
git -C .. add frontend/WORKFLOW.md backend/app/api/v1/teaching.py backend/app/services/teaching_service.py backend/tests/test_teaching_service.py
git -C .. commit -m "fix: 完成 teaching service 重构验证"
```

---

## Final Acceptance Checklist

- [ ] `backend/app/api/v1/teaching.py` no longer imports `case`, `func`, `select`, `Course`, `CourseEnrollment`, `Evaluation`, `LearningPath`, `UserProfile`, `QuizAnswer`, `QuizQuestion`, or `QuizSession`.
- [ ] `backend/app/api/v1/teaching.py` route functions only construct `TeachingService(db)`, call one service method, and return the wrapper.
- [ ] `backend/app/services/teaching_service.py` preserves current HTTPException details.
- [ ] `backend/tests/test_teaching_service.py` covers `verify_teacher`, `list_students`, `get_student_info`, `get_student_learning`, and `get_class_insights`.
- [ ] Existing API regression tests pass.
- [ ] `WORKFLOW.md` records no interface drift.
