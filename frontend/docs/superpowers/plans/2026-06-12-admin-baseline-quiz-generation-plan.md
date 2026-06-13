# Admin 批量生成保底题库 + 节点级答题 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admin 一键生成 20 节点 × 7 题保底题库，学生按节点进入答题。

**Architecture:** 在 catalogs.py 新增 `POST /admin/course-catalogs/{id}/quiz/generations`，每 KG 节点 1 个子 task 异步调 Agent 出题落库。`GET /quiz/questions` 加 `node_id` filter，LearningPath "进入练习" 带 node_id，Quiz 页面按节点过滤题目。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, React, axios

---

### Task 1: Backend — Admin 批量生成题库端点

**Files:**
- Modify: `../backend/app/api/v1/catalogs.py` (追加 ~120 行, 加 1 个 import)

- [ ] **Step 1: 加 import**

在 `from app.models.others import AsyncTask, Resource` 之后插入：
```python
from app.models.quiz import QuizQuestion
```

- [ ] **Step 2: 插入端点函数**

在 `admin_generate_catalog_resources` 之后、`list_ready_course_catalogs` 之前插入：

```python
@router.post("/admin/course-catalogs/{catalog_id}/quiz/generations", status_code=202)
async def admin_generate_catalog_quiz(
    catalog_id: str,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Admin 批量生成保底题库：遍历 active KG 全部节点，每节点调 Agent 出题落库。"""
    catalog = await _get_admin_catalog_or_404(db, catalog_id)
    if catalog.status != "ready":
        raise _course_material_missing()
    if catalog.knowledge_status not in {"ready", "partial"}:
        raise _course_material_missing()
    if (catalog.chunk_count or 0) <= 0:
        raise _knowledge_base_empty()

    offerings_result = await db.execute(
        select(CourseOffering)
        .where(
            CourseOffering.catalog_id == catalog.id,
            CourseOffering.is_deleted == False,
        )
        .order_by(CourseOffering.create_time.asc(), CourseOffering.id.asc())
    )
    offerings = offerings_result.scalars().all()
    if not offerings:
        raise _course_offering_missing()

    fanout_course_ids = [offering.id for offering in offerings]

    kg = await get_active_knowledge_graph(db, catalog.kg_host_course_id or "")
    if kg is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": 40917,
                "message": "课程知识图谱未就绪",
                "data": {"error_code": "kg_not_ready"},
            },
        )

    kg_nodes = kg.nodes if isinstance(kg.nodes, list) else []
    if not kg_nodes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": 40918,
                "message": "课程知识图谱节点为空",
                "data": {"error_code": "kg_nodes_empty"},
            },
        )

    # 重复生成前软删除旧保底题
    for cid in fanout_course_ids:
        await db.execute(
            update(QuizQuestion)
            .where(
                QuizQuestion.course_id == cid,
                QuizQuestion.source == "baseline",
                QuizQuestion.is_deleted == False,
            )
            .values(is_deleted=True)
        )

    parent = AsyncTask(
        task_type="quiz_generation",
        status="processing",
        progress=10,
        user_id=current_user.id,
        course_id=None,
        result={
            "catalog_id": catalog.id,
            "catalog_title": catalog.title,
            "fanout_course_ids": fanout_course_ids,
            "total_node_count": len(kg_nodes),
            "completed_node_count": 0,
            "failed_node_count": 0,
            "total_question_count": 0,
        },
    )
    db.add(parent)
    await db.flush()
    await db.refresh(parent)

    children: list[AsyncTask] = []
    for kg_node in kg_nodes:
        node_name = kg_node.get("name", "")
        chapter = kg_node.get("chapter", "")
        child = AsyncTask(
            task_type="quiz_generation",
            status="processing",
            progress=10,
            user_id=current_user.id,
            course_id=fanout_course_ids[0],
            result={
                "catalog_id": catalog.id,
                "parent_task_id": parent.id,
                "node_name": node_name,
                "chapter": chapter,
                "course_ids": fanout_course_ids,
            },
        )
        db.add(child)
        children.append(child)
    await db.flush()

    for child in children:
        node_name = child.result["node_name"]
        chapter = child.result["chapter"] or ""
        payload = {
            "task_id": child.id,
            "user_id": current_user.id,
            "course_id": child.course_id,
            "chapter": chapter,
            "knowledge_point": node_name,
            "question_types": [
                "single_choice", "single_choice", "single_choice",
                "multi_choice", "multi_choice", "multi_choice", "multi_choice",
            ],
            "count": 7,
            "difficulty": "medium",
            "source": "baseline",
        }
        try:
            data = await agent_client.post_json(
                "/agent/v1/assessment/generate-questions",
                payload,
            )
            questions = data.get("questions") if isinstance(data, dict) else []
            for cid in (child.result.get("course_ids") or fanout_course_ids):
                for q in (questions if isinstance(questions, list) else []):
                    async with async_session_factory() as recovery_db:
                        recovery_db.add(QuizQuestion(
                            course_id=cid,
                            chapter=chapter,
                            knowledge_point=node_name,
                            type=q.get("type", "single_choice"),
                            source="baseline",
                            personalized=False,
                            difficulty="medium",
                            content=q.get("content", ""),
                            options=q.get("options", []),
                            correct_answer=str(q.get("answer", "")),
                            explanation=q.get("explanation", ""),
                        ))
                        await recovery_db.commit()
            child.status = "completed"
            child.progress = 100
            child.completed_at = _now_utc()
            child.result = {**child.result, "question_count": len(questions) if isinstance(questions, list) else 0}
        except AgentServiceError as e:
            child.status = "failed"
            child.progress = 100
            child.error_code = str(e.agent_code or "agent_error")
            child.error_message = e.message
            child.completed_at = _now_utc()
        except Exception as e:
            child.status = "failed"
            child.progress = 100
            child.error_code = "unexpected_error"
            child.error_message = str(e)[:500]
            child.completed_at = _now_utc()

    # 汇总父任务
    completed = sum(1 for c in children if c.status == "completed")
    failed = sum(1 for c in children if c.status == "failed")
    total_qs = sum(
        (c.result.get("question_count") if isinstance(c.result, dict) else 0)
        for c in children if c.status == "completed"
    )
    parent.status = "completed" if failed == 0 else "failed"
    parent.progress = 100
    parent.completed_at = _now_utc()
    parent.result = {
        **parent.result,
        "completed_node_count": completed,
        "failed_node_count": failed,
        "total_question_count": total_qs,
    }
    await db.commit()

    return {
        "code": 202,
        "message": "accepted",
        "data": {"task_id": parent.id, "catalog_id": catalog.id, "status": "processing"},
    }
```

- [ ] **Step 3: 确认语法**

```bash
cd ../backend && python -c "from app.api.v1.catalogs import admin_generate_catalog_quiz; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
cd ../backend && git add app/api/v1/catalogs.py && git commit -m "feat: Admin 批量生成保底题库端点"
```

---

### Task 2: Backend — GET /quiz/questions 加 node_id 过滤

**Files:**
- Modify: `../backend/app/api/v1/quiz.py:37-93`

- [ ] **Step 1: 加 import**

在 `from app.services.agent_client import AgentServiceError, agent_client` 之后插入：
```python
from app.models.catalog import CourseCatalog, CourseOffering
from app.services.course_knowledge_graphs import get_active_knowledge_graph
```

- [ ] **Step 2: 修改 get_questions 函数签名加 node_id 参数**

将函数签名从：
```python
async def get_questions(
    course_id: str = Query(...),
    chapter: str = Query(None),
    knowledge_point: str = Query(None),
    type: str = Query(None),
    source: str = Query(None),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
```
改为：
```python
async def get_questions(
    course_id: str = Query(...),
    chapter: str = Query(None),
    knowledge_point: str = Query(None),
    type: str = Query(None),
    source: str = Query(None),
    node_id: str = Query(None),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
```

- [ ] **Step 3: 在 source 过滤之后、result.execute 之前追加 node_id 解析逻辑**

在 `if source:` 块之后插入：
```python
    if node_id:
        kg_node_name = node_id
        kg = await get_active_knowledge_graph(db, course_id)
        if kg is None:
            offering_result = await db.execute(
                select(CourseOffering).where(
                    CourseOffering.id == course_id,
                    CourseOffering.is_deleted == False,
                )
            )
            offering = offering_result.scalar_one_or_none()
            if offering is not None:
                catalog_result = await db.execute(
                    select(CourseCatalog).where(
                        CourseCatalog.id == offering.catalog_id,
                        CourseCatalog.is_deleted == False,
                    )
                )
                catalog = catalog_result.scalar_one_or_none()
                if catalog is not None and catalog.kg_host_course_id:
                    kg = await get_active_knowledge_graph(db, catalog.kg_host_course_id)
        if kg and kg.nodes:
            kg_nodes = kg.nodes if isinstance(kg.nodes, list) else []
            for kg_node in kg_nodes:
                if isinstance(kg_node, dict) and kg_node.get("id") == node_id:
                    kg_node_name = kg_node.get("name", node_id)
                    break
        query = query.where(QuizQuestion.knowledge_point == kg_node_name)
```

- [ ] **Step 4: 确认语法**

```bash
cd ../backend && python -c "from app.api.v1.quiz import router; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
cd ../backend && git add app/api/v1/quiz.py && git commit -m "feat: GET /quiz/questions 加 node_id 过滤"
```

---

### Task 3: Frontend — service 层

**Files:**
- Modify: `src/api/services/admin.js`
- Modify: `src/api/services/quiz.js`

- [ ] **Step 1: admin.js 加 startQuizGeneration**

```javascript
  startQuizGeneration: async (catalogId) => {
    return apiClient.post(`/admin/course-catalogs/${catalogId}/quiz/generations`);
  },
```

- [ ] **Step 2: quiz.js 支持 node_id 参数**

```javascript
getQuestions(courseId, nodeId) {
    const params = { course_id: courseId };
    if (nodeId) params.node_id = nodeId;
    return apiClient.get('/quiz/questions', { params });
},
```

- [ ] **Step 3: Commit**

```bash
git add src/api/services/admin.js src/api/services/quiz.js && git commit -m "feat: admin/quiz service 加题库生成和 node_id 支持"
```

---

### Task 4: Frontend — LearningPath "进入练习" 带 node_id

**Files:**
- Modify: `src/pages/LearningPath.jsx:303`

- [ ] **Step 1: 改链接**

Line 303 当前：
```jsx
<Link to="/quiz" className="w-full block text-center py-2 bg-blue-600 text-white rounded-lg text-sm font-bold hover:bg-blue-700 transition-colors">
```
改为：
```jsx
<Link to={`/quiz?course_id=${activeCourseId}&node_id=${selectedNodeId}`} className="w-full block text-center py-2 bg-blue-600 text-white rounded-lg text-sm font-bold hover:bg-blue-700 transition-colors">
```

`activeCourseId` 和 `selectedNodeId` 已在组件 state 中。

- [ ] **Step 2: Commit**

```bash
git add src/pages/LearningPath.jsx && git commit -m "feat: LearningPath 进入练习带 node_id"
```

---

### Task 5: Frontend — Quiz.jsx 读 URL node_id

**Files:**
- Modify: `src/pages/Quiz.jsx`

- [ ] **Step 1: 从 URL 读取 node_id 并传给 API**

加 import：
```javascript
import { useSearchParams } from 'react-router-dom';
```

在组件开始处（after hooks declarations）取出 node_id：
```javascript
const [searchParams] = useSearchParams();
const nodeId = searchParams.get('node_id');
```

改 fetchQuestions 调用（line 20）：
```javascript
const res = await quizService.getQuestions(activeCourseId, nodeId || undefined);
```

- [ ] **Step 2: Commit**

```bash
git add src/pages/Quiz.jsx && git commit -m "feat: Quiz 页面支持 node_id 节点模式答题"
```

---

### Task 6: Frontend — CourseCatalogDrawer "生成题库" 按钮

**Files:**
- Modify: `src/components/admin/CourseCatalogDrawer.jsx`

- [ ] **Step 1: 加 state 和 handler**

在 state 区域追加：
```javascript
const [quizGenerating, setQuizGenerating] = useState(false);
const [quizGenTask, setQuizGenTask] = useState(null);
const quizGenTaskRef = useRef(null);
```

加 handler：
```javascript
const handleStartQuizGeneration = useCallback(async () => {
    if (!catalog || quizGenerating) return;
    setQuizGenerating(true);
    setQuizGenTask(null);
    try {
      const res = await adminService.startQuizGeneration(catalog.id);
      if (res.code === 202) {
        setQuizGenTask({ task_id: res.data.task_id, status: 'processing', progress: 10 });
        quizGenTaskRef.current = { task_id: res.data.task_id, status: 'processing' };
      }
    } catch (err) {
      console.error('Failed to start quiz generation:', err);
      setQuizGenerating(false);
    }
}, [catalog, quizGenerating]);
```

加轮询 effect：
```javascript
useEffect(() => {
    if (!quizGenTask?.task_id || quizGenTask.status === 'completed' || quizGenTask.status === 'failed') return;
    let active = true;
    const poll = async () => {
      try {
        const res = await taskService.getTaskStatus(quizGenTask.task_id);
        const task = normalizeTask(res.data, quizGenTask.task_id, 'quiz_generation');
        if (!active) return;
        quizGenTaskRef.current = task;
        setQuizGenTask(task);
        if (task.status === 'completed' || task.status === 'failed') {
          setQuizGenerating(false);
          if (onChanged) onChanged();
        }
      } catch (err) {
        if (active) setQuizGenerating(false);
      }
    };
    const timer = setInterval(poll, 2000);
    return () => { active = false; clearInterval(timer); };
}, [quizGenTask?.task_id, quizGenTask?.status, onChanged]);
```

- [ ] **Step 2: 加 UI（在"生成学习资源"区域下方）**

追加：
```jsx
            <div className="my-6 border-t border-slate-200" />

            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-sm font-bold text-slate-900">生成保底题库</h3>
                <p className="mt-1 text-xs text-slate-500">按 KG 全部节点生成保底题库（每节点 3 单选 + 4 多选）。</p>
              </div>
              <button
                type="button"
                onClick={handleStartQuizGeneration}
                disabled={quizGenerating || !hasReadyKnowledge || !hasActiveKnowledgeGraph}
                className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  quizGenerating || !hasReadyKnowledge || !hasActiveKnowledgeGraph
                    ? 'cursor-not-allowed bg-slate-100 text-slate-400'
                    : 'cursor-pointer bg-emerald-600 text-white hover:bg-emerald-700'
                }`}
              >
                <span className={`material-symbols-outlined text-[18px] ${quizGenerating ? 'animate-spin' : ''}`}>
                  {quizGenerating ? 'progress_activity' : 'quiz'}
                </span>
                {quizGenerating ? '生成中' : '生成题库'}
              </button>
            </div>

            {(quizGenTask?.status === 'processing' || quizGenTask?.status === 'completed' || quizGenTask?.status === 'failed') && (
              <div className="mt-3 rounded-lg bg-slate-50 p-3 text-sm">
                <div className="flex items-center gap-2">
                  <span className={`inline-flex h-2 w-2 rounded-full ${
                    quizGenTask.status === 'completed' ? 'bg-emerald-500' :
                    quizGenTask.status === 'failed' ? 'bg-red-500' : 'bg-amber-500 animate-pulse'
                  }`}></span>
                  <span className="text-xs text-slate-700 font-medium">
                    题库生成 {quizGenTask.status === 'completed' ? '完成' : quizGenTask.status === 'failed' ? '失败' : '进行中'}
                    {quizGenTask.status === 'completed' && quizGenTask.result?.total_question_count
                      ? `（${quizGenTask.result.completed_node_count}/${quizGenTask.result.total_node_count} 节点，共 ${quizGenTask.result.total_question_count} 题）`
                      : ''}
                  </span>
                </div>
                {quizGenTask.status === 'failed' && quizGenTask.error_message && (
                  <div className="mt-2 text-xs text-red-600">{quizGenTask.error_message}</div>
                )}
              </div>
            )}
```

- [ ] **Step 3: Commit**

```bash
git add src/components/admin/CourseCatalogDrawer.jsx && git commit -m "feat: CourseCatalogDrawer 加生成保底题库按钮"
```

---

### Task 7: 集成测试

**Files:**
- Modify: `../backend/tests/test_learning_path_fallback.py`

- [ ] **Step 1: 追加 quiz node_id 过滤测试**

```python
@pytest.mark.asyncio
async def test_quiz_questions_node_id_filter_returns_node_questions():
    """GET /quiz/questions?node_id=xxx should return only that node's questions."""
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        suffix = uuid.uuid4().hex[:8]
        reg_code = f"qzfb_{suffix}"
        email = f"qznode_{suffix[:6]}@t.com"
        username = f"qznode_{suffix[:6]}"

        async with async_session_factory() as db:
            db.add(RegistrationCode(code=reg_code, role="student"))
            await db.commit()

        ct_token, ct_ans = await _captcha_answer(client)
        r = await client.post("/api/v1/auth/register", json={
            "registration_code": reg_code, "email": email, "password": "Abc12345",
            "username": username, "captcha_token": ct_token, "captcha_code": ct_ans,
        })
        assert r.status_code == 201

        ct_token, ct_ans = await _captcha_answer(client)
        r = await client.post("/api/v1/auth/login", json={
            "email": email, "password": "Abc12345",
            "captcha_token": ct_token, "captcha_code": ct_ans,
        })
        headers = {"Authorization": f"Bearer {r.json()['data']['token']}"}

        catalog_id = f"qzcat_{suffix[:8]}"
        host_course_id = f"qzhc_{suffix[:8]}"
        course_id = f"qzco_{suffix[:8]}"

        async with async_session_factory() as db:
            db.add(CourseCatalog(id=catalog_id, title="QZ Catalog", kg_host_course_id=host_course_id))
            db.add(CourseOffering(id=course_id, name="QZ Class", catalog_id=catalog_id,
                                  teacher_id=r.json()["data"].get("user_id", ""), class_code=f"QZ{suffix[:4].upper()}"))
            await db.flush()
            db.add(CourseKnowledgeGraph(course_id=host_course_id, version=1, is_active=True,
                source_type="catalog_chunks", generation_strategy="catalog_chunks_llm",
                nodes=[{"id":"n1","name":"Node1","chapter":"Ch1"}],
                edges=[]))
            db.add(QuizQuestion(course_id=course_id, chapter="Ch1", knowledge_point="Node1",
                type="single_choice", source="baseline", content="Q1 for Node1",
                correct_answer="A", options={"A":"x","B":"y"}))
            db.add(QuizQuestion(course_id=course_id, chapter="Ch1", knowledge_point="OtherNode",
                type="single_choice", source="baseline", content="Q2 for Other",
                correct_answer="B", options={"A":"x","B":"y"}))
            await db.commit()

        r = await client.get(f"/api/v1/quiz/questions?course_id={course_id}&node_id=n1", headers=headers)
        assert r.status_code == 200
        questions = r.json()["data"]["questions"]
        assert len(questions) == 1
        assert questions[0]["content"] == "Q1 for Node1"
```

- [ ] **Step 2: 运行测试**

```bash
cd ../backend && python -m pytest tests/test_learning_path_fallback.py -v
```

- [ ] **Step 3: Commit**

```bash
cd ../backend && git add tests/test_learning_path_fallback.py && git commit -m "test: quiz node_id 过滤集成测试"
```

---

### Task 8: 文档更新

**Files:**
- Modify: `WORKFLOW.md`
- Modify: `docs/feature-ledger.md`

- [ ] **Step 1: 更新 WORKFLOW.md 和 feature-ledger.md**

追加施工记录并更新 Quiz 相关条目状态。

- [ ] **Step 2: Commit**

```bash
git add WORKFLOW.md docs/feature-ledger.md && git commit -m "docs: 记录 Admin 批量生成保底题库进度"
```
