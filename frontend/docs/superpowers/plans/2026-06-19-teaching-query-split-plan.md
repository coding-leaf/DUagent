# Teaching Query Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Teaching 的单学生报告与班级洞察聚合拆为两个独立 Query Object，同时保持 `TeachingService` 门面、权限边界和 Client API 行为不变。

**Architecture:** Router 继续只调用 `TeachingService`。`TeachingService` 完成课程和 enrollment 校验后，把已验证的数据范围交给 `StudentReportQuery` 或 `ClassInsightsQuery`；两个 Query 复用同一 `AsyncSession` 并只执行只读 SQL。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 2.x async、MySQL 8、Pytest、pytest-asyncio、pytest-cov。

---

## 文件结构

- Create: `backend/app/services/student_report_query.py`
  - 单学生最新记录、Quiz 证据、薄弱点、最近活动及 DTO。
- Create: `backend/app/services/class_insights_query.py`
  - 有效 enrollment 范围、班级 Quiz、薄弱点和路径进度 DTO。
- Modify: `backend/app/services/teaching_service.py`
  - 保留权限、简单学生查询和公开门面；大型聚合方法改为委派。
- Create: `backend/tests/test_student_report_query.py`
  - 学生报告 Query 的纯函数、最新记录和空态测试。
- Create: `backend/tests/test_class_insights_query.py`
  - 班级洞察 Query 的 enrollment、最新路径和空态测试。
- Modify: `backend/tests/test_teaching_service.py`
  - 移除已迁移的聚合测试，新增门面校验后委派测试。
- Modify: `frontend/WORKFLOW.md`
  - 记录实现提交、验证命令与无契约漂移。
- Modify: `frontend/docs/requirements-coverage.md`
  - 更新 Teaching 查询内部边界。

不要修改 `backend/app/api/v1/teaching.py`、Client OpenAPI 或 Agent Service。

## 测试环境

在 `backend/` 执行全部后端命令：

```bash
TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/teaching_refactor_test?charset=utf8mb4'
```

若测试库不存在，先执行：

```bash
docker exec eduagent-mysql mysql -uroot -p123456 -e "CREATE DATABASE IF NOT EXISTS teaching_refactor_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

不得修改 `.env`。

### Task 1: 用红灯测试锁定 Student Report Query 边界

**Files:**
- Create: `backend/tests/test_student_report_query.py`
- Modify: `backend/tests/test_teaching_service.py`

- [ ] **Step 1: 新建 MySQL-only Query 测试基架**

`test_student_report_query.py` 使用与现有 Teaching 测试相同的初始化方式：读取 `TEST_DATABASE_URL`，要求 `mysql+aiomysql://`，设置 `DATABASE_URL`，运行 `init_db()` 后导入模型和目标模块。

测试 helper 使用以下接口：

```python
def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


async def _student(db) -> User:
    user = User(
        username=_uid("student"),
        email=f"{_uid('student')}@test.local",
        password_hash="test",
        role="student",
        real_name="report student",
        student_id=_uid("sid"),
    )
    db.add(user)
    await db.flush()
    return user
```

- [ ] **Step 2: 迁移评分纯函数测试**

从 `test_teaching_service.py` 移动 `test_overall_score_uses_only_finite_scores_in_range` 参数表，并将导入改为：

```python
from app.services.student_report_query import StudentReportQuery, _overall_score
```

断言继续覆盖数字、数字字符串、bool、越界、NaN、Infinity、空 rows 和 `None`。

- [ ] **Step 3: 写 Query 最新记录红灯测试**

创建学生及同一课程下的新旧 Evaluation、UserProfile、LearningPath，直接调用：

```python
data = await StudentReportQuery(db).execute(course_id, student)

assert data["evaluation_summary"] == {
    "overall_score": 75.0,
    "generated_at": new_time.isoformat(),
    "summary_text": "new evaluation",
}
assert data["profile_summary"]["knowledge_mastered"] == 1
assert data["profile_summary"]["knowledge_weak"] == 1
assert data["profile_summary"]["modal_preference"] == ["text_analysis"]
assert data["path_progress"] == {
    "current_node": "new node",
    "completed_nodes": 1,
    "total_nodes": 2,
}
assert data["quiz_stats"] is None
assert data["weak_points"] == []
assert data["recent_activity"] == []
```

该测试不创建 enrollment 或 teacher，证明 Query 只接收已验证的 `User`，不重复权限查询。

- [ ] **Step 4: 运行 RED**

Run:

```bash
TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/teaching_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_student_report_query.py -q -p no:cacheprovider
```

Expected: collection fails with `ModuleNotFoundError: app.services.student_report_query`.

### Task 2: 实现 Student Report Query 并收缩门面

**Files:**
- Create: `backend/app/services/student_report_query.py`
- Modify: `backend/app/services/teaching_service.py`
- Test: `backend/tests/test_student_report_query.py`
- Test: `backend/tests/test_teaching_service.py`

- [ ] **Step 1: 创建 StudentReportQuery**

从 `teaching_service.py` 原样移动 `_overall_score()`、`_ranked_modal_preferences()`、`_latest_evaluation()`、`_latest_profile()`、`_latest_learning_path()`，以及 `get_student_learning()` 在两次权限校验之后的全部语句。将三个 latest helper 变为 `StudentReportQuery` 私有方法，将聚合主体命名为 `execute(class_id: str, student: User)`，并在方法首行设置 `student_id = student.id`。

模块必须包含以下完整对象初始化代码：

```python
class StudentReportQuery:
    """Build a student learning report from already-authorized scope."""

    def __init__(self, db: AsyncSession):
        self.db = db
```

移动后的 SQL、排序、软删除过滤、limit 和 DTO 字段逐项保持原实现；`execute()` 返回 `student`、`evaluation_summary`、`profile_summary`、`path_progress`、`quiz_stats`、`weak_points`、`recent_activity` 七个现有键。

- [ ] **Step 2: 将 TeachingService 改为校验后委派**

删除已经移动的模型和 SQL import，并新增：

```python
from app.services.student_report_query import StudentReportQuery
```

公开方法改为：

```python
async def get_student_learning(
    self,
    class_id: str,
    student_id: str,
    current_user: User,
) -> dict:
    await self.verify_teacher(class_id, current_user)
    student = await self._require_enrolled_student(class_id, student_id)
    return await StudentReportQuery(self.db).execute(class_id, student)
```

- [ ] **Step 3: 写门面委派测试**

在 `test_teaching_service.py` monkeypatch `StudentReportQuery.execute`：

```python
async def fake_execute(query, class_id, enrolled_student):
    assert query.db is db
    assert class_id == course.id
    assert enrolled_student.id == student.id
    return {"sentinel": "student-report"}

monkeypatch.setattr(StudentReportQuery, "execute", fake_execute)
data = await TeachingService(db).get_student_learning(
    course.id, student.id, teacher
)
assert data == {"sentinel": "student-report"}
```

测试必须创建有效 enrollment；现有未入班 404 测试继续证明委派前执行权限校验。

- [ ] **Step 4: 运行 GREEN**

Run:

```bash
TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/teaching_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_student_report_query.py tests/test_teaching_service.py -q -p no:cacheprovider
TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/teaching_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_teacher_student_learning.py -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 5: 提交 Student Report 阶段**

```bash
git add backend/app/services/student_report_query.py backend/app/services/teaching_service.py backend/tests/test_student_report_query.py backend/tests/test_teaching_service.py
git commit -m "refactor(teaching): 拆分学生报告查询"
```

### Task 3: 用红灯测试锁定 Class Insights Query 边界

**Files:**
- Create: `backend/tests/test_class_insights_query.py`
- Modify: `backend/tests/test_teaching_service.py`

- [ ] **Step 1: 新建 MySQL-only Query 测试基架**

复用 Task 1 的数据库初始化规则，但只导入 `CourseEnrollment`、`LearningPath`、`QuizSession`、`User` 和目标 Query。

- [ ] **Step 2: 迁移有效 enrollment 与最新路径测试**

从 `test_teaching_service.py` 迁移 `test_class_insights_uses_active_enrollments_and_latest_paths` 的数据准备，改为直接调用：

```python
data = await ClassInsightsQuery(db).execute(course.id)

assert data["avg_quiz_score"] is None
assert data["total_quiz_attempts"] == 0
assert data["weak_points_top"] == []
assert data["path_node_progress"] == {
    "completed": 0,
    "in_progress": 0,
    "recommended": 0,
    "pending": 1,
    "total_nodes": 1,
}
```

数据必须包含：有效学生的新旧路径、软删除 enrollment 学生的路径和高分 Quiz，证明二者不进入结果。

- [ ] **Step 3: 增加空班级测试**

```python
data = await ClassInsightsQuery(db).execute(course.id)
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

- [ ] **Step 4: 运行 RED**

Run:

```bash
TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/teaching_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_class_insights_query.py -q -p no:cacheprovider
```

Expected: collection fails with `ModuleNotFoundError: app.services.class_insights_query`.

### Task 4: 实现 Class Insights Query 并收缩门面

**Files:**
- Create: `backend/app/services/class_insights_query.py`
- Modify: `backend/app/services/teaching_service.py`
- Test: `backend/tests/test_class_insights_query.py`
- Test: `backend/tests/test_teaching_service.py`

- [ ] **Step 1: 创建 ClassInsightsQuery**

```python
class ClassInsightsQuery:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute(self, class_id: str) -> dict:
        # 原 get_class_insights() 在 verify_teacher() 之后的全部只读聚合。
        # 保持 active_enrollments 子查询、Quiz/weak point 聚合、
        # row_number() 最新路径选择及空班级 DTO 不变。
```

模块只导入该查询实际需要的 SQLAlchemy 构造器以及 `CourseEnrollment`、`LearningPath`、`QuizAnswer`、`QuizQuestion`、`QuizSession`、`User`。

- [ ] **Step 2: 将 TeachingService 改为校验后委派**

新增：

```python
from app.services.class_insights_query import ClassInsightsQuery
```

公开方法改为：

```python
async def get_class_insights(
    self,
    class_id: str,
    current_user: User,
) -> dict:
    await self.verify_teacher(class_id, current_user)
    return await ClassInsightsQuery(self.db).execute(class_id)
```

- [ ] **Step 3: 写门面委派测试**

```python
async def fake_execute(query, class_id):
    assert query.db is db
    assert class_id == course.id
    return {"sentinel": "class-insights"}

monkeypatch.setattr(ClassInsightsQuery, "execute", fake_execute)
data = await TeachingService(db).get_class_insights(course.id, teacher)
assert data == {"sentinel": "class-insights"}
```

现有 403/404 测试继续证明委派前执行任课教师校验。

- [ ] **Step 4: 运行 GREEN**

Run:

```bash
TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/teaching_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_class_insights_query.py tests/test_teaching_service.py -q -p no:cacheprovider
TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/teaching_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_teacher_class_insights.py -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 5: 提交 Class Insights 阶段**

```bash
git add backend/app/services/class_insights_query.py backend/app/services/teaching_service.py backend/tests/test_class_insights_query.py backend/tests/test_teaching_service.py
git commit -m "refactor(teaching): 拆分班级洞察查询"
```

### Task 5: 完整验证、自审与记录

**Files:**
- Modify: `frontend/WORKFLOW.md`
- Modify: `frontend/docs/requirements-coverage.md`

- [ ] **Step 1: 运行 Teaching 全量 MySQL 回归**

```bash
TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/teaching_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_teaching_service.py tests/test_student_report_query.py tests/test_class_insights_query.py -q -p no:cacheprovider
TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/teaching_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_teacher_student_learning.py -q -p no:cacheprovider
TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/teaching_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_teacher_class_insights.py -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 2: 验证定向覆盖率**

```bash
TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/teaching_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_student_report_query.py tests/test_class_insights_query.py --cov=app.services.student_report_query --cov=app.services.class_insights_query --cov-report=term-missing -q -p no:cacheprovider
```

Expected: both Query modules report at least 80% coverage.

HTTP 测试必须分别运行。它们在模块导入阶段通过 `asyncio.run(init_db())` 初始化共享全局 engine；将多个 HTTP 测试文件放进同一 pytest 进程会使 aiomysql 连接跨 event loop 复用并产生与业务无关的 `Future attached to a different loop`。

- [ ] **Step 3: 运行语法与边界检查**

```bash
../.venv/bin/python -m py_compile app/services/teaching_service.py app/services/student_report_query.py app/services/class_insights_query.py app/api/v1/teaching.py
rg -n 'sqlalchemy|app\.models' app/api/v1/teaching.py
```

Expected: `py_compile` exits 0；`rg` 只允许 `sqlalchemy.ext.asyncio.AsyncSession` 和 `app.models.user.User` 这两个 Router 边界依赖，不出现查询构造器或业务聚合模型。

- [ ] **Step 4: 自审职责与规模**

```bash
wc -l app/services/teaching_service.py app/services/student_report_query.py app/services/class_insights_query.py
rg -n '^    async def |^def ' app/services/teaching_service.py app/services/student_report_query.py app/services/class_insights_query.py
git diff --check
```

Expected: `TeachingService` 不再包含 Evaluation/Profile/Path/Quiz 聚合；两个 Query 各只有对应查询职责；diff 无空白错误。

- [ ] **Step 5: 更新记录**

在 `frontend/WORKFLOW.md` 末尾记录：日期、两次拆分提交、涉及文件、全部验证命令与结果、Client API 无漂移、Agent API 无漂移。

在 `frontend/docs/requirements-coverage.md` 的 Teaching 条目记录：Router → TeachingService Facade → StudentReportQuery/ClassInsightsQuery，并注明查询仍来自 MySQL 真实数据。

- [ ] **Step 6: 提交记录**

```bash
git add frontend/WORKFLOW.md frontend/docs/requirements-coverage.md
git commit -m "docs: 记录 teaching 查询拆分验证"
```
