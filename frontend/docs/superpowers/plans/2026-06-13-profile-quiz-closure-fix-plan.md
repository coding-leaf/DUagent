# Profile Quiz Closure Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复学生画像补充、保底题模板漏网和 Quiz 固定 UI，使 C 语言基础学习闭环不再出现假接口、假题和假页面语义。

**Architecture:** 先补齐 Agent Service 的 `profile/dialogue-update` 契约，再让 Backend 已有画像补充链路调用真实 Agent 路由；题库生成侧加强 skeleton 模板过滤，防止对象选项和字符串选项都漏网；Quiz 页面改成由课程名、题目元数据和当前节点驱动的通用练习页，不展示数据结构硬编码。每个修复点都有独立回归测试或构建验证。

**Tech Stack:** FastAPI、Pydantic、SQLAlchemy async、MySQL、React 19、Vite、ESLint、pytest。

---

## File Structure

- Modify: `../agent_service/schemas/profile.py`
  - 新增 `ProfileDialogueUpdateRequest`、`ProfileDialogueUpdateData`、`ProfileDialogueUpdateResponse`。
- Modify: `../agent_service/api/v1/profile.py`
  - 新增 `POST /agent/v1/profile/dialogue-update`，先用确定性规则解析自然语言补充，后续可再接 LLM。
- Modify: `../agent_service/tests/test_profile_agent.py`
  - 增加 Agent 路由测试，保证 OpenAPI 和直接函数调用不会再缺路由。
- Modify: `../backend/tests/test_refresh_async.py`
  - 增加 Backend 画像补充测试对 Agent path 的断言，防止再改错路由。
- Modify: `../backend/app/api/v1/catalogs.py`
  - 强化 `_is_skeleton_quiz_question()`，兼容对象选项和字符串选项。
- Modify: `../backend/tests/test_admin_catalog_resource_generation.py`
  - 增加字符串数组模板题拒绝测试。
- Modify: `../backend/app/api/v1/quiz.py`
  - `GET /quiz/questions` 返回 `chapter`、`knowledge_point`、`difficulty`，供前端通用 UI 使用。
- Modify: `src/pages/Quiz.jsx`
  - 去掉“数据结构智慧训练”“第4章：树形结构”“树与二叉树”“18:45”“节点索引关系示意图区域”等硬编码，改用真实课程名与题目元数据。
- Modify: `WORKFLOW.md`
  - 记录本次修复、验证命令和剩余风险。

---

### Task 1: Agent Service 增加画像补充接口

**Files:**
- Modify: `../agent_service/schemas/profile.py`
- Modify: `../agent_service/api/v1/profile.py`
- Test: `../agent_service/tests/test_profile_agent.py`

- [ ] **Step 1: Write failing Agent schema/API tests**

Append to `../agent_service/tests/test_profile_agent.py`:

```python
def test_profile_dialogue_update_extracts_goal_weak_points_and_preferences() -> None:
    import asyncio
    from agent_service.api.v1.profile import update_profile_by_dialogue
    from agent_service.schemas.profile import ProfileDialogueUpdateRequest

    response = asyncio.run(
        update_profile_by_dialogue(
            ProfileDialogueUpdateRequest(
                user_id="student-1",
                course_id="course-c",
                message="我想两周内补齐 C 语言指针和动态内存分配，最好多给代码练习和图解。",
            )
        )
    )

    assert response.code == 200
    assert response.data.learning_goal == "我想两周内补齐 C 语言指针和动态内存分配，最好多给代码练习和图解。"
    assert "动态内存分配" in response.data.weak_points
    assert "code_practice" in response.data.preferred_resources
    assert "chart_logic" in response.data.preferred_resources


def test_profile_dialogue_update_route_is_in_openapi() -> None:
    from agent_service.main import app

    schema = app.openapi()

    assert "/agent/v1/profile/dialogue-update" in schema["paths"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `../agent_service`:

```bash
../.venv/bin/python -m pytest tests/test_profile_agent.py -q -p no:cacheprovider
```

Expected: FAIL because `ProfileDialogueUpdateRequest` and `update_profile_by_dialogue` do not exist.

- [ ] **Step 3: Add profile dialogue schemas**

In `../agent_service/schemas/profile.py`, after `ProfileGenerateResponse` add:

```python
class ProfileDialogueUpdateRequest(BaseModel):
    user_id: str = Field(..., description="用户 ID")
    course_id: str = Field(..., description="课程 ID")
    message: str = Field(..., min_length=1, max_length=1000, description="学生补充文本")


class ProfileDialogueUpdateData(BaseModel):
    learning_goal: str | None = Field(None, description="自然语言学习目标")
    weak_points: list[str] = Field(default_factory=list, description="学生自述薄弱点")
    preferred_resources: list[str] = Field(default_factory=list, description="资源偏好键")
    guidance_level: GuidanceLevel | None = Field(None, description="可选引导粒度")


class ProfileDialogueUpdateResponse(ApiResponse[ProfileDialogueUpdateData]):
    pass
```

- [ ] **Step 4: Add deterministic Agent route**

In `../agent_service/api/v1/profile.py`, replace the schema import with:

```python
from agent_service.schemas.profile import (
    ProfileDialogueUpdateData,
    ProfileDialogueUpdateRequest,
    ProfileDialogueUpdateResponse,
    ProfileGenerateRequest,
    ProfileGenerateResponse,
)
```

Then append after `generate_profile()`:

```python
def _extract_dialogue_profile(message: str) -> ProfileDialogueUpdateData:
    text = message.strip()
    weak_points: list[str] = []
    preferred_resources: list[str] = []

    weak_keywords = ["动态内存分配", "指针", "数组", "字符串", "输入输出", "函数", "递归", "结构体"]
    for keyword in weak_keywords:
        if keyword in text:
            weak_points.append(keyword)

    if any(keyword in text for keyword in ["代码", "编程", "实操", "练习"]):
        preferred_resources.append("code_practice")
    if any(keyword in text for keyword in ["图解", "图示", "流程图", "示意图"]):
        preferred_resources.append("chart_logic")
    if any(keyword in text for keyword in ["阅读", "文本", "讲义", "材料"]):
        preferred_resources.append("text_analysis")

    guidance_level = None
    if "少提示" in text or "自己思考" in text:
        guidance_level = "L1"
    elif "分步骤" in text or "逐步" in text:
        guidance_level = "L2"
    elif "直接给答案" in text or "保姆" in text:
        guidance_level = "L3"

    return ProfileDialogueUpdateData(
        learning_goal=text,
        weak_points=list(dict.fromkeys(weak_points)),
        preferred_resources=list(dict.fromkeys(preferred_resources)),
        guidance_level=guidance_level,
    )


@router.post(
    "/dialogue-update",
    response_model=ProfileDialogueUpdateResponse,
    tags=["Profile"],
    summary="对话补充用户画像",
)
async def update_profile_by_dialogue(request: ProfileDialogueUpdateRequest) -> ProfileDialogueUpdateResponse:
    data = _extract_dialogue_profile(request.message)
    return ProfileDialogueUpdateResponse(code=200, message="success", data=data)
```

- [ ] **Step 5: Run Agent tests**

Run from `../agent_service`:

```bash
../.venv/bin/python -m pytest tests/test_profile_agent.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 6: Commit Agent fix**

```bash
git add ../agent_service/schemas/profile.py ../agent_service/api/v1/profile.py ../agent_service/tests/test_profile_agent.py
git commit -m "补齐画像对话补充接口"
```

---

### Task 2: Backend 画像补充链路加路径防回归测试

**Files:**
- Modify: `../backend/tests/test_refresh_async.py`

- [ ] **Step 1: Tighten existing path assertion**

In the `profile/dialogue-update success` section of `../backend/tests/test_refresh_async.py`, replace:

```python
payload = mock_agent.await_args.args[1] if mock_agent.await_args else {}
chk("dialogue-update → agent course_id", payload.get("course_id") == course_id)
```

with:

```python
agent_path = mock_agent.await_args.args[0] if mock_agent.await_args else ""
payload = mock_agent.await_args.args[1] if mock_agent.await_args else {}
chk("dialogue-update → agent path",
    agent_path == "/agent/v1/profile/dialogue-update")
chk("dialogue-update → agent course_id", payload.get("course_id") == course_id)
chk("dialogue-update → agent message passthrough",
    "动态内存分配" in payload.get("message", ""))
```

- [ ] **Step 2: Run Backend profile test**

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/student_profile_loop_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_refresh_async.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 3: Commit Backend profile test**

```bash
git add ../backend/tests/test_refresh_async.py
git commit -m "补充画像对话链路回归断言"
```

---

### Task 3: 修复模板题过滤漏网

**Files:**
- Modify: `../backend/app/api/v1/catalogs.py`
- Modify: `../backend/tests/test_admin_catalog_resource_generation.py`

- [ ] **Step 1: Write failing test for string-array skeleton options**

Append to `../backend/tests/test_admin_catalog_resource_generation.py` after `test_admin_catalog_quiz_child_rejects_skeleton_fallback_questions()`:

```python
async def test_admin_catalog_quiz_child_rejects_skeleton_fallback_string_options():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    class_id = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")
    child_id = "quiz-child-skeleton-string-options"
    async with async_session_factory() as db:
        db.add(
            AsyncTask(
                id=child_id,
                task_type="quiz_generation",
                status="processing",
                progress=10,
                user_id="admin-admin-gen",
                course_id=class_id,
                result={
                    "catalog_id": catalog_id,
                    "agent_course_id": catalog_id,
                    "node_name": "输入输出函数",
                    "chapter": "第7章 输入输出",
                    "course_ids": [class_id],
                },
            )
        )
        await db.commit()

    with patch("app.api.v1.catalogs.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = {
            "questions": [
                {
                    "type": "multi_choice",
                    "content": "第 7 题：请围绕输入输出函数完成一道多选题。",
                    "options": ["正确表述", "易混淆表述", "相关补充表述", "无关表述"],
                    "answer": ["A", "C"],
                    "explanation": "本题用于检查对输入输出函数的基础理解。",
                }
            ]
        }
        from app.api.v1.catalogs import _generate_quiz_for_child

        async with async_session_factory() as db:
            result = await _generate_quiz_for_child(db, child_id, [class_id])
            await db.commit()

            questions = (
                await db.execute(
                    select(QuizQuestion).where(
                        QuizQuestion.course_id == class_id,
                        QuizQuestion.is_deleted == False,
                    )
                )
            ).scalars().all()

    assert result["status"] == "failed"
    assert result["error"] == "skeleton_rejected"
    assert questions == []
```

- [ ] **Step 2: Run test to verify it fails**

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/admin_catalog_quiz_fix_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py::test_admin_catalog_quiz_child_rejects_skeleton_fallback_string_options -q -p no:cacheprovider
```

Expected: FAIL because current `_is_skeleton_quiz_question()` ignores string options.

- [ ] **Step 3: Implement robust option text extraction**

In `../backend/app/api/v1/catalogs.py`, replace `_is_skeleton_quiz_question()` with:

```python
def _quiz_option_text(option) -> str:
    if isinstance(option, dict):
        return str(option.get("text") or option.get("label") or option.get("content") or "").strip()
    return str(option or "").strip()


def _is_skeleton_quiz_question(question: dict) -> bool:
    if not isinstance(question, dict):
        return False
    content = str(question.get("content") or "")
    if "请围绕" not in content or "完成一道" not in content:
        return False
    options = question.get("options")
    if not isinstance(options, list):
        return False
    option_texts = [_quiz_option_text(option) for option in options]
    option_texts = [text for text in option_texts if text]
    return option_texts == ["正确表述", "易混淆表述", "相关补充表述", "无关表述"]
```

- [ ] **Step 4: Run targeted and full Admin quiz tests**

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/admin_catalog_quiz_fix_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py::test_admin_catalog_quiz_child_rejects_skeleton_fallback_questions tests/test_admin_catalog_resource_generation.py::test_admin_catalog_quiz_child_rejects_skeleton_fallback_string_options -q -p no:cacheprovider
```

Expected: `2 passed`.

Then run:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/admin_catalog_quiz_fix_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py -q -p no:cacheprovider
```

Expected: PASS for all tests in file.

- [ ] **Step 5: Commit skeleton filter fix**

```bash
git add ../backend/app/api/v1/catalogs.py ../backend/tests/test_admin_catalog_resource_generation.py
git commit -m "修复模板题过滤漏网"
```

---

### Task 4: Quiz API 返回题目元数据

**Files:**
- Modify: `../backend/app/api/v1/quiz.py`
- Test: `../backend/tests/test_learning_path_fallback.py`

- [ ] **Step 1: Extend existing node quiz assertion**

In `../backend/tests/test_learning_path_fallback.py`, in `test_quiz_questions_node_id_filter_returns_node_questions()`, after:

```python
assert questions[0]["content"] == "Q1 for Node1"
```

add:

```python
assert questions[0]["knowledge_point"] == "Node1"
assert "chapter" in questions[0]
assert "difficulty" in questions[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/learning_path_quiz_meta_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_learning_path_fallback.py::test_quiz_questions_node_id_filter_returns_node_questions -q -p no:cacheprovider
```

Expected: FAIL because question response does not include metadata.

- [ ] **Step 3: Add metadata fields to question response**

In `../backend/app/api/v1/quiz.py`, replace the question dict inside `get_questions()` with:

```python
{
    "id": q.id,
    "type": q.type,
    "source": q.source,
    "personalized": q.personalized,
    "chapter": q.chapter,
    "knowledge_point": q.knowledge_point,
    "difficulty": q.difficulty,
    "content": q.content,
    "options": q.options if q.options is not None else [],
}
```

- [ ] **Step 4: Run Backend quiz metadata test**

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/learning_path_quiz_meta_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_learning_path_fallback.py::test_quiz_questions_node_id_filter_returns_node_questions -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 5: Commit Quiz API metadata**

```bash
git add ../backend/app/api/v1/quiz.py ../backend/tests/test_learning_path_fallback.py
git commit -m "补充练习题目元数据"
```

---

### Task 5: Quiz 页面改成通用练习 UI

**Files:**
- Modify: `src/pages/Quiz.jsx`

- [ ] **Step 1: Replace static context with computed course/question context**

In `src/pages/Quiz.jsx`, change the CourseContext line:

```javascript
const { activeCourseId } = useCourse();
```

to:

```javascript
const { activeCourseId, courses } = useCourse();
```

After `progressPercent` add:

```javascript
const activeCourse = courses.find((course) => course.id === activeCourseId);
const courseName = activeCourse?.name || '课程练习';
const currentKnowledgePoint = currentQuestion.knowledge_point || currentQuestion.knowledgePoint || '综合练习';
const currentChapter = currentQuestion.chapter || quizData.chapter || '当前章节';
const sourceLabel = {
  baseline: '保底题库',
  common: '公共题库',
  personalized: '个性化题',
}[currentQuestion.source] || '题库';
```

- [ ] **Step 2: Remove hard-coded header and timer**

Replace:

```jsx
<span className="text-xl font-bold tracking-tighter text-slate-900">数据结构智慧训练</span>
```

with:

```jsx
<div>
  <p className="text-xs text-slate-400 font-bold uppercase tracking-wider">智能练习</p>
  <span className="text-xl font-bold tracking-tighter text-slate-900">{courseName}</span>
</div>
```

Replace the timer block:

```jsx
<div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex items-center gap-2">
  <span className="material-symbols-outlined text-primary">timer</span>
  <span className="font-body-md text-primary font-bold tracking-tight">18:45</span>
</div>
```

with:

```jsx
<div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 hidden md:flex items-center gap-2">
  <span className="material-symbols-outlined text-primary">school</span>
  <span className="font-body-md text-primary font-bold tracking-tight">{currentKnowledgePoint}</span>
</div>
```

- [ ] **Step 3: Replace hard-coded sidebar labels**

Replace:

```jsx
<h3 className="text-sm font-bold text-slate-900">第4章：树形结构</h3>
```

with:

```jsx
<h3 className="text-sm font-bold text-slate-900">{currentChapter}</h3>
```

Replace the entire `<nav className="flex-1 space-y-1">...</nav>` with:

```jsx
<nav className="flex-1 space-y-1">
  <div className="flex items-center gap-3 px-4 py-3 bg-white text-primary shadow-sm rounded-lg border-l-4 border-primary font-bold">
    <span className="material-symbols-outlined text-sm">quiz</span>
    <span className="font-label-sm text-xs font-medium">{currentKnowledgePoint}</span>
  </div>
  <div className="flex items-center gap-3 px-4 py-3 text-slate-500 rounded-lg">
    <span className="material-symbols-outlined text-sm">category</span>
    <span className="font-label-sm text-xs font-medium">{sourceLabel}</span>
  </div>
  <div className="flex items-center gap-3 px-4 py-3 text-slate-500 rounded-lg">
    <span className="material-symbols-outlined text-sm">format_list_numbered</span>
    <span className="font-label-sm text-xs font-medium">共 {totalQuestions} 题</span>
  </div>
</nav>
```

- [ ] **Step 4: Replace fake visualization block with metadata panel**

Replace the static visualization block at `src/pages/Quiz.jsx` with:

```jsx
<div className="w-full rounded-xl mb-8 border border-slate-200 bg-slate-50 p-4">
  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
    <div>
      <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">章节</p>
      <p className="text-slate-700 font-semibold">{currentChapter}</p>
    </div>
    <div>
      <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">知识点</p>
      <p className="text-slate-700 font-semibold">{currentKnowledgePoint}</p>
    </div>
    <div>
      <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">来源</p>
      <p className="text-slate-700 font-semibold">{sourceLabel}</p>
    </div>
  </div>
</div>
```

- [ ] **Step 5: Run frontend checks**

Run from `frontend`:

```bash
npm run lint
npm run build
```

Expected: both commands exit 0. `npm run build` may keep the existing Vite chunk size warning.

- [ ] **Step 6: Commit Quiz UI fix**

```bash
git add src/pages/Quiz.jsx
git commit -m "改造练习页通用展示"
```

---

### Task 6: Final verification and workflow update

**Files:**
- Modify: `WORKFLOW.md`

- [ ] **Step 1: Run final verification commands**

Run:

```bash
cd ../agent_service && ../.venv/bin/python -m pytest tests/test_profile_agent.py -q -p no:cacheprovider
```

Expected: PASS.

Run:

```bash
cd ../backend && TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/student_profile_loop_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_refresh_async.py -q -p no:cacheprovider
```

Expected: PASS.

Run:

```bash
cd ../backend && TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/admin_catalog_quiz_fix_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py -q -p no:cacheprovider
```

Expected: PASS.

Run:

```bash
cd ../backend && TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/learning_path_quiz_meta_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_learning_path_fallback.py::test_quiz_questions_node_id_filter_returns_node_questions -q -p no:cacheprovider
```

Expected: PASS.

Run from `frontend`:

```bash
npm run lint
npm run build
```

Expected: both commands exit 0; Vite chunk warning is acceptable if unchanged.

- [ ] **Step 2: Update workflow**

Append to `WORKFLOW.md`:

```markdown
## 2026-06-13 画像补充与练习页闭环修复

- **问题**: Backend 画像补充调用 Agent 端不存在的 `/profile/dialogue-update`；保底题 skeleton 过滤漏掉字符串数组选项；Quiz 页面仍写死数据结构课程 UI。
- **方案**: Agent Service 新增画像对话补充接口；Backend 增加路径断言和字符串模板题拒绝；Quiz API 返回题目元数据，前端练习页改用课程和题目元数据渲染。
- **验证**: 记录实际运行的 Agent、Backend、Frontend 命令和结果。
- **契约**: Client API 既有 `/profile/dialogue-update` 契约不变；Agent Service OpenAPI 新增对应内部接口；`GET /quiz/questions` 增量返回 `chapter/knowledge_point/difficulty`，不删除旧字段。
```

- [ ] **Step 3: Commit workflow**

```bash
git add WORKFLOW.md
git commit -m "记录画像和练习页闭环修复"
```

---

## Self-Review

**Spec coverage:**
- 画像疑似没补充：Task 1 补 Agent 路由，Task 2 加 Backend path 回归断言。
- fallback 模板题不应出现：Task 3 加字符串数组模板题拒绝测试和实现。
- Quiz UI 写死：Task 4 给 API 补元数据，Task 5 去掉固定数据结构 UI。
- 基础闭环验证：Task 6 汇总 Agent、Backend、Frontend 验证。

**Placeholder scan:**
- 未使用占位式待办语句。
- 每个代码修改步骤都给出目标文件和具体替换代码。
- 每个测试步骤都有命令和预期结果。

**Type consistency:**
- Agent schema 使用 `ProfileDialogueUpdateRequest/ProfileDialogueUpdateData/ProfileDialogueUpdateResponse`，API import 和测试名一致。
- Backend 继续调用 `/agent/v1/profile/dialogue-update`，与 Agent 新路由一致。
- Quiz API 字段 `chapter/knowledge_point/difficulty` 与前端 `currentQuestion.chapter/currentQuestion.knowledge_point/currentQuestion.difficulty` 一致。

**Known execution risks:**
- `../agent_service` 不在 frontend writable root；执行时如 sandbox 拒绝写入，需要按权限流程申请。
- 当前工作区已有无关 dirty 文件；执行时只 stage 本计划涉及文件，不能整仓 `git add .`。
- Agent 对话补充先采用规则解析，能支撑基础闭环；LLM 精细解析不进入本计划，避免扩大范围。
