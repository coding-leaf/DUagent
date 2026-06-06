# 教师端学生弱项与活动数据聚合实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `get_student_learning` 端点补齐 `weak_points`（错题聚合 top 5）和 `recent_activity`（最近 5 次练习），替换 TeacherStudentReport 硬编码空数组。

**Architecture:** 5 个 task，TDD 顺序：Backend 测试（红灯）→ Backend 实现（绿灯）→ OpenAPI → Frontend → 验证收口。单端点增强，不新增表/端点/Agent 调用。

**Tech Stack:** OpenAPI JSON, FastAPI (Python), React (JavaScript), Vite

**依据 Spec：** `docs/superpowers/specs/2026-06-06-teacher-student-weakpoints-recentactivity-design.md`

---

### Task 1: Backend 测试（红灯）— 先写测试

**Files:**
- Create: `backend/tests/test_teacher_student_learning.py`

**目标：** 先写测试，验证当前 `weak_points`/`recent_activity` 为空或不存在，测试预期会 FAIL。Task 2 实现后变绿。

- [ ] **Step 1: 创建测试文件（使用第二个 teacher 测试 403）**

```python
"""Integration tests for GET /teaching/classes/{class_id}/students/{student_id}/learning.

Covers: 403 teacher not owning course, weak_points aggregation with HAVING filter,
empty weak_points when all correct, recent_activity max 5 items.

Requires MySQL or SQLite.

Run: python -m pytest tests/test_teacher_student_learning.py -v -s
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
    "sqlite+aiosqlite:///./test_teacher_learning.db",
)

from app.db.session import async_session_factory, init_db
from httpx import AsyncClient, ASGITransport

asyncio.run(init_db())

from app.main import app
from app.models.user import RegistrationCode
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession


async def _captcha_answer(client):
    r = await client.get("/api/v1/auth/captcha")
    d = r.json()["data"]
    nums = re.findall(r"\d+", d["captcha_question"])
    ans = str(int(nums[0]) + int(nums[1])) if "+" in d["captcha_question"] else str(int(nums[0]) - int(nums[1]))
    return d["captcha_token"], ans


async def _register_and_login(client, code, email, username):
    ct_token, ct_ans = await _captcha_answer(client)
    r = await client.post("/api/v1/auth/register", json={
        "registration_code": code, "email": email, "password": "Abc12345",
        "username": username, "captcha_token": ct_token, "captcha_code": ct_ans,
    })
    assert r.status_code == 201, f"Register failed: {r.status_code} {r.json()}"
    user_id = r.json()["data"]["user_id"]
    ct_token, ct_ans = await _captcha_answer(client)
    r = await client.post("/api/v1/auth/login", json={
        "email": email, "password": "Abc12345",
        "captcha_token": ct_token, "captcha_code": ct_ans,
    })
    assert "token" in r.json().get("data", {}), f"Login failed: {r.json()}"
    return {"Authorization": f"Bearer {r.json()['data']['token']}"}, user_id


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
            RegistrationCode(code=f"stu_{uuid.uuid4().hex[:8]}", role="student"),
            RegistrationCode(code=f"tea1_{uuid.uuid4().hex[:8]}", role="teacher"),
            RegistrationCode(code=f"tea2_{uuid.uuid4().hex[:8]}", role="teacher"),
        ]
        async with async_session_factory() as db:
            db.add_all(codes)
            await db.commit()
            student_code = codes[0].code
            tea1_code = codes[1].code
            tea2_code = codes[2].code

        stu_headers, stu_id = await _register_and_login(
            client, student_code, f"stu_{uuid.uuid4().hex[:8]}@test.com", f"stu_{uuid.uuid4().hex[:8]}")
        tea1_headers, tea1_id = await _register_and_login(
            client, tea1_code, f"tea1_{uuid.uuid4().hex[:8]}@test.com", f"tea1_{uuid.uuid4().hex[:8]}")
        tea2_headers, tea2_id = await _register_and_login(
            client, tea2_code, f"tea2_{uuid.uuid4().hex[:8]}@test.com", f"tea2_{uuid.uuid4().hex[:8]}")

        # ===== Create course by tea1 =====
        r = await client.post("/api/v1/courses", json={"name": "Tchr Test"}, headers=tea1_headers)
        assert r.status_code == 201, f"Create course failed: {r.status_code} {r.json()}"
        course_data = r.json()["data"]
        course_id = course_data["id"]
        course_code = course_data.get("course_code", "")

        join_r = await client.post("/api/v1/courses/join", json={"course_code": course_code}, headers=stu_headers)
        assert join_r.status_code == 200, f"Join failed: {join_r.status_code} {join_r.json()}"

        # ===== Seed quiz data (for weak_points verification) =====
        async with async_session_factory() as db:
            qs = QuizSession(user_id=stu_id, course_id=course_id, chapter="ch1",
                             score=50, correct_count=1, total_count=2, time_spent=60)
            db.add(qs)
            await db.flush()

            q1 = QuizQuestion(course_id=course_id, chapter="ch1", knowledge_point="AVL树旋转",
                              type="single_choice", content="Q1?", options=["A","B","C","D"], correct_answer="A")
            q2 = QuizQuestion(course_id=course_id, chapter="ch1", knowledge_point="AVL树旋转",
                              type="single_choice", content="Q2?", options=["A","B","C","D"], correct_answer="A")
            q3 = QuizQuestion(course_id=course_id, chapter="ch1", knowledge_point="散列冲突",
                              type="single_choice", content="Q3?", options=["A","B","C","D"], correct_answer="A")
            q4 = QuizQuestion(course_id=course_id, chapter="ch1", knowledge_point="",
                              type="single_choice", content="Empty KP", options=["A","B","C","D"], correct_answer="A")
            db.add_all([q1, q2, q3, q4])
            await db.flush()

            answers = [
                QuizAnswer(quiz_id=qs.id, question_id=q1.id, user_answer="B", is_correct=False, correct_answer="A"),
                QuizAnswer(quiz_id=qs.id, question_id=q2.id, user_answer="A", is_correct=True, correct_answer="A"),
                QuizAnswer(quiz_id=qs.id, question_id=q3.id, user_answer="B", is_correct=False, correct_answer="A"),
                QuizAnswer(quiz_id=qs.id, question_id=q4.id, user_answer="B", is_correct=False, correct_answer="A"),
            ]
            db.add_all(answers)
            await db.commit()

        # ===== 1. 403 — tea2 is teacher but not course owner =====
        print("\n-- 1. 403 teacher not course owner --")
        # tea2 is a teacher but did NOT create course_id.
        # _verify_teacher checks course.teacher_id == current_user.id => 403.
        r = await client.get(
            f"/api/v1/teaching/classes/{course_id}/students/{stu_id}/learning",
            headers=tea2_headers)
        chk("403 teacher not owner", r.status_code == 403)

        # ===== 2. 200 — weak_points aggregation (tea1 can access) =====
        print("\n-- 2. weak_points aggregation --")
        r = await client.get(
            f"/api/v1/teaching/classes/{course_id}/students/{stu_id}/learning",
            headers=tea1_headers)
        chk("200 teacher access", r.status_code == 200)
        data = r.json()["data"]

        wp = data.get("weak_points", [])
        chk("weak_points non-empty", len(wp) > 0)
        if len(wp) > 0:
            chk("weak_points has knowledge_point", "knowledge_point" in wp[0])
            chk("weak_points has error_count", "error_count" in wp[0])
            chk("weak_points has total_attempts", "total_attempts" in wp[0])
            chk("weak_points has error_rate", "error_rate" in wp[0])
            # AVL树旋转: 1 wrong / 2 total = 0.5
            avl = [w for w in wp if w["knowledge_point"] == "AVL树旋转"]
            chk("AVL树旋转 present", len(avl) > 0)
            if len(avl) > 0:
                chk("AVL error_count = 1", avl[0]["error_count"] == 1)
                chk("AVL total_attempts = 2", avl[0]["total_attempts"] == 2)
                chk("AVL error_rate = 0.5", avl[0]["error_rate"] == 0.5)
            hash_wp = [w for w in wp if w["knowledge_point"] == "散列冲突"]
            chk("散列冲突 present", len(hash_wp) > 0)
            empty_kp = [w for w in wp if w["knowledge_point"] == ""]
            chk("empty KP filtered", len(empty_kp) == 0)

        # ===== 3. recent_activity =====
        print("\n-- 3. recent_activity --")
        ra = data.get("recent_activity", [])
        chk("recent_activity non-empty", len(ra) > 0)
        if len(ra) > 0:
            chk("ra has quiz_id", "quiz_id" in ra[0])
            chk("ra has chapter", "chapter" in ra[0])
            chk("ra has score", "score" in ra[0])
            chk("ra has correct_count", "correct_count" in ra[0])
            chk("ra has total_count", "total_count" in ra[0])
            chk("ra has time_spent", "time_spent" in ra[0])
            chk("ra has created_at", "created_at" in ra[0])

        # ===== 4. empty weak_points when all correct =====
        print("\n-- 4. all-correct -> empty weak_points --")
        stu2_code = f"stu_{uuid.uuid4().hex[:8]}"
        async with async_session_factory() as db:
            db.add(RegistrationCode(code=stu2_code, role="student"))
            await db.commit()
        stu2_headers, stu2_id = await _register_and_login(
            client, stu2_code, f"stu2_{uuid.uuid4().hex[:8]}@test.com", f"stu2_{uuid.uuid4().hex[:8]}")
        await client.post("/api/v1/courses/join", json={"course_code": course_code}, headers=stu2_headers)

        async with async_session_factory() as db:
            qs3 = QuizSession(user_id=stu2_id, course_id=course_id, chapter="ch1",
                              score=100, correct_count=1, total_count=1, time_spent=30)
            db.add(qs3)
            await db.flush()
            q_all = QuizQuestion(course_id=course_id, chapter="ch1", knowledge_point="正确知识点",
                                 type="single_choice", content="Q?", options=["A","B"], correct_answer="A")
            db.add(q_all)
            await db.flush()
            db.add(QuizAnswer(quiz_id=qs3.id, question_id=q_all.id, user_answer="A",
                              is_correct=True, correct_answer="A"))
            await db.commit()

        r = await client.get(
            f"/api/v1/teaching/classes/{course_id}/students/{stu2_id}/learning",
            headers=tea1_headers)
        chk("all-correct -> 200", r.status_code == 200)
        st2_data = r.json()["data"]
        st2_wp = st2_data.get("weak_points", [])
        chk("all-correct -> weak_points empty", st2_wp == [])

        # ===== 5. recent_activity max 5 =====
        print("\n-- 5. recent_activity max 5 --")
        async with async_session_factory() as db:
            for i in range(7):
                qs_n = QuizSession(user_id=stu_id, course_id=course_id, chapter=f"ch{i}",
                                   score=80, correct_count=3, total_count=4, time_spent=60)
                db.add(qs_n)
            await db.commit()

        r = await client.get(
            f"/api/v1/teaching/classes/{course_id}/students/{stu_id}/learning",
            headers=tea1_headers)
        chk("more sessions -> 200", r.status_code == 200)
        ra_all = r.json()["data"].get("recent_activity", [])
        chk("recent_activity max 5", len(ra_all) == 5)

    print(f"\n{'='*50}")
    print(f"  Total: {ok} OK, {fail} FAIL")
    assert fail == 0, f"{fail} check(s) FAIL"
    return True


if __name__ == "__main__":
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
```

- [ ] **Step 2: 运行测试（预期 FAIL — weak_points 和 recent_activity 仍为 `[]`）**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/backend
python -m pytest tests/test_teacher_student_learning.py -v -s
```
Expected: weak_points/recent_activity 相关断言 FAIL（当前返回 `[]`），403 相关断言可能 PASS。

- [ ] **Step 3: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add backend/tests/test_teacher_student_learning.py
git commit -m "测试: 教师端学生 weak_points 和 recent_activity 聚合（当前红灯）"
```

---

### Task 2: Backend 实现（绿灯）— get_student_learning 补齐聚合

**Files:**
- Modify: `backend/app/api/v1/teaching.py`

**注意：** Task 2 同时处理 weak_points 和 recent_activity（同一函数内）。实现后 Task 1 的测试应变绿。

- [ ] **Step 1: 更新 import**

当前第 2 行和第 8 行：
```python
from sqlalchemy import func, select
```
```python
from app.models.quiz import QuizSession
```

替换为：
```python
from sqlalchemy import case, func, select
```
```python
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
```

分别修改 import 行。第二处将 `QuizSession` 替换为 `QuizAnswer, QuizQuestion, QuizSession`。

- [ ] **Step 2: 在 quiz_stats 和 return 之间插入 weak_points + recent_activity 聚合**

找到 `quiz_stats` 代码块结束后（`quiz_stats = None` / `quiz_stats = { ... }` 的 `}`）、`return {` 之前的位置，插入：

```python
    # weak_points: 按知识点聚合错题 top 5（条件聚合 + 过滤空知识点 + HAVING error_count > 0）
    error_count_expr = func.sum(case((QuizAnswer.is_correct == False, 1), else_=0))
    total_attempts_expr = func.count(QuizAnswer.id)

    weak_points = []
    wp_result = await db.execute(
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
        .order_by(
            (error_count_expr / total_attempts_expr).desc(),
            error_count_expr.desc(),
        )
        .limit(5)
    )
    for row in wp_result:
        total = row.total_attempts
        errors = row.error_count or 0
        weak_points.append({
            "knowledge_point": row.knowledge_point,
            "error_count": errors,
            "total_attempts": total,
            "error_rate": round(errors / total, 2) if total > 0 else 0,
        })

    # recent_activity: 最近 5 次 QuizSession
    recent_activity = []
    ra_result = await db.execute(
        select(QuizSession)
        .where(
            QuizSession.user_id == student_id,
            QuizSession.course_id == class_id,
            QuizSession.is_deleted == False,
        )
        .order_by(QuizSession.create_time.desc())
        .limit(5)
    )
    for qs in ra_result.scalars().all():
        recent_activity.append({
            "quiz_id": qs.id,
            "chapter": qs.chapter or "",
            "score": qs.score,
            "correct_count": qs.correct_count,
            "total_count": qs.total_count,
            "time_spent": qs.time_spent,
            "created_at": qs.create_time.isoformat() if qs.create_time else "",
        })
```

- [ ] **Step 3: 替换 return 中的 weak_points 和 recent_activity**

当前 return 中（约第 204-205 行）：
```python
            "weak_points": [],
            "recent_activity": [],
```

替换为：
```python
            "weak_points": weak_points,
            "recent_activity": recent_activity,
```

- [ ] **Step 4: 运行 Task 1 的测试（预期 GREEN）**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/backend
python -m pytest tests/test_teacher_student_learning.py -v -s
```
Expected: all OK, 0 FAIL, PASSED.

- [ ] **Step 5: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add backend/app/api/v1/teaching.py
git commit -m "Backend get_student_learning 补齐 weak_points 和 recent_activity 聚合"
```

---

### Task 3: OpenAPI — 更新 StudentLearning schema

**Files:**
- Modify: `docs/10-client-api/Client-API.openapi.json` (weak_points 约第 1406 行，recent_activity 约第 1411 行)

**目标：** 将 `weak_points` 和 `recent_activity` 从旧 schema 改为聚合字段定义。

**当前实际 schema：**
- `weak_points`: `items: { "type": "string" }`，description "薄弱知识点列表"
- `recent_activity`: `items: { "type": "object", "properties": { "type", "title", "created_at" } }`，description "最近学习活动"

- [ ] **Step 1: 验证 JSON 有效**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
jq empty docs/10-client-api/Client-API.openapi.json
```
Expected: no output.

- [ ] **Step 2: 更新 weak_points 定义**

当前（`items: { "type": "string" }`）替换为：
```json
          "weak_points": {
            "type": "array",
            "description": "按知识点聚合的错题 top 5，按 error_rate DESC, error_count DESC 排序；无错题时为空数组",
            "items": {
              "type": "object",
              "properties": {
                "knowledge_point": { "type": "string", "description": "知识点名称" },
                "error_count": { "type": "integer", "description": "错误次数" },
                "total_attempts": { "type": "integer", "description": "该知识点答题总数" },
                "error_rate": { "type": "number", "description": "错误率 0-1" }
              }
            }
          },
```

- [ ] **Step 3: 更新 recent_activity 定义**

当前（`items.properties: { type, title, created_at }`）替换为：
```json
          "recent_activity": {
            "type": "array",
            "description": "最近 5 次 QuizSession，按 create_time DESC 排序；无记录时为空数组",
            "items": {
              "type": "object",
              "properties": {
                "quiz_id": { "type": "string", "description": "练习 ID" },
                "chapter": { "type": "string", "description": "章节" },
                "score": { "type": "number", "description": "得分（百分比）" },
                "correct_count": { "type": "integer", "description": "正确数" },
                "total_count": { "type": "integer", "description": "总题数" },
                "time_spent": { "type": "integer", "description": "耗时（秒）" },
                "created_at": { "type": "string", "format": "date-time", "description": "练习时间" }
              }
            }
          }
```

**注意：** 精确匹配旧 schema 的 `"description"` 字符串进行替换。weak_points 旧 schema 有 `"description": "薄弱知识点列表"`；recent_activity 旧 schema 有 `"description": "最近学习活动"`。

- [ ] **Step 4: 验证 JSON 仍然有效**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
jq empty docs/10-client-api/Client-API.openapi.json
```
Expected: no output.

- [ ] **Step 5: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add docs/10-client-api/Client-API.openapi.json
git commit -m "OpenAPI StudentLearning 补齐 weak_points 和 recent_activity 字段定义"
```

---

### Task 4: Frontend — TeacherStudentReport.jsx 消费真实数据

**Files:**
- Modify: `frontend/src/pages/TeacherStudentReport.jsx`

- [ ] **Step 1: 替换 weak_points 区块（约第 465-468 行）**

当前：
```jsx
                <div className="flex flex-wrap gap-2 mt-3">
                  {/* weak_points — 后端当前返回空数组，等待 Backend 聚合实现 */}
                  <p className="text-xs text-outline italic">正式接口暂未提供</p>
                </div>
```

替换为：
```jsx
                <div className="flex flex-wrap gap-2 mt-3">
                  {report.weak_points?.length > 0 ? (
                    report.weak_points.map((wp, i) => (
                      <div key={i} className="px-3 py-2 bg-orange-50 rounded-lg border border-orange-100 text-xs">
                        <span className="font-bold text-orange-700">{wp.knowledge_point}</span>
                        <span className="text-orange-500 ml-2">
                          {wp.error_count}/{wp.total_attempts} 错 ({Math.round(wp.error_rate * 100)}%)
                        </span>
                      </div>
                    ))
                  ) : (
                    <p className="text-xs text-outline italic">暂无薄弱点</p>
                  )}
                </div>
```

- [ ] **Step 2: 替换 recent_activity 区块（约第 489-491 行）**

当前：
```jsx
              <div className="space-y-4 max-h-[220px] overflow-y-auto pr-2 scrollbar-thin">
                {/* recent_activity — 后端当前返回空数组，等待 Backend 聚合实现 */}
                <p className="text-xs text-outline italic text-center py-8">正式接口暂未提供</p>
              </div>
```

替换为：
```jsx
              <div className="space-y-4 max-h-[220px] overflow-y-auto pr-2 scrollbar-thin">
                {report.recent_activity?.length > 0 ? (
                  report.recent_activity.map((ra, i) => (
                    <div key={i} className="flex items-center gap-3 pb-3 border-b border-slate-50 last:border-0">
                      <div className="w-8 h-8 rounded-full bg-cyan-100 flex items-center justify-center flex-shrink-0">
                        <span className="material-symbols-outlined text-cyan-600 text-sm">exercise</span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-bold text-on-surface truncate">{ra.chapter || '练习'}</p>
                        <p className="text-[10px] text-outline">
                          {ra.created_at ? new Date(ra.created_at).toLocaleDateString('zh-CN') : ''}
                        </p>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <span className="text-sm font-bold text-primary">{Math.round(ra.score)}%</span>
                        <p className="text-[10px] text-outline">{ra.correct_count}/{ra.total_count} 正确</p>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-outline italic text-center py-8">暂无近期活动</p>
                )}
              </div>
```

- [ ] **Step 3: 验证 lint + build**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```
Expected: lint PASS, build PASS.

- [ ] **Step 4: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/pages/TeacherStudentReport.jsx
git commit -m "TeacherStudentReport 消费真实 weak_points 和 recent_activity 数据"
```

---

### Task 5: 全量验证 + WORKFLOW 收口

**Files:**
- Modify: `frontend/WORKFLOW.md`

- [ ] **Step 1: lint + build**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```
Expected: PASS.

- [ ] **Step 2: 运行所有 Backend 测试**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/backend
python -m pytest tests/test_teacher_student_learning.py tests/test_node_resources.py tests/test_resource_detail.py -v -s
```
Expected: all three test files PASSED.

- [ ] **Step 3: OpenAPI JSON 验证**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
jq empty docs/10-client-api/Client-API.openapi.json
```
Expected: no output (valid).

- [ ] **Step 4: 更新 WORKFLOW.md**

在 `## 最近验证` 末尾追加：
```markdown
- 2026-06-06：教师端学生 weak_points + recent_activity 聚合完成：
  - Backend 测试（TDD）：先写 `test_teacher_student_learning.py` 覆盖 403（tea2 not owner）/ weak_points 聚合 / 全对空数组 / recent_activity max 5
  - Backend：`get_student_learning` 补齐 `weak_points`（case() 条件聚合 + HAVING error_count > 0 + 过滤空 KP + top 5）和 `recent_activity`（最近 5 次 QuizSession）
  - OpenAPI：`StudentLearning` schema 补齐 `weak_points[]`、`recent_activity[]` 字段定义
  - Frontend：`TeacherStudentReport.jsx` 去掉硬编码 `[]`，渲染真实 weak_points 和 recent_activity，保留空态
  - 不新增端点、不调 Agent、不改 TeacherConsole Insights
  - `npm run lint` / `npm run build` / Backend pytest 通过。
```

- [ ] **Step 5: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/WORKFLOW.md
git commit -m "docs: 记录教师端学生 weak_points 和 recent_activity 聚合完成"
```

---

## 自审清单

**1. Spec 覆盖：** ✅ Task 1-5 覆盖 Backend 测试/Backend 实现/OpenAPI/Frontend/收口。TDD 顺序（测试先于实现）。

**2. 无占位符：** ✅ 所有步骤含完整代码。

**3. 类型一致性：** ✅ `weak_points` 字段（knowledge_point/error_count/total_attempts/error_rate）三层一致。`recent_activity` 字段同样一致。`case` import 在顶部。

**4. 修正记录：**
- 403 测试：tea2（teacher role，非 course owner）→ `_verify_teacher` 返回 403 ✅
- `_register_and_login` 返回 `data.user_id`（对齐 test_resource_detail.py 模式）✅
- OpenAPI 旧 schema 准确描述（weak_points → `items: { type: string }`，recent_activity → 旧 `{type, title, created_at}`）✅
- 测试命令使用直接 `python -m pytest ... -v -s`（无 grep 管道）✅
- 无 `rm -f` 步骤（动态 UUID ID 保证可重复）✅
