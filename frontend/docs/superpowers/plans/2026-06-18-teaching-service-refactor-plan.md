# Teaching Service Security and Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 Teaching 学生越权读取与假评分，同时把教师端只读查询迁入 `TeachingService`，消除学生列表 N+1 并保持其余 Client API 行为稳定。

**Architecture:** `teaching.py` 只负责 FastAPI 路由、依赖和响应包装；`TeachingService(db)` 负责任课教师校验、enrollment 校验、最新记录读取、报表聚合和 DTO。SQLAlchemy 直接位于 Service，不新增 Repository；全部验收使用独立 MySQL 测试库。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 2.x async、MySQL 8、Pytest、pytest-asyncio、pytest-cov。

---

## 文件结构

- Create: `backend/app/services/teaching_service.py`
  - Teaching 权限、查询、聚合和短小 DTO helper。
- Create: `backend/tests/test_teaching_service.py`
  - Service 单元/集成测试，强制从 `TEST_DATABASE_URL` 使用 MySQL。
- Modify: `backend/app/api/v1/teaching.py`
  - 只保留 4 个 route、依赖和标准响应包装。
- Modify: `backend/tests/test_teacher_student_learning.py`
  - 补真实评分、最新记录和 Profile 状态回归，取消 SQLite 默认值。
- Modify: `backend/tests/test_teacher_class_insights.py`
  - 补最新 LearningPath 统计回归，取消 SQLite 默认值。
- Modify: `docs/10-client-api/Client-API.openapi.json`
  - `overall_score` 增加 nullable。
- Modify: `docs/10-client-api/API_前端接口规范.md`
  - 记录未入班 404 与评分 null 语义。
- Modify: `frontend/WORKFLOW.md`
  - 记录阶段、测试和 Client API 漂移。
- Modify: `frontend/docs/requirements-coverage.md`
  - 更新 Teaching 后端分层和真实数据说明。

每个提交最多涉及 5 个文件。禁止纳入现有 `start_all.sh`、storage、真实测试脚本或其他未提交改动。

## 测试库准备

在 `backend/` 目录执行：

```bash
docker exec eduagent-mysql mysql -uroot -p123456 -e "CREATE DATABASE IF NOT EXISTS teaching_refactor_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

后续统一使用：

```bash
TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/teaching_refactor_test?charset=utf8mb4'
```

不要修改 `.env`。

### Task 1: 锁定评分与权限契约

**Files:**
- Create: `backend/tests/test_teaching_service.py`

- [ ] **Step 1: 创建 MySQL-only 测试基架**

文件开头使用明确环境约束，不提供 SQLite fallback：

```python
import asyncio
import math
import os
import uuid

import pytest
from fastapi import HTTPException

database_url = os.environ.get("TEST_DATABASE_URL")
if not database_url or not database_url.startswith("mysql+aiomysql://"):
    raise RuntimeError("TEST_DATABASE_URL must point to an isolated MySQL database")
os.environ["DATABASE_URL"] = database_url

from app.db.session import async_session_factory, engine, init_db
from app.models.course import Course, CourseEnrollment
from app.models.others import Evaluation, LearningPath, UserProfile
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.models.user import User

async def _init_schema() -> None:
    await init_db()
    await engine.dispose()


asyncio.run(_init_schema())

from app.services.teaching_service import TeachingService, _overall_score


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


async def _user(db, role: str, prefix: str) -> User:
    user = User(
        username=_uid(prefix),
        email=f"{_uid(prefix)}@test.local",
        password_hash="test",
        role=role,
        real_name=f"{prefix} name",
        student_id=_uid("sid") if role == "student" else "",
    )
    db.add(user)
    await db.flush()
    return user


async def _course(db):
    teacher = await _user(db, "teacher", "teacher")
    course = Course(name="Teaching Test", course_code=_uid("course"), teacher_id=teacher.id)
    db.add(course)
    await db.flush()
    return teacher, course
```

- [ ] **Step 2: 写评分红灯测试**

```python
@pytest.mark.parametrize(
    ("table", "expected"),
    [
        ({"rows": [{"average_score": 80}, {"average_score": "60"}]}, 70.0),
        ({"rows": [{"average_score": True}, {"average_score": 101}, {"average_score": -1}]}, None),
        ({"rows": [{"average_score": "nan"}, {"average_score": "inf"}, {}]}, None),
        ({"rows": []}, None),
        (None, None),
    ],
)
def test_overall_score_uses_only_finite_scores_in_range(table, expected):
    assert _overall_score(table) == expected
```

- [ ] **Step 3: 写未入班详情红灯测试**

```python
@pytest.mark.asyncio
async def test_get_student_info_hides_non_enrolled_user():
    async with async_session_factory() as db:
        teacher, course = await _course(db)
        outsider = await _user(db, "student", "outsider")
        await db.commit()

        with pytest.raises(HTTPException) as exc:
            await TeachingService(db).get_student_info(course.id, outsider.id, teacher)

        assert exc.value.status_code == 404
        assert exc.value.detail == {"code": 40400, "message": "学生未入班", "data": None}
```

- [ ] **Step 4: 运行 RED**

```bash
TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/teaching_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_teaching_service.py -q -p no:cacheprovider
```

Expected: collection fails with `ModuleNotFoundError: app.services.teaching_service`.

不要提交红灯状态，直接进入 Task 2。

### Task 2: 实现权限、评分与学生列表

**Files:**
- Create: `backend/app/services/teaching_service.py`
- Modify: `backend/tests/test_teaching_service.py`

- [ ] **Step 1: 实现基础 Service 和评分纯函数**

```python
import math

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course, CourseEnrollment
from app.models.user import User


def _overall_score(mastery_table: object) -> float | None:
    if not isinstance(mastery_table, dict) or not isinstance(mastery_table.get("rows"), list):
        return None
    scores: list[float] = []
    for row in mastery_table["rows"]:
        if not isinstance(row, dict):
            continue
        raw = row.get("average_score")
        if isinstance(raw, bool):
            continue
        try:
            score = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(score) and 0 <= score <= 100:
            scores.append(score)
    return round(sum(scores) / len(scores), 1) if scores else None


class TeachingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def verify_teacher(self, class_id: str, current_user: User) -> Course:
        result = await self.db.execute(
            select(Course).where(Course.id == class_id, Course.is_deleted.is_(False))
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

    async def _require_enrolled_student(self, class_id: str, student_id: str) -> User:
        result = await self.db.execute(
            select(User)
            .join(CourseEnrollment, CourseEnrollment.student_id == User.id)
            .where(
                User.id == student_id,
                User.is_deleted.is_(False),
                CourseEnrollment.course_id == class_id,
                CourseEnrollment.is_deleted.is_(False),
            )
            .limit(1)
        )
        student = result.scalar_one_or_none()
        if student is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 40400, "message": "学生未入班", "data": None},
            )
        return student
```

- [ ] **Step 2: 实现详情和有界学生列表**

```python
    async def get_student_info(self, class_id: str, student_id: str, current_user: User) -> dict:
        await self.verify_teacher(class_id, current_user)
        user = await self._require_enrolled_student(class_id, student_id)
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

    async def list_students(
        self, class_id: str, current_user: User, page: int, page_size: int
    ) -> dict:
        await self.verify_teacher(class_id, current_user)
        active = (
            CourseEnrollment.course_id == class_id,
            CourseEnrollment.is_deleted.is_(False),
            User.is_deleted.is_(False),
        )
        count_result = await self.db.execute(
            select(func.count(CourseEnrollment.id))
            .join(User, User.id == CourseEnrollment.student_id)
            .where(*active)
        )
        rows = await self.db.execute(
            select(CourseEnrollment, User)
            .join(User, User.id == CourseEnrollment.student_id)
            .where(*active)
            .order_by(CourseEnrollment.create_time.asc(), CourseEnrollment.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        students = [
            {
                "id": user.id,
                "username": user.username,
                "real_name": user.real_name,
                "student_id": user.student_id,
                "major": user.major,
                "grade": user.grade,
                "joined_at": enrollment.create_time.isoformat() if enrollment.create_time else "",
            }
            for enrollment, user in rows.all()
        ]
        return {
            "students": students,
            "total": count_result.scalar() or 0,
            "page": page,
            "page_size": page_size,
        }
```

- [ ] **Step 3: 补列表顺序、软删除和固定查询数测试**

测试使用 SQLAlchemy `event.listen(engine.sync_engine, "before_cursor_execute", listener)`；在调用 `list_students()` 前清空计数，分别记录 1 人和 20 人页面的语句数，断言两者相同且为固定正数，不硬编码具体次数（ORM 的固定 eager-load 查询不应被误判为 N+1）。在 `finally` 中 `event.remove`，避免污染其他测试。另断言返回顺序与 enrollment `create_time/id` 一致、软删除 enrollment 和 User 均不出现。

- [ ] **Step 4: 运行 GREEN 与覆盖率**

```bash
TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/teaching_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_teaching_service.py -q -p no:cacheprovider --cov=app.services.teaching_service --cov-report=term-missing
```

Expected: 当前测试通过；覆盖率不足 80%可以继续后续任务，不在本阶段伪造覆盖。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/teaching_service.py backend/tests/test_teaching_service.py
git commit -m "refactor(teaching): 收口权限与学生查询"
```

### Task 3: 迁移单学生学习报告

**Files:**
- Modify: `backend/app/services/teaching_service.py`
- Modify: `backend/tests/test_teaching_service.py`
- Modify: `backend/tests/test_teacher_student_learning.py`

- [ ] **Step 1: 写最新记录、真实评分和 Profile 红灯测试**

构造同一学生同一课程的两条 Evaluation/Profile/LearningPath，旧记录使用较早 `generated_at`，新记录使用较晚时间。断言：

```python
assert data["evaluation_summary"]["overall_score"] == 75.0  # rows 70 与 80
assert data["evaluation_summary"]["summary_text"] == "new evaluation"
assert data["profile_summary"]["knowledge_mastered"] == 1
assert data["profile_summary"]["knowledge_weak"] == 1
assert data["path_progress"]["current_node"] == "new node"
```

新 Profile coordinates 必须同时包含 `mastered`、`weak`、`learning`、`pending`，验证后两者不计入 weak。再增加无有效 `average_score` 时 `overall_score is None` 的用例。

- [ ] **Step 2: 运行 RED**

```bash
TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/teaching_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_teaching_service.py -q -p no:cacheprovider
```

Expected: `TeachingService` 缺少 `get_student_learning`。

- [ ] **Step 3: 实现统一最新记录 helper**

```python
    async def _latest_evaluation(self, user_id: str, course_id: str):
        result = await self.db.execute(
            select(Evaluation)
            .where(
                Evaluation.user_id == user_id,
                Evaluation.course_id == course_id,
                Evaluation.is_deleted.is_(False),
            )
            .order_by(
                Evaluation.generated_at.desc(),
                Evaluation.create_time.desc(),
                Evaluation.id.desc(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()
```

同时实现另外两个明确 helper：

```python
    async def _latest_profile(self, user_id: str, course_id: str):
        result = await self.db.execute(
            select(UserProfile)
            .where(
                UserProfile.user_id == user_id,
                UserProfile.course_id == course_id,
                UserProfile.is_deleted.is_(False),
            )
            .order_by(
                UserProfile.generated_at.desc(),
                UserProfile.create_time.desc(),
                UserProfile.id.desc(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _latest_learning_path(self, user_id: str, course_id: str):
        result = await self.db.execute(
            select(LearningPath)
            .where(
                LearningPath.user_id == user_id,
                LearningPath.course_id == course_id,
                LearningPath.is_deleted.is_(False),
            )
            .order_by(
                LearningPath.generated_at.desc(),
                LearningPath.create_time.desc(),
                LearningPath.id.desc(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()
```

- [ ] **Step 4: 实现学习报告**

`get_student_learning()` 先调用 `verify_teacher()` 和 `_require_enrolled_student()`；复用当前 `teaching.py` 的 mastery breakdown、weak points、recent activity 查询与 DTO 字段，但做以下强制替换：

```python
quiz_result = await self.db.execute(
    select(
        func.count(QuizSession.id).label("total_attempts"),
        func.avg(QuizSession.score).label("avg_score"),
        func.avg(QuizSession.time_spent).label("avg_time"),
    ).where(
        QuizSession.user_id == student_id,
        QuizSession.course_id == class_id,
        QuizSession.is_deleted.is_(False),
    )
)
quiz_row = quiz_result.one()
quiz_stats = None
if quiz_row.total_attempts:
    quiz_stats = {
        "total_attempts": quiz_row.total_attempts,
        "avg_score": round(float(quiz_row.avg_score), 1),
        "avg_time_spent": int(float(quiz_row.avg_time)),
        "mastery_breakdown": mastery_breakdown,
    }
```

Evaluation DTO：

```python
evaluation_summary = None
if evaluation:
    evaluation_summary = {
        "overall_score": _overall_score(evaluation.mastery_table),
        "generated_at": evaluation.generated_at.isoformat() if evaluation.generated_at else None,
        "summary_text": evaluation.summary_text or None,
    }
```

Profile 计数：

```python
coordinates = profile.knowledge_coordinates if isinstance(profile.knowledge_coordinates, list) else []
mastered = sum(row.get("status") == "mastered" for row in coordinates if isinstance(row, dict))
weak = sum(row.get("status") == "weak" for row in coordinates if isinstance(row, dict))
```

recent activity 必须增加 `QuizSession.id.desc()` 次排序。所有原响应 key 保持不变。

- [ ] **Step 5: 将既有 HTTP 测试切换为 MySQL-only 并补评分断言**

在 `test_teacher_student_learning.py` 用以下代码替换 SQLite fallback：

```python
database_url = os.environ.get("TEST_DATABASE_URL")
if not database_url or not database_url.startswith("mysql+aiomysql://"):
    raise RuntimeError("TEST_DATABASE_URL must point to an isolated MySQL database")
os.environ["DATABASE_URL"] = database_url
```

并把模块级 `asyncio.run(init_db())` 替换为以下初始化，确保建表连接在初始化事件循环关闭前释放：

```python
from app.db.session import async_session_factory, engine, init_db


async def _init_schema() -> None:
    await init_db()
    await engine.dispose()


asyncio.run(_init_schema())
```

为测试 Evaluation 写入 `mastery_table={"rows": [{"average_score": 70}, {"average_score": 80}]}`，断言 `overall_score == 75.0`；再写空 rows 断言 null。

- [ ] **Step 6: 运行 GREEN 并提交**

```bash
TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/teaching_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_teaching_service.py tests/test_teacher_student_learning.py -q -p no:cacheprovider
git add backend/app/services/teaching_service.py backend/tests/test_teaching_service.py backend/tests/test_teacher_student_learning.py
git commit -m "refactor(teaching): 迁移真实学情聚合"
```

Expected: 全部通过。

### Task 4: 迁移班级洞察

**Files:**
- Modify: `backend/app/services/teaching_service.py`
- Modify: `backend/tests/test_teaching_service.py`
- Modify: `backend/tests/test_teacher_class_insights.py`

- [ ] **Step 1: 写每名学生只统计最新路径的红灯测试**

同一学生写入旧/新两条 LearningPath，旧路径含 3 个 completed，新路径含 1 个 pending。断言班级结果仅为：

```python
assert data["path_node_progress"] == {
    "completed": 0,
    "in_progress": 0,
    "recommended": 0,
    "pending": 1,
    "total_nodes": 1,
}
```

另写 soft-deleted enrollment 完全不参与 quiz、weak points 和 path progress 的用例。

- [ ] **Step 2: 运行 RED**

Expected: 缺少 `get_class_insights`。

- [ ] **Step 3: 实现班级聚合**

使用有效 enrollment 子查询：

```python
enrolled = (
    select(CourseEnrollment.student_id)
    .join(User, User.id == CourseEnrollment.student_id)
    .where(
        CourseEnrollment.course_id == class_id,
        CourseEnrollment.is_deleted.is_(False),
        User.is_deleted.is_(False),
    )
)
```

Quiz 和 weak point 查询用 `QuizSession.user_id.in_(enrolled)`，不先构造 Python `student_ids`。LearningPath 用 MySQL 8 窗口函数：

```python
ranked = (
    select(
        LearningPath.id.label("path_id"),
        LearningPath.nodes.label("nodes"),
        func.row_number().over(
            partition_by=LearningPath.user_id,
            order_by=(
                LearningPath.generated_at.desc(),
                LearningPath.create_time.desc(),
                LearningPath.id.desc(),
            ),
        ).label("row_num"),
    )
    .where(
        LearningPath.course_id == class_id,
        LearningPath.user_id.in_(enrolled),
        LearningPath.is_deleted.is_(False),
    )
    .subquery()
)
latest_paths = await self.db.execute(select(ranked.c.nodes).where(ranked.c.row_num == 1))
```

复用当前四种状态与空班级 DTO；未知状态继续忽略。

- [ ] **Step 4: 切换并扩展 HTTP 测试**

`test_teacher_class_insights.py` 删除 SQLite fallback，替换为：

```python
database_url = os.environ.get("TEST_DATABASE_URL")
if not database_url or not database_url.startswith("mysql+aiomysql://"):
    raise RuntimeError("TEST_DATABASE_URL must point to an isolated MySQL database")
os.environ["DATABASE_URL"] = database_url
```

并使用与 Task 3 相同的 `_init_schema()`（`init_db()` 后在同一事件循环 `await engine.dispose()`）替换模块级 `asyncio.run(init_db())`，避免 aiomysql 连接池跨事件循环。

然后补充 Step 1 定义的重复 LearningPath 用例。

- [ ] **Step 5: 运行与提交**

```bash
TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/teaching_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_teaching_service.py tests/test_teacher_class_insights.py -q -p no:cacheprovider
git add backend/app/services/teaching_service.py backend/tests/test_teaching_service.py backend/tests/test_teacher_class_insights.py
git commit -m "refactor(teaching): 迁移班级洞察查询"
```

### Task 5: 精简 Router 并锁定 HTTP 契约

**Files:**
- Modify: `backend/app/api/v1/teaching.py`
- Modify: `backend/tests/test_teaching_service.py`
- Modify: `backend/tests/test_teacher_student_learning.py`

- [ ] **Step 1: 增加未入班详情 HTTP 红灯测试**

通过真实 teacher token 请求 `/api/v1/teaching/classes/{class_id}/students/{outsider_id}`，断言 404 和 `学生未入班`，同时保留非任课教师 403 回归。

- [ ] **Step 2: 将 Router 改为薄适配层**

四个 route 均采用以下形态：

```python
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
```

学生详情、学习报告、班级洞察只替换 Service 方法名和路径参数。删除 `case/func/select` 与 Course、Enrollment、Evaluation、Profile、Path、Quiz ORM imports。

- [ ] **Step 3: 运行 Router 回归和语法检查**

```bash
PYTHONPYCACHEPREFIX=/tmp/eduagent_pycache ../.venv/bin/python -m py_compile app/api/v1/teaching.py app/services/teaching_service.py
TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/teaching_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_teaching_service.py tests/test_teacher_student_learning.py tests/test_teacher_class_insights.py -q -p no:cacheprovider
rg -n "from sqlalchemy import|CourseEnrollment|Evaluation|LearningPath|UserProfile|Quiz" app/api/v1/teaching.py
```

Expected: 语法与测试通过；`rg` 无匹配。

- [ ] **Step 4: 运行定向覆盖率**

```bash
TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/teaching_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_teaching_service.py tests/test_teacher_student_learning.py tests/test_teacher_class_insights.py -q -p no:cacheprovider --cov=app.services.teaching_service --cov=app.api.v1.teaching --cov-report=term-missing
```

Expected: 总定向覆盖率 >= 80%。若不足，针对 missing lines 增加具体分支测试后重跑，不使用 pragma 排除业务分支。

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/v1/teaching.py backend/app/services/teaching_service.py backend/tests/test_teaching_service.py backend/tests/test_teacher_student_learning.py backend/tests/test_teacher_class_insights.py
git commit -m "refactor(teaching): 收口路由与接口权限"
```

### Task 6: 更新 Client 契约文档

**Files:**
- Modify: `docs/10-client-api/Client-API.openapi.json`
- Modify: `docs/10-client-api/API_前端接口规范.md`

- [ ] **Step 1: 更新 OpenAPI nullable**

在 `StudentLearning.evaluation_summary.overall_score` 增加：

```json
"nullable": true
```

描述改为“最新评估知识点 average_score 的有效平均值；无有效掌握度数据时为 null”。不改变路径、参数或其他字段。

- [ ] **Step 2: 更新中文规范**

明确：

```markdown
- `evaluation_summary.overall_score` 为最新 Evaluation `mastery_table` 中有效 `average_score` 的平均值；没有有效值时为 `null`。
- 学生个人信息与学习情况接口均要求 `student_id` 存在当前班级的有效 enrollment；否则统一返回 404“学生未入班”。
```

- [ ] **Step 3: 校验并提交**

```bash
python -m json.tool docs/10-client-api/Client-API.openapi.json >/tmp/client-api-openapi-check.json
git diff --check -- docs/10-client-api/Client-API.openapi.json docs/10-client-api/API_前端接口规范.md
git add docs/10-client-api/Client-API.openapi.json docs/10-client-api/API_前端接口规范.md
git commit -m "docs: 对齐 teaching 权限与评分契约"
```

### Task 7: 最终验证与记录

**Files:**
- Modify: `frontend/WORKFLOW.md`
- Modify: `frontend/docs/requirements-coverage.md`

- [ ] **Step 1: 运行最终验证**

```bash
cd backend
PYTHONPYCACHEPREFIX=/tmp/eduagent_pycache ../.venv/bin/python -m py_compile app/api/v1/teaching.py app/services/teaching_service.py
TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/teaching_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_teaching_service.py tests/test_teacher_student_learning.py tests/test_teacher_class_insights.py -q -p no:cacheprovider --cov=app.services.teaching_service --cov=app.api.v1.teaching --cov-report=term-missing
```

Expected: 全部通过、定向覆盖率 >= 80%。

- [ ] **Step 2: 人工审查 diff**

```bash
git status --short
git diff --check HEAD~5..HEAD
git diff --stat HEAD~5..HEAD
```

确认未包含 `start_all.sh`、storage、`.env`、密钥、volume、用户文件或 Agent Service 改动。

- [ ] **Step 3: 更新记录**

`frontend/WORKFLOW.md` 记录：安全缺口、假评分、Service 分层、查询优化、实际测试命令与结果、Client API 两项漂移、Agent API 无漂移。

`frontend/docs/requirements-coverage.md` 在教师学情项注明：详情与报告均校验 enrollment，评分来自真实 mastery 数据，后端已按 Router → TeachingService → DB 分层。

- [ ] **Step 4: 提交记录**

```bash
git add frontend/WORKFLOW.md frontend/docs/requirements-coverage.md
git commit -m "docs: 记录 teaching 重构验证结果"
```

## 最终验收清单

- [ ] Router 不包含 SQLAlchemy 查询或业务 ORM imports。
- [ ] 未入班用户的详情和学习报告均为 404，不泄露用户存在性。
- [ ] `overall_score` 不再硬编码，number/null 均有测试。
- [ ] 学生列表查询数不随学生数增长，分页排序稳定。
- [ ] Evaluation/Profile/LearningPath 重复历史数据按统一规则选择最新记录。
- [ ] 班级路径统计每名学生只使用最新 LearningPath。
- [ ] Quiz 汇总由 SQL 聚合完成。
- [ ] MySQL 回归通过，定向覆盖率 >= 80%。
- [ ] Client API 漂移已同步文档，Agent API 无漂移。
- [ ] 每个提交不超过 5 个文件，未纳入无关工作区改动。
