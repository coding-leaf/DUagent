# 阶段一验收缺陷修复（v2）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复阶段一验收中发现的 7 个前端缺陷 + 审查并提交 6 个候选修复 + 建立可复现 E2E 测试数据环境，使 E2E 3/3 通过。

**Architecture:** 6 个批次：种子脚本 → E2E 基础设施 → 候选修复验证与提交 → TeacherStudentReport 契约对齐 → learning.js 路径修正 → WORKFLOW.md 更新。每批独立验证并 commit。批次 3 必须先验证后提交。

**Tech Stack:** Python 3 (SQLAlchemy async, FastAPI), React 19, Vite 8, Playwright 1.60, MySQL

---

### Task 1: 种子脚本 — 安全守卫与导入

**Files:**
- Create: `/home/yezisama/workspace/workflow/EDUagent/backend/scripts/seed_e2e_data.py`

- [ ] **Step 1: 编写脚本头部**

```python
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
```

- [ ] **Step 2: 验证可导入**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/backend && ALLOW_E2E_SEED=true DATABASE_URL='mysql+aiomysql://root:123456@localhost:3306/duagent_test?charset=utf8mb4' python -c "exec(open('scripts/seed_e2e_data.py').read().split('if __name__')[0]); print('imports OK')"
```

---

### Task 2: 种子脚本 — 数据创建函数

**Files:**
- Modify: `/home/yezisama/workspace/workflow/EDUagent/backend/scripts/seed_e2e_data.py`

- [ ] **Step 1: 追加幂等辅助和 User 创建**

```python
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
```

- [ ] **Step 2: 追加 Course 和 Enrollment 创建**

```python
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
```

- [ ] **Step 3: 追加 Resource、QuizQuestion 创建**

```python
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
```

- [ ] **Step 4: 追加 UserProfile、Evaluation、QuizSession 创建**

```python
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
```

---

### Task 3: 种子脚本 — README 与验证

**Files:**
- Create: `/home/yezisama/workspace/workflow/EDUagent/backend/scripts/README.md`

- [ ] **Step 1: 编写 README**

```markdown
# Scripts

## seed_e2e_data.py

Creates repeatable test data for Playwright E2E tests.

### Usage

```bash
# 1. Create test database (once)
mysql -u root -p123456 -e "CREATE DATABASE IF NOT EXISTS duagent_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 2. Run seeder (idempotent, safe to re-run)
ALLOW_E2E_SEED=true DATABASE_URL='mysql+aiomysql://root:123456@localhost:3306/duagent_test?charset=utf8mb4' python scripts/seed_e2e_data.py

# 3. Start backend with same test DB
DATABASE_URL='mysql+aiomysql://root:123456@localhost:3306/duagent_test?charset=utf8mb4' python -m uvicorn app.main:app --host 127.0.0.1 --port 8001

# 4. Run E2E tests
cd ../frontend && npm run test:e2e
```

### Safety

- Requires `ALLOW_E2E_SEED=true`
- Database name must contain "test"
- Idempotent: safe to re-run

### Accounts Created

| Email | Password | Role |
|-------|----------|------|
| s@t.com | Abc12345 | student |
| t@t.com | Abc12345 | teacher |
```

- [ ] **Step 2: 验证种子脚本幂等**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/backend && ALLOW_E2E_SEED=true DATABASE_URL='mysql+aiomysql://root:123456@localhost:3306/duagent_test?charset=utf8mb4' python scripts/seed_e2e_data.py
```

Expected: 第一次运行显示 "Created"；第二次运行全部显示 "Skipped ... (exists)"。

- [ ] **Step 3: 提交批次 1**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add backend/scripts/seed_e2e_data.py backend/scripts/README.md && git commit -m "feat: add E2E test data seeder script"
```

---

### Task 4: playwright.config.js — 添加 VITE_API_BASE_URL

**Files:**
- Modify: `/home/yezisama/workspace/workflow/EDUagent/frontend/playwright.config.js`

- [ ] **Step 1: 在 webServer.env 中添加**

将第 33-35 行：
```js
env: {
  VITE_USE_MOCK: 'false',
},
```

改为：
```js
env: {
  VITE_USE_MOCK: 'false',
  VITE_API_BASE_URL: 'http://localhost:8001/api/v1',
},
```

---

### Task 5: specs.spec.js — 验证码等待逻辑修复

**Files:**
- Modify: `/home/yezisama/workspace/workflow/EDUagent/frontend/e2e/specs.spec.js`

- [ ] **Step 1: 修复 solveCaptcha — 解析失败时 throw 而非返回 "0"**

将第 4-13 行替换为：
```js
const solveCaptcha = (question) => {
  const match = question.match(/(\d+)\s*([+\-*])\s*(\d+)/);
  if (!match) {
    throw new Error(`Failed to parse captcha question: "${question}"`);
  }
  const num1 = parseInt(match[1]);
  const op = match[2];
  const num2 = parseInt(match[3]);
  if (op === '+') return String(num1 + num2);
  if (op === '-') return String(num1 - num2);
  if (op === '*') return String(num1 * num2);
  throw new Error(`Unknown captcha operator: "${op}"`);
};
```

- [ ] **Step 2: 修复验证码等待 — 等待算术题文本出现**

将第 22-26 行：
```js
const captchaEl = page.locator('button[title="点击刷新验证码"]');
await captchaEl.waitFor({ state: 'visible' });
const question = await captchaEl.innerText();
const answer = solveCaptcha(question);
```

改为：
```js
const captchaEl = page.locator('button[title="点击刷新验证码"]');
await captchaEl.waitFor({ state: 'visible' });
await expect(captchaEl).toHaveText(/^\d+\s*[-+*]\s*\d+\s*=\s*\?\s*$/, { timeout: 5000 });
const question = await captchaEl.innerText();
const answer = solveCaptcha(question);
```

---

### Task 6: 批次 2 提交 — E2E 基础设施

- [ ] **Step 1: 验证 lint 和 build**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```

- [ ] **Step 2: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add frontend/playwright.config.js frontend/e2e/specs.spec.js && git commit -m "fix(e2e): add VITE_API_BASE_URL to playwright config, fix captcha wait condition"
```

---

### Task 7: 批次 3 预验证 — 静态核对 + curl

**无文件修改。仅验证。**

- [ ] **Step 1: 确认测试后端和 Agent 运行中**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8002/agent/v1/health
curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/v1/auth/captcha
```

Expected: 200, 200.

- [ ] **Step 2: curl 验证 login 响应形状**

```bash
CAPTCHA=$(curl -s http://localhost:8001/api/v1/auth/captcha)
TOKEN=$(echo "$CAPTCHA" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['captcha_token'])")
QUESTION=$(echo "$CAPTCHA" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['captcha_question'])")
ANSWER=$(python3 -c "q='$QUESTION'.replace('= ?','').strip(); print(eval(q))")
LOGIN=$(curl -s -X POST http://localhost:8001/api/v1/auth/login -H "Content-Type: application/json" -d "{\"email\":\"s@t.com\",\"password\":\"Abc12345\",\"captcha_token\":\"$TOKEN\",\"captcha_code\":\"$ANSWER\"}")
echo "$LOGIN" | python3 -c "
import sys,json
d=json.load(sys.stdin)
assert d['code']==200, f'login failed: {d}'
data=d['data']
assert 'token' in data, 'missing token'
assert 'user' in data, 'missing user'
assert 'role' in data['user'], 'missing user.role'
print(f'OK: login — role={data[\"user\"][\"role\"]}')
"
JWT=$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['token'])")
```

- [ ] **Step 3: curl 验证 courses 响应形状**

```bash
curl -s http://localhost:8001/api/v1/courses -H "Authorization: Bearer $JWT" | python3 -c "
import sys,json
d=json.load(sys.stdin)
assert d['code']==200
courses=d['data']['courses']
assert isinstance(courses, list), f'courses is not a list: {type(courses)}'
assert len(courses)>=2, f'need >=2 courses, got {len(courses)}'
assert 'id' in courses[0], 'missing course.id'
print(f'OK: {len(courses)} courses — first={courses[0][\"name\"]}')
"
```

- [ ] **Step 4: curl 验证 teaching students 响应形状**

```bash
COURSE_ID=$(curl -s http://localhost:8001/api/v1/courses -H "Authorization: Bearer $JWT" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['courses'][0]['id'])")
curl -s "http://localhost:8001/api/v1/teaching/classes/$COURSE_ID/students" -H "Authorization: Bearer $JWT" | python3 -c "
import sys,json
d=json.load(sys.stdin)
assert d['code']==200
students=d['data']['students']
assert isinstance(students, list)
if len(students)>0:
    s=students[0]
    for f in ['major','grade']:
        assert f in s, f'missing student.{f}'
    print(f'OK: {len(students)} students — first has major={s.get(\"major\")}, grade={s.get(\"grade\")}')
else:
    print('WARN: 0 students in class')
"
```

- [ ] **Step 5: 静态核对 5 个候选文件的 diff**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && for f in \
  frontend/src/pages/Login.jsx \
  frontend/src/context/CourseContext.jsx \
  frontend/src/api/services/teaching.js \
  frontend/src/pages/AIChat.jsx \
  frontend/src/App.jsx; do
  echo "=== $f ==="
  git diff "$f" | head -40
  echo ""
done
```

核对要点：
- Login.jsx: 使用 `login(token, userData)`，消费 `response.data.token` 和 `response.data.user` ✅
- CourseContext.jsx: 使用 `res.data.courses`，消费 `.some()` ✅
- teaching.js: 消费 `data.students[].major/.grade/.joined_at`；透传 StudentLearning ✅
- AIChat.jsx: 兼容 `knowledge_points`/`points`/`data` ✅
- App.jsx: 仅移除 ResourceDetail ✅

---

### Task 8: 批次 3 提交 — 5 个候选修复

**仅当 Task 7 全部验证通过后才提交。**

- [ ] **Step 1: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add \
  frontend/src/pages/Login.jsx \
  frontend/src/context/CourseContext.jsx \
  frontend/src/api/services/teaching.js \
  frontend/src/pages/AIChat.jsx \
  frontend/src/App.jsx && \
  git diff --check --cached && \
  git commit -m "fix(frontend): commit candidate fixes — AuthContext login, CourseContext courses, teaching real API, AIChat multi-key, App route cleanup"
```

---

### Task 9: TeacherStudentReport.jsx — 移除未声明字段

**Files:**
- Modify: `/home/yezisama/workspace/workflow/EDUagent/frontend/src/pages/TeacherStudentReport.jsx`

- [ ] **Step 1: 修复标题中的 report.username**

将标题行：
```jsx
<h1 className="font-h1 text-h1 text-on-background">学情详尽报告 <span className="text-primary-container">· {report.student?.real_name || report.username || '学生报告'}</span></h1>
```

改为：
```jsx
<h1 className="font-h1 text-h1 text-on-background">学情详尽报告 <span className="text-primary-container">· {report.student?.real_name || report.student?.student_id || '学生报告'}</span></h1>
```

- [ ] **Step 2: 修复 Profile banner 中的 report.username 和 report.student_id 回退**

将：
```jsx
<h2 className="text-2xl font-bold text-on-surface mb-1">{report.student?.real_name || report.username || '学生'}</h2>
<p className="text-sm text-secondary">学号: {report.student?.student_id || report.student_id || '未知'} · 班级ID: {classId}</p>
```

改为：
```jsx
<h2 className="text-2xl font-bold text-on-surface mb-1">{report.student?.real_name || report.student?.student_id || '学生'}</h2>
<p className="text-sm text-secondary">学号: {report.student?.student_id || '未知'} · 班级ID: {classId}</p>
```

- [ ] **Step 3: 隐藏 weak_points 区块**

在真实模式（`!useMock`）的 weak_points 区块，将条件渲染改为静态文案：
```jsx
{/* weak_points — 不在正式 StudentLearning 契约中 */}
<p className="text-xs text-outline italic">正式接口暂未提供</p>
```

- [ ] **Step 4: 隐藏 recent_activity 区块**

在真实模式（`!useMock`）的 recent_activity 区块，同样改为：
```jsx
{/* recent_activity — 不在正式 StudentLearning 契约中 */}
<p className="text-xs text-outline italic text-center py-8">正式接口暂未提供</p>
```

注意：不修改 `useMock` 分支内的任何代码。

- [ ] **Step 5: 验证 lint 和 build**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```

---

### Task 10: 批次 4 提交 — TeacherStudentReport

- [ ] **Step 1: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add frontend/src/pages/TeacherStudentReport.jsx && git commit -m "fix(frontend): remove undeclared fields from TeacherStudentReport real mode"
```

---

### Task 11: learning.js — 路径修正

**Files:**
- Modify: `/home/yezisama/workspace/workflow/EDUagent/frontend/src/api/services/learning.js`

- [ ] **Step 1: 修正路径**

将第 20 行 `return apiClient.get(\`/tasks/${taskId}/status\`);` 改为：
```js
return apiClient.get(`/tasks/${taskId}`);
```

- [ ] **Step 2: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add frontend/src/api/services/learning.js && git commit -m "fix(frontend): correct getTaskStatus path to /tasks/{id}"
```

---

### Task 12: WORKFLOW.md — 按实际结果更新

**Files:**
- Modify: `/home/yezisama/workspace/workflow/EDUagent/backend/WORKFLOW.md`

- [ ] **Step 1: 更新标题为反映实际结果**

将第 140 行标题替换为（E2E 全通过时）：
```
- `2026-06-05` `前端阶段一验收缺陷修复（v2）— E2E 3/3 通过`
```
或（E2E 未全通过时）：
```
- `2026-06-05` `前端阶段一验收缺陷修复（v2）— E2E [N/3] 通过`
```

- [ ] **Step 2: 追加验证结果**

在该条目末尾追加：
```markdown
  - **验证结果**：
    - `npm run lint`：[实际]
    - `npm run build`：[实际]
    - `npm run test:e2e`：[实际，含失败原因]
    - `git diff --check`：[实际]
    - Client API 契约漂移：否
    - Agent API 契约漂移：否
```

- [ ] **Step 3: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add backend/WORKFLOW.md && git commit -m "docs: update WORKFLOW.md with v2 verification results"
```

---

### Task 13: 最终 E2E 完整验证

- [ ] **Step 1: 完整启动序列**

```bash
# 0. 创建测试 DB
mysql -u root -p123456 -e "CREATE DATABASE IF NOT EXISTS duagent_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 1. Agent Service
cd /home/yezisama/workspace/workflow/EDUagent/agent_service && ./.venv/bin/uvicorn agent_service.main:app --host 127.0.0.1 --port 8002 &

# 2. Backend (test DB)
cd /home/yezisama/workspace/workflow/EDUagent/backend && DATABASE_URL='mysql+aiomysql://root:123456@localhost:3306/duagent_test?charset=utf8mb4' python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 &

# 3. Seed
cd /home/yezisama/workspace/workflow/EDUagent/backend && ALLOW_E2E_SEED=true DATABASE_URL='mysql+aiomysql://root:123456@localhost:3306/duagent_test?charset=utf8mb4' python scripts/seed_e2e_data.py

# 4. E2E
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run test:e2e
```

Expected: 3/3 passed.

- [ ] **Step 2: 最终全量检查**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
cd /home/yezisama/workspace/workflow/EDUagent && git diff --check && git status --short
```

- [ ] **Step 3: 确认工作区卫生**

确认 `AGENTS.md`、`frontend/.gitkeep` 未纳入提交。`test-results/` 不在追踪列表。
