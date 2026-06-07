# TeacherConsole Class Insights 最小聚合 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a class-level SQL aggregation endpoint `GET /api/v1/teaching/classes/{class_id}/insights` and wire the frontend `TeacherConsole` to display real class statistics (avg quiz score, quiz attempts, weak points top 5, path node progress), replacing the current `useMock &&` guard and `data: null` stub.

**Architecture:** Three sequential layers — OpenAPI contract first, then backend route with SQL aggregation, then frontend service + page integration. All aggregation is pure SQL over existing tables (`CourseEnrollment`, `QuizSession`, `QuizAnswer`, `QuizQuestion`, `LearningPath`). No Agent API dependency.

**Tech Stack:** FastAPI + SQLAlchemy async (backend), React 19 + Vite (frontend), OpenAPI 3.0 JSON schema.

**Design spec:** `docs/superpowers/specs/2026-06-06-teacher-console-class-insights-design.md`

---

## Task 顺序说明

本 plan 采用 **contract-first** 而非严格 TDD 顺序。理由：

1. OpenAPI 契约是 Backend 实现和 Frontend 接入的共同参考，先落契约可以让 Task 2（测试）和 Task 3（实现）都直接对照字段名和类型编写，减少对齐成本。
2. Task 2 仍然是红灯测试先行——只是它基于 Task 1 已确认的 schema 来写断言。
3. 如果严格 TDD 则测试应在契约之前写，但本端点的测试断言直接依赖响应结构体命名（`avg_quiz_score`、`path_node_progress` 等），先定契约让测试不需要猜。

这是一个 **contract-first 例外**，不是跳过 TDD。红灯→绿灯→重构的节奏从 Task 2 开始仍然严格遵守。

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `docs/10-client-api/Client-API.openapi.json` | Add `/teaching/classes/{class_id}/insights` path + `ClassInsights`, `ClassWeakPoint`, `PathNodeProgress` schemas |
| Modify | `backend/app/api/v1/teaching.py` | Add `get_class_insights` route with SQL aggregation |
| Create | `backend/tests/test_teacher_class_insights.py` | Integration tests: permissions, empty state, aggregation correctness |
| Modify | `frontend/src/api/services/teaching.js` | Wire `getConsoleInsights` real mode to `/teaching/classes/${courseId}/insights` |
| Modify | `frontend/src/pages/TeacherConsole.jsx` | Remove `useMock &&` guard on Insights section, split error handling, render class statistics |

---

## Task 1: OpenAPI Contract — Add ClassInsights Schemas and Path

**Files:**
- Modify: `docs/10-client-api/Client-API.openapi.json`

- [ ] **Step 1: Add component schemas**

Open `docs/10-client-api/Client-API.openapi.json`. Add three new schemas under `components.schemas`:

```json
"ClassWeakPoint": {
  "type": "object",
  "required": ["knowledge_point", "error_count", "total_attempts", "error_rate"],
  "properties": {
    "knowledge_point": {
      "type": "string",
      "description": "知识点名称"
    },
    "error_count": {
      "type": "integer",
      "description": "班级错题数"
    },
    "total_attempts": {
      "type": "integer",
      "description": "班级该知识点答题总次数"
    },
    "error_rate": {
      "type": "number",
      "description": "错误率 0-1"
    }
  }
},
"PathNodeProgress": {
  "type": "object",
  "required": ["completed", "in_progress", "recommended", "pending", "total_nodes"],
  "properties": {
    "completed": { "type": "integer" },
    "in_progress": { "type": "integer" },
    "recommended": { "type": "integer" },
    "pending": { "type": "integer" },
    "total_nodes": { "type": "integer" }
  }
},
"ClassInsights": {
  "type": "object",
  "required": ["avg_quiz_score", "total_quiz_attempts", "weak_points_top", "path_node_progress"],
  "properties": {
    "avg_quiz_score": {
      "type": "number",
      "nullable": true,
      "description": "班级平均练习分；无练习时为 null"
    },
    "total_quiz_attempts": {
      "type": "integer",
      "description": "班级练习总次数"
    },
    "weak_points_top": {
      "type": "array",
      "items": { "$ref": "#/components/schemas/ClassWeakPoint" },
      "description": "班级薄弱知识点 Top 5"
    },
    "path_node_progress": {
      "$ref": "#/components/schemas/PathNodeProgress",
      "description": "班级路径节点状态分布"
    }
  }
}
```

- [ ] **Step 2: Add path entry**

Add a new path under `paths`:

```json
"/teaching/classes/{class_id}/insights": {
  "get": {
    "tags": ["teaching"],
    "summary": "获取班级统计洞察",
    "operationId": "getClassInsights",
    "parameters": [
      {
        "name": "class_id",
        "in": "path",
        "required": true,
        "schema": { "type": "string" },
        "description": "课程 ID"
      }
    ],
    "responses": {
      "200": {
        "description": "成功",
        "content": {
          "application/json": {
            "schema": {
              "type": "object",
              "properties": {
                "code": { "type": "integer", "example": 200 },
                "message": { "type": "string", "example": "success" },
                "data": { "$ref": "#/components/schemas/ClassInsights" }
              }
            }
          }
        }
      },
      "401": { "description": "未登录或角色不符" },
      "403": { "description": "非该课程教师，无权查看" },
      "404": { "description": "课程不存在" }
    },
    "security": [{ "bearerAuth": [] }]
  }
}
```

- [ ] **Step 3: Validate JSON**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent && python3 -c "import json; json.load(open('docs/10-client-api/Client-API.openapi.json')); print('JSON valid')"
```
Expected: `JSON valid`

- [ ] **Step 4: Commit**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add docs/10-client-api/Client-API.openapi.json
git commit -m "docs: add ClassInsights OpenAPI contract for GET /teaching/classes/{class_id}/insights"
```

---

## Task 2: Backend — Write Failing Tests

**Files:**
- Create: `backend/tests/test_teacher_class_insights.py`

This test file follows the same pattern as `backend/tests/test_teacher_student_learning.py`: register users via HTTP, seed data via ORM, assert HTTP responses.

- [ ] **Step 1: Create test file with setup helpers and all test cases**

Create `backend/tests/test_teacher_class_insights.py`:

```python
"""Integration tests for GET /api/v1/teaching/classes/{class_id}/insights.

Covers: 404 course not found, 403 teacher not owner, empty class,
quiz aggregation, weak_points_top, path_node_progress, soft-delete filtering.

Run: python -m pytest tests/test_teacher_class_insights.py -v -s
"""
import asyncio
import os
import pytest
import re
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_class_insights.db",
)

from app.db.session import async_session_factory, init_db
from httpx import AsyncClient, ASGITransport

asyncio.run(init_db())

from app.main import app
from app.models.user import RegistrationCode
from app.models.course import CourseEnrollment
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.models.others import LearningPath


async def _captcha_answer(client):
    r = await client.get("/api/v1/auth/captcha")
    d = r.json()["data"]
    nums = re.findall(r"\d+", d["captcha_question"])
    ans = (
        str(int(nums[0]) + int(nums[1]))
        if "+" in d["captcha_question"]
        else str(int(nums[0]) - int(nums[1]))
    )
    return d["captcha_token"], ans


async def _register_and_login(client, code, email, username):
    ct_token, ct_ans = await _captcha_answer(client)
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "registration_code": code,
            "email": email,
            "password": "Abc12345",
            "username": username,
            "captcha_token": ct_token,
            "captcha_code": ct_ans,
        },
    )
    assert r.status_code == 201, f"Register failed: {r.status_code} {r.json()}"
    user_id = r.json()["data"]["user_id"]
    ct_token, ct_ans = await _captcha_answer(client)
    r = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "Abc12345",
            "captcha_token": ct_token,
            "captcha_code": ct_ans,
        },
    )
    assert "token" in r.json().get("data", {}), f"Login failed: {r.json()}"
    return {"Authorization": f"Bearer {r.json()['data']['token']}"}, user_id


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.mark.asyncio
async def test():
    transport = ASGITransport(app=app)
    ok = fail = 0

    def chk(name, cond):
        nonlocal ok, fail
        tag = "OK" if cond else "FAIL"
        print(f"  {tag}  {name}")
        if cond:
            ok += 1
        else:
            fail += 1
        return cond

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # ===== Seed users =====
        codes = [
            RegistrationCode(code=f"stu1_{_uid()}", role="student"),
            RegistrationCode(code=f"stu2_{_uid()}", role="student"),
            RegistrationCode(code=f"tea1_{_uid()}", role="teacher"),
            RegistrationCode(code=f"tea2_{_uid()}", role="teacher"),
        ]
        async with async_session_factory() as db:
            db.add_all(codes)
            await db.commit()

        stu1_headers, stu1_id = await _register_and_login(
            client, codes[0].code, f"s1_{_uid()}@t.com", f"s1_{_uid()}"
        )
        stu2_headers, stu2_id = await _register_and_login(
            client, codes[1].code, f"s2_{_uid()}@t.com", f"s2_{_uid()}"
        )
        tea1_headers, tea1_id = await _register_and_login(
            client, codes[2].code, f"t1_{_uid()}@t.com", f"t1_{_uid()}"
        )
        tea2_headers, tea2_id = await _register_and_login(
            client, codes[3].code, f"t2_{_uid()}@t.com", f"t2_{_uid()}"
        )

        # ===== Create course by tea1, enroll stu1 and stu2 =====
        r = await client.post(
            "/api/v1/courses", json={"name": "Insights Test"}, headers=tea1_headers
        )
        assert r.status_code == 201
        course_id = r.json()["data"]["id"]
        course_code = r.json()["data"].get("course_code", "")

        await client.post(
            "/api/v1/courses/join",
            json={"course_code": course_code},
            headers=stu1_headers,
        )
        await client.post(
            "/api/v1/courses/join",
            json={"course_code": course_code},
            headers=stu2_headers,
        )

        URL = f"/api/v1/teaching/classes/{course_id}/insights"

        # ===== 1. 404 — course does not exist =====
        print("\n-- 1. 404 course not found --")
        r = await client.get(
            "/api/v1/teaching/classes/nonexistent_id/insights",
            headers=tea1_headers,
        )
        chk("404 course not found", r.status_code == 404)

        # ===== 2. 403 — tea2 is teacher but not course owner =====
        print("\n-- 2. 403 teacher not owner --")
        r = await client.get(URL, headers=tea2_headers)
        chk("403 teacher not owner", r.status_code == 403)

        # ===== 3. No quiz data — avg_quiz_score is null =====
        print("\n-- 3. No quiz data --")
        r = await client.get(URL, headers=tea1_headers)
        chk("200 no quiz data", r.status_code == 200)
        data = r.json()["data"]
        chk("avg_quiz_score is null", data["avg_quiz_score"] is None)
        chk("total_quiz_attempts is 0", data["total_quiz_attempts"] == 0)
        chk("weak_points_top is empty", data["weak_points_top"] == [])
        chk(
            "path_node_progress all zeros",
            data["path_node_progress"]["completed"] == 0
            and data["path_node_progress"]["in_progress"] == 0
            and data["path_node_progress"]["recommended"] == 0
            and data["path_node_progress"]["pending"] == 0
            and data["path_node_progress"]["total_nodes"] == 0,
        )

        # ===== 4. Seed quiz data for both students =====
        print("\n-- 4. Quiz aggregation --")
        async with async_session_factory() as db:
            qs1 = QuizSession(
                user_id=stu1_id,
                course_id=course_id,
                chapter="ch1",
                score=60,
                correct_count=3,
                total_count=5,
                time_spent=120,
            )
            qs2 = QuizSession(
                user_id=stu2_id,
                course_id=course_id,
                chapter="ch1",
                score=80,
                correct_count=4,
                total_count=5,
                time_spent=90,
            )
            db.add_all([qs1, qs2])
            await db.flush()

            q1 = QuizQuestion(
                course_id=course_id,
                chapter="ch1",
                knowledge_point="AVL树旋转",
                type="single_choice",
                content="Q1?",
                options=["A", "B", "C", "D"],
                correct_answer="A",
            )
            q2 = QuizQuestion(
                course_id=course_id,
                chapter="ch1",
                knowledge_point="AVL树旋转",
                type="single_choice",
                content="Q2?",
                options=["A", "B", "C", "D"],
                correct_answer="A",
            )
            q3 = QuizQuestion(
                course_id=course_id,
                chapter="ch1",
                knowledge_point="散列冲突",
                type="single_choice",
                content="Q3?",
                options=["A", "B", "C", "D"],
                correct_answer="A",
            )
            q4 = QuizQuestion(
                course_id=course_id,
                chapter="ch1",
                knowledge_point="",
                type="single_choice",
                content="Empty KP",
                options=["A", "B", "C", "D"],
                correct_answer="A",
            )
            db.add_all([q1, q2, q3, q4])
            await db.flush()

            answers = [
                # stu1: q1 wrong, q2 wrong, q3 wrong, q4 wrong (empty KP)
                QuizAnswer(quiz_id=qs1.id, question_id=q1.id, user_answer="B", is_correct=False, correct_answer="A"),
                QuizAnswer(quiz_id=qs1.id, question_id=q2.id, user_answer="B", is_correct=False, correct_answer="A"),
                QuizAnswer(quiz_id=qs1.id, question_id=q3.id, user_answer="B", is_correct=False, correct_answer="A"),
                QuizAnswer(quiz_id=qs1.id, question_id=q4.id, user_answer="B", is_correct=False, correct_answer="A"),
                # stu2: q1 correct, q2 wrong, q3 correct
                QuizAnswer(quiz_id=qs2.id, question_id=q1.id, user_answer="A", is_correct=True, correct_answer="A"),
                QuizAnswer(quiz_id=qs2.id, question_id=q2.id, user_answer="B", is_correct=False, correct_answer="A"),
                QuizAnswer(quiz_id=qs2.id, question_id=q3.id, user_answer="A", is_correct=True, correct_answer="A"),
            ]
            db.add_all(answers)
            await db.commit()

        r = await client.get(URL, headers=tea1_headers)
        chk("200 with quiz data", r.status_code == 200)
        data = r.json()["data"]

        chk("avg_quiz_score is 70.0", data["avg_quiz_score"] == 70.0)
        chk("total_quiz_attempts is 2", data["total_quiz_attempts"] == 2)

        # ===== 5. weak_points_top =====
        print("\n-- 5. weak_points_top --")
        wp = data["weak_points_top"]
        chk("weak_points_top non-empty", len(wp) > 0)
        chk("weak_points_top max 5", len(wp) <= 5)

        kp_names = [w["knowledge_point"] for w in wp]
        chk("empty KP filtered", "" not in kp_names)

        avl = [w for w in wp if w["knowledge_point"] == "AVL树旋转"]
        chk("AVL present", len(avl) == 1)
        if avl:
            # AVL: stu1 q1 wrong + q2 wrong, stu2 q1 correct + q2 wrong => error=3, total=4
            chk("AVL error_count=3", avl[0]["error_count"] == 3)
            chk("AVL total_attempts=4", avl[0]["total_attempts"] == 4)
            chk("AVL error_rate=0.75", avl[0]["error_rate"] == 0.75)

        hash_wp = [w for w in wp if w["knowledge_point"] == "散列冲突"]
        chk("散列冲突 present", len(hash_wp) == 1)
        if hash_wp:
            # 散列冲突: stu1 wrong, stu2 correct => error=1, total=2
            chk("散列 error_count=1", hash_wp[0]["error_count"] == 1)
            chk("散列 total_attempts=2", hash_wp[0]["total_attempts"] == 2)
            chk("散列 error_rate=0.5", hash_wp[0]["error_rate"] == 0.5)

        # Verify sorted by error_rate DESC
        if len(wp) >= 2:
            chk(
                "sorted by error_rate DESC",
                wp[0]["error_rate"] >= wp[1]["error_rate"],
            )

        # ===== 6. path_node_progress =====
        print("\n-- 6. path_node_progress --")
        async with async_session_factory() as db:
            lp1 = LearningPath(
                user_id=stu1_id,
                course_id=course_id,
                nodes=[
                    {"id": "n1", "status": "completed"},
                    {"id": "n2", "status": "completed"},
                    {"id": "n3", "status": "in_progress"},
                    {"id": "n4", "status": "pending"},
                    {"id": "n5", "status": "unknown_status"},
                ],
            )
            lp2 = LearningPath(
                user_id=stu2_id,
                course_id=course_id,
                nodes=[
                    {"id": "n1", "status": "completed"},
                    {"id": "n2", "status": "recommended"},
                    {"id": "n3", "status": "recommended"},
                    {"id": "n4", "status": "pending"},
                ],
            )
            db.add_all([lp1, lp2])
            await db.commit()

        r = await client.get(URL, headers=tea1_headers)
        chk("200 with path data", r.status_code == 200)
        pnp = r.json()["data"]["path_node_progress"]
        # stu1: 2 completed, 1 in_progress, 0 recommended, 1 pending (unknown ignored)
        # stu2: 1 completed, 0 in_progress, 2 recommended, 1 pending
        # Total: 3 completed, 1 in_progress, 2 recommended, 2 pending
        chk("completed=3", pnp["completed"] == 3)
        chk("in_progress=1", pnp["in_progress"] == 1)
        chk("recommended=2", pnp["recommended"] == 2)
        chk("pending=2", pnp["pending"] == 2)
        chk("total_nodes=8", pnp["total_nodes"] == 8)

        # ===== 7. Soft-deleted enrollment excluded =====
        print("\n-- 7. Soft-deleted enrollment --")
        async with async_session_factory() as db:
            from sqlalchemy import select, update

            await db.execute(
                update(CourseEnrollment)
                .where(
                    CourseEnrollment.student_id == stu2_id,
                    CourseEnrollment.course_id == course_id,
                )
                .values(is_deleted=True)
            )
            await db.commit()

        r = await client.get(URL, headers=tea1_headers)
        chk("200 after soft-delete enrollment", r.status_code == 200)
        data_after = r.json()["data"]
        # Only stu1 remains: score=60, attempts=1
        chk("avg_quiz_score=60 after unenroll", data_after["avg_quiz_score"] == 60.0)
        chk("total_quiz_attempts=1 after unenroll", data_after["total_quiz_attempts"] == 1)
        # path: only stu1: 2 completed, 1 in_progress, 0 recommended, 1 pending
        pnp2 = data_after["path_node_progress"]
        chk("completed=2 after unenroll", pnp2["completed"] == 2)
        chk("recommended=0 after unenroll", pnp2["recommended"] == 0)
        chk("total_nodes=4 after unenroll", pnp2["total_nodes"] == 4)

        # ===== 8. Empty class (unenroll stu1 too) =====
        print("\n-- 8. Empty class --")
        async with async_session_factory() as db:
            await db.execute(
                update(CourseEnrollment)
                .where(
                    CourseEnrollment.student_id == stu1_id,
                    CourseEnrollment.course_id == course_id,
                )
                .values(is_deleted=True)
            )
            await db.commit()

        r = await client.get(URL, headers=tea1_headers)
        chk("200 empty class", r.status_code == 200)
        empty = r.json()["data"]
        chk("empty avg_quiz_score null", empty["avg_quiz_score"] is None)
        chk("empty total_quiz_attempts 0", empty["total_quiz_attempts"] == 0)
        chk("empty weak_points_top []", empty["weak_points_top"] == [])
        chk("empty path total_nodes 0", empty["path_node_progress"]["total_nodes"] == 0)

    print(f"\n{'='*50}")
    print(f"  Total: {ok} OK, {fail} FAIL")
    assert fail == 0, f"{fail} check(s) FAIL"
    return True


if __name__ == "__main__":
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/backend && python -m pytest tests/test_teacher_class_insights.py -v -s
```
Expected: FAIL — `404` on `/api/v1/teaching/classes/{class_id}/insights` because the route does not exist yet.

- [ ] **Step 3: 不提交**

红灯测试不单独提交。Task 3 实现通过后，测试和实现一起提交。

---

## Task 3: Backend — Implement `get_class_insights` Route

**Files:**
- Modify: `backend/app/api/v1/teaching.py` (append new route after line 283)

- [ ] **Step 1: Add the route handler**

Append the following route to `backend/app/api/v1/teaching.py` after the existing `get_student_learning` function (after line 283):

```python
@router.get("/classes/{class_id}/insights")
async def get_class_insights(
    class_id: str,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    await _verify_teacher(class_id, current_user, db)

    # 1. Get enrolled student IDs
    enrolled_result = await db.execute(
        select(CourseEnrollment.student_id).where(
            CourseEnrollment.course_id == class_id,
            CourseEnrollment.is_deleted == False,
        )
    )
    student_ids = [row[0] for row in enrolled_result.all()]

    if not student_ids:
        return {
            "code": 200,
            "message": "success",
            "data": {
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
            },
        }

    # 2. avg_quiz_score & total_quiz_attempts
    quiz_result = await db.execute(
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

    # 3. weak_points_top
    error_count_expr = func.sum(case((QuizAnswer.is_correct == False, 1), else_=0))
    total_attempts_expr = func.count(QuizAnswer.id)

    wp_result = await db.execute(
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
        .order_by(
            (error_count_expr / total_attempts_expr).desc(),
            error_count_expr.desc(),
        )
        .limit(5)
    )

    weak_points_top = []
    for row in wp_result:
        total = row.total_attempts
        errors = row.error_count or 0
        weak_points_top.append({
            "knowledge_point": row.knowledge_point,
            "error_count": errors,
            "total_attempts": total,
            "error_rate": round(errors / total, 2) if total > 0 else 0,
        })

    # 4. path_node_progress
    lp_result = await db.execute(
        select(LearningPath).where(
            LearningPath.course_id == class_id,
            LearningPath.user_id.in_(student_ids),
            LearningPath.is_deleted == False,
        )
    )
    known_statuses = {"completed", "in_progress", "recommended", "pending"}
    progress = {s: 0 for s in known_statuses}
    for lp in lp_result.scalars().all():
        nodes = lp.nodes if isinstance(lp.nodes, list) else []
        for node in nodes:
            st = node.get("status")
            if st in known_statuses:
                progress[st] += 1

    return {
        "code": 200,
        "message": "success",
        "data": {
            "avg_quiz_score": avg_quiz_score,
            "total_quiz_attempts": total_quiz_attempts,
            "weak_points_top": weak_points_top,
            "path_node_progress": {
                **progress,
                "total_nodes": sum(progress.values()),
            },
        },
    }
```

- [ ] **Step 2: Run tests to verify they pass**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/backend && python -m pytest tests/test_teacher_class_insights.py -v -s
```
Expected: all checks PASS, 0 FAIL.

- [ ] **Step 3: Run existing teaching tests to check for regressions**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/backend && python -m pytest tests/test_teacher_student_learning.py -v -s
```
Expected: PASS (no regression).

- [ ] **Step 4: Commit（测试 + 实现一起提交）**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add backend/tests/test_teacher_class_insights.py backend/app/api/v1/teaching.py
git commit -m "feat: add GET /teaching/classes/{class_id}/insights with SQL aggregation and tests"
```

---

## Task 4: Frontend — Wire `teachingService.getConsoleInsights` to Real Endpoint

**Files:**
- Modify: `frontend/src/api/services/teaching.js`

### Mock 分支处理决策

Spec 留出了弹性："是否彻底删除 mock 分支可留到 implementation plan 决定"。

**判断依据：** `teaching.js` 中 `useMock` 仅被 `getConsoleInsights` 一处使用（line 55）。`TeacherConsole.jsx` 中的 `useMock` 是独立的文件级变量，不由 `teaching.js` 控制。因此 `teaching.js` 中的 mock 分支可以安全删除。

**执行规则：** 如果执行时发现 `VITE_USE_MOCK=true` 还有其他页面/回归场景依赖 `teaching.js` 的 mock 路径（例如其他 service 方法引用了 `useMock`），则只修正式分支（将 real 分支指向新端点），保留 mock 分支原样。执行者应先 `grep useMock frontend/src/api/services/teaching.js` 确认。

- [ ] **Step 1: Check mock usage scope**

Run:
```bash
grep -n "useMock" frontend/src/api/services/teaching.js
```

If only line 3 (declaration) and line 55 (in `getConsoleInsights`) reference it, proceed to delete both. If other methods reference it, keep the declaration and only replace `getConsoleInsights`.

- [ ] **Step 2: Replace the `getConsoleInsights` method**

In `frontend/src/api/services/teaching.js`, replace the existing `getConsoleInsights` method (lines 54-63) with:

```javascript
  getConsoleInsights: (courseId) => {
    return client.get(`/teaching/classes/${courseId}/insights`);
  },
```

- [ ] **Step 3: Remove `useMock` declaration if orphaned**

If Step 1 confirmed `useMock` is only used by `getConsoleInsights`, remove line 3:

```javascript
const useMock = import.meta.env.VITE_USE_MOCK === 'true';
```

- [ ] **Step 4: Run lint and build**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add frontend/src/api/services/teaching.js
git commit -m "feat: wire getConsoleInsights to real /teaching/classes/{courseId}/insights endpoint"
```

---

## Task 5: Frontend — Split Error Handling in TeacherConsole Data Loading

**Files:**
- Modify: `frontend/src/pages/TeacherConsole.jsx`

The design spec requires students and insights to have independent error handling. Currently they share a single `Promise.all` with a shared `.catch`.

- [ ] **Step 1: Add separate state variables for insights loading and errors**

In `TeacherConsole.jsx`, add state variables after the existing `studentsLoading` state (line 20):

```javascript
  const [studentsError, setStudentsError] = useState(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [insightsError, setInsightsError] = useState(null);
```

- [ ] **Step 2: Replace the combined `useEffect` with isolated fetches**

Replace the `useEffect` at lines 49-59 with:

```javascript
  useEffect(() => {
    if (!activeClass) return;

    setStudentsLoading(true);
    setStudentsError(null);
    teachingService.getClassStudents(activeClass)
      .then((res) => {
        if (res.code === 200) setStudents(res.data);
      })
      .catch((err) => {
        console.error('students fetch error', err);
        setStudentsError('学生列表加载失败');
      })
      .finally(() => setStudentsLoading(false));

    setInsightsLoading(true);
    setInsightsError(null);
    teachingService.getConsoleInsights(activeClass)
      .then((res) => {
        if (res.code === 200) setInsights(res.data);
      })
      .catch((err) => {
        console.error('insights fetch error', err);
        setInsightsError('班级统计加载失败，请稍后重试。');
      })
      .finally(() => setInsightsLoading(false));
  }, [activeClass]);
```

- [ ] **Step 3: Run lint and build**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add frontend/src/pages/TeacherConsole.jsx
git commit -m "refactor: split students and insights loading with independent error handling"
```

---

## Task 6: Frontend — Replace Mock Insights Section with Real Class Statistics

**Files:**
- Modify: `frontend/src/pages/TeacherConsole.jsx`

This task does two things:
1. Removes the `{useMock && (...)}` guard around the Insights section (lines 258-275) and replaces it with a real class statistics section that renders the four aggregation fields.
2. Adds `studentsError` UI in the student monitoring table, so students and insights have fully independent error presentation（spec 要求 "students / insights 独立错误处理"）。

- [ ] **Step 1: Add studentsError display in the student monitoring table**

In `TeacherConsole.jsx`, find the student list rendering (the `{studentsLoading ? ... : students.map(...)}` block inside the student monitoring grid, around line 184). Add a `studentsError` branch between `studentsLoading` and the normal student list:

Replace:
```jsx
                  {studentsLoading ? (
                    <div className="col-span-1 lg:col-span-2 py-8 flex justify-center">
                      <FeedbackStatus status="loading" title="加载学生列表..." />
                    </div>
                  ) : (
                    students.map(student => (
```

With:
```jsx
                  {studentsLoading ? (
                    <div className="col-span-1 lg:col-span-2 py-8 flex justify-center">
                      <FeedbackStatus status="loading" title="加载学生列表..." />
                    </div>
                  ) : studentsError ? (
                    <div className="col-span-1 lg:col-span-2 py-8 flex justify-center">
                      <FeedbackStatus status="error" title={studentsError} />
                    </div>
                  ) : students.length === 0 ? (
                    <div className="col-span-1 lg:col-span-2 py-8 flex justify-center">
                      <FeedbackStatus status="empty" title="该班级暂无学生" />
                    </div>
                  ) : (
                    students.map(student => (
```

- [ ] **Step 2: Replace the Insights section**

Remove the entire `{useMock && ( <section>...</section> )}` block (lines 258-275) and replace with:

```jsx
          {/* Class Statistics Section */}
          <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-gutter mb-margin">
            {insightsLoading ? (
              <div className="col-span-full py-8 flex justify-center">
                <FeedbackStatus status="loading" title="加载班级统计..." />
              </div>
            ) : insightsError ? (
              <div className="col-span-full py-8 flex justify-center">
                <FeedbackStatus status="error" title={insightsError} />
              </div>
            ) : !insights ? (
              <div className="col-span-full py-8 flex justify-center">
                <FeedbackStatus status="empty" title="暂无班级统计数据" />
              </div>
            ) : (
              <>
                {/* Avg Quiz Score */}
                <div className="bg-white rounded-xl border border-outline-variant shadow-sm p-md">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="material-symbols-outlined text-primary text-xl">quiz</span>
                    <span className="text-sm font-semibold text-outline">平均练习分</span>
                  </div>
                  <p className="text-3xl font-bold text-on-surface">
                    {insights.avg_quiz_score != null
                      ? insights.avg_quiz_score.toFixed(1)
                      : '暂无数据'}
                  </p>
                </div>

                {/* Total Quiz Attempts */}
                <div className="bg-white rounded-xl border border-outline-variant shadow-sm p-md">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="material-symbols-outlined text-primary text-xl">assignment</span>
                    <span className="text-sm font-semibold text-outline">练习次数</span>
                  </div>
                  <p className="text-3xl font-bold text-on-surface">
                    {insights.total_quiz_attempts}
                  </p>
                </div>

                {/* Weak Points Top */}
                <div className="bg-white rounded-xl border border-outline-variant shadow-sm p-md md:col-span-2 lg:col-span-1">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="material-symbols-outlined text-error text-xl">warning</span>
                    <span className="text-sm font-semibold text-outline">薄弱知识点</span>
                  </div>
                  {insights.weak_points_top.length === 0 ? (
                    <p className="text-sm text-outline">暂无薄弱知识点</p>
                  ) : (
                    <ul className="space-y-2">
                      {insights.weak_points_top.map((wp) => (
                        <li key={wp.knowledge_point} className="text-sm">
                          <div className="flex justify-between items-center">
                            <span className="text-on-surface truncate max-w-[60%]">{wp.knowledge_point}</span>
                            <span className="text-error font-semibold">{Math.round(wp.error_rate * 100)}%</span>
                          </div>
                          <span className="text-xs text-outline">
                            错 {wp.error_count} / 共 {wp.total_attempts} 次
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {/* Path Node Progress */}
                <div className="bg-white rounded-xl border border-outline-variant shadow-sm p-md">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="material-symbols-outlined text-primary text-xl">route</span>
                    <span className="text-sm font-semibold text-outline">路径节点分布</span>
                  </div>
                  {insights.path_node_progress.total_nodes === 0 ? (
                    <p className="text-sm text-outline">暂无学习路径数据</p>
                  ) : (
                    <div className="space-y-2">
                      {[
                        { label: '已完成', key: 'completed', color: 'bg-green-500' },
                        { label: '进行中', key: 'in_progress', color: 'bg-blue-500' },
                        { label: '推荐', key: 'recommended', color: 'bg-amber-500' },
                        { label: '待开始', key: 'pending', color: 'bg-gray-400' },
                      ].map(({ label, key, color }) => (
                        <div key={key} className="flex items-center gap-2 text-sm">
                          <div className={`w-2.5 h-2.5 rounded-full ${color}`} />
                          <span className="text-on-surface-variant w-14">{label}</span>
                          <span className="font-semibold text-on-surface">{insights.path_node_progress[key]}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            )}
          </section>
```

- [ ] **Step 3: Assess `useMock` removal in TeacherConsole.jsx**

`useMock` is also used at line 205 for the student card mock branch (showing `current_path_node` and `overall_mastery`). That branch is unrelated to this task.

**Rule:** Only remove the `useMock` constant (line 8) if no other code in this file references it. Since line 205 still uses it, **keep** the constant. Only the Insights section `{useMock && ...}` block is removed.

- [ ] **Step 4: Run lint and build**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add frontend/src/pages/TeacherConsole.jsx
git commit -m "feat: replace mock Insights with real statistics, add studentsError UI"
```

---

## Task 7: Integration Verification

- [ ] **Step 1: Run all backend tests**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/backend && python -m pytest tests/test_teacher_class_insights.py tests/test_teacher_student_learning.py -v -s
```
Expected: all PASS.

- [ ] **Step 2: Run frontend lint + build**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```
Expected: no errors.

- [ ] **Step 3: Run E2E tests if available**

先检查 `package.json` 是否包含 `test:e2e` 脚本：
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && node -e "const p=require('./package.json'); if(p.scripts && p.scripts['test:e2e']){console.log('test:e2e found');process.exit(0)}else{console.log('test:e2e not configured, skipping');process.exit(1)}"
```

- 如果输出 `test:e2e not configured, skipping`（exit 1）：记录"E2E 未配置，跳过"，进入 Step 4。
- 如果输出 `test:e2e found`（exit 0）：执行下面的命令，**不吞错误**：
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run test:e2e
```
Expected: PASS。如果失败，保留完整错误输出并排查，不要跳过。

- [ ] **Step 4: Update WORKFLOW.md**

Add to the `下一步建议` section in `frontend/WORKFLOW.md` to record completion:

```markdown
- TeacherConsole 班级 Insights 最小 SQL 聚合已完成：OpenAPI 契约、Backend 聚合端点、Frontend 接入。`useMock &&` 守卫已移除，真实模式展示班级平均练习分、练习次数、薄弱知识点 Top 5、路径节点分布。
```

- [ ] **Step 5: Commit WORKFLOW.md**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add frontend/WORKFLOW.md
git commit -m "docs: record TeacherConsole class insights completion in WORKFLOW"
```

---

## Self-Review Checklist

| Spec Requirement | Task |
|------------------|------|
| OpenAPI contract with `ClassInsights`, `ClassWeakPoint`, `PathNodeProgress` | Task 1 |
| Backend `GET /teaching/classes/{class_id}/insights` route | Task 3 |
| `_verify_teacher` reuse, `require_role("teacher", "admin")` | Task 3 step 1 |
| Enrolled student filter via `CourseEnrollment` | Task 3 step 1 |
| `avg_quiz_score` null when no quiz data | Task 2 (test case 3), Task 3 |
| `weak_points_top` Top 5, empty KP filtered, sorted by error_rate DESC | Task 2 (test case 5), Task 3 |
| `path_node_progress` node count by status, unknown ignored | Task 2 (test case 6), Task 3 |
| Empty class returns full empty state | Task 2 (test case 8), Task 3 |
| Soft-deleted enrollment excluded | Task 2 (test case 7), Task 3 |
| Frontend `getConsoleInsights` calls real endpoint | Task 4 |
| Separate `insightsLoading` / `insightsError` / `studentsLoading` / `studentsError` | Task 5 |
| Remove `useMock &&` guard on Insights section | Task 6 |
| Display: avg score, attempts, weak points, path node progress | Task 6 |
| Error text: "班级统计加载失败，请稍后重试。" | Task 5, Task 6 |
| Empty text: "暂无班级统计数据" | Task 6 |
| Non-goals excluded: overview, focus_students, coverage_rate, ranking, agent_summary | Task 6 (none rendered) |
| 401/403/404 error responses consistent with existing teaching module | Task 1, Task 3 |
| Backend tests: 404 course, 403 not owner, empty, aggregation, soft-delete | Task 2 |
