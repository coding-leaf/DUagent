# 个性化错题购物车 (Personalized Quiz Cart) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 允许用户在“个性化资源”页面按知识点勾选多道错题，并携带 `question_ids` 组合成一次练习任务发起测试。

**Architecture:** 
- 后端 `/api/v1/quiz/questions` 新增可选参数 `question_ids`，如果传入则按 `id` 过滤并忽略 `limit`。
- 前端 `PersonalizedResources.jsx` 改用带复选框的可展开卡片列表，维护选中题目 ID 数组，跳转带参数。
- 前端 `Quiz.jsx` 提取 `question_ids` URL 参数，透传给请求组卷。

**Tech Stack:** React, TailwindCSS, FastAPI, SQLAlchemy

---

### Task 1: Backend `get_questions` Endpoint Modification

**Files:**
- Modify: `backend/app/api/v1/quiz.py`

- [ ] **Step 1: Write minimal implementation**

在 `backend/app/api/v1/quiz.py` 中的 `get_questions` 路由函数里，新增 `question_ids: str = Query(None)` 参数，并处理过滤与 limit：

```python
@router.get("/questions")
async def get_questions(
    course_id: str = Query(...),
    chapter: str = Query(None),
    knowledge_point: str = Query(None),
    type: str = Query(None),
    source: str = Query(None),
    node_id: str = Query(None),
    question_ids: str = Query(None),  # 新增
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = await resolve_course_resource_scope(db, course_id)
    query = select(QuizQuestion).where(
        or_(
            and_(QuizQuestion.catalog_id.is_(None), QuizQuestion.course_id == course_id),
            QuizQuestion.catalog_id == scope.catalog_id,
        ),
        QuizQuestion.is_deleted == False,
        (QuizQuestion.source.in_(["common", "baseline"]))
        | ((QuizQuestion.source == "personalized") & (QuizQuestion.owner_user_id == current_user.id)),
    )
    
    if question_ids:
        # 如果传入了具体的题目 ID，直接过滤，忽略其它条件（或者保留基础过滤），并忽略 limit
        ids_list = [qid.strip() for qid in question_ids.split(",") if qid.strip()]
        if ids_list:
            query = query.where(QuizQuestion.id.in_(ids_list))
    else:
        # 原有的条件过滤和 limit 仅在没有明确 question_ids 时生效
        if chapter:
            query = query.where(QuizQuestion.chapter == chapter)
        if knowledge_point:
            query = query.where(QuizQuestion.knowledge_point == knowledge_point)
        if type:
            query = query.where(QuizQuestion.type == type)
        if source:
            query = query.where(QuizQuestion.source == source)

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

        query = query.limit(limit)

    result = await db.execute(query)
    questions = result.scalars().all()
    # ... 后续组卷逻辑不变 ...
```
*(注意：需要根据实际文件原本逻辑精准替换，保持外层 `select` 及 `quiz_session` 创建等逻辑不变)*

- [ ] **Step 2: Run syntax check**

```bash
cd backend && python3 -m py_compile app/api/v1/quiz.py
```
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/v1/quiz.py
git commit -m "feat(backend): add question_ids parameter to get_questions endpoint to support specific question selection"
```

---

### Task 2: Frontend `Quiz.jsx` URL Param handling

**Files:**
- Modify: `frontend/src/pages/Quiz.jsx`

- [ ] **Step 1: Write minimal implementation**

在 `frontend/src/pages/Quiz.jsx` 中，解析 `question_ids` 并传递给 `extraParams`。

```javascript
  const [searchParams] = useSearchParams();
  const nodeId = searchParams.get('node_id');
  const sourceParam = searchParams.get('source');
  const knowledgePointParam = searchParams.get('knowledge_point');
  const questionIdsParam = searchParams.get('question_ids'); // 新增

  useEffect(() => {
    const fetchQuestions = async () => {
      if (!activeCourseId) return;
      try {
        setLoading(true);
        setCurrentQuestionIndex(0);
        setAnswers({});
        const extraParams = {};
        if (sourceParam) extraParams.source = sourceParam;
        if (knowledgePointParam) extraParams.knowledge_point = knowledgePointParam;
        if (questionIdsParam) extraParams.question_ids = questionIdsParam; // 新增
        const res = await quizService.getQuestions(activeCourseId, nodeId || undefined, extraParams);
```

- [ ] **Step 2: Run linter**

```bash
npm run lint -- src/pages/Quiz.jsx
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/pages/Quiz.jsx
git commit -m "feat(frontend): extract question_ids from URL and pass to quizService in Quiz page"
```

---

### Task 3: Frontend `PersonalizedResources.jsx` UI and Logic

**Files:**
- Modify: `frontend/src/pages/PersonalizedResources.jsx`

- [ ] **Step 1: Write implementation for `QuizGroupCard`**

修改 `PersonalizedResources.jsx`。我们需要引入展开状态 `isExpanded`，内部题目列表，以及选中的 ID 管理。为了减少顶层状态重新渲染的负担，最好将这些封装到 `QuizGroupCard` 组件内部，但需要注意跳转 URL 的构造。

```javascript
function QuizGroupCard({ kp, kpItems, courseId, navigate }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedIds, setSelectedIds] = useState([]);
  
  const count = kpItems.length;
  // 仅筛选出有效的题目的 items
  const validQuestionItems = kpItems.filter(i => i.question);
  
  const handleToggleSelectAll = (e) => {
    e.stopPropagation();
    if (selectedIds.length === validQuestionItems.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(validQuestionItems.map(i => i.question.id));
    }
  };

  const handleToggleItem = (id) => {
    setSelectedIds(prev => 
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const handleStartPractice = (e) => {
    e.stopPropagation();
    if (selectedIds.length === 0) {
      // 未勾选任何题目：维持原有逻辑
      navigate(`/quiz?course_id=${courseId}&source=personalized&knowledge_point=${encodeURIComponent(kp)}`);
    } else {
      // 勾选了具体题目
      navigate(`/quiz?course_id=${courseId}&question_ids=${selectedIds.join(',')}`);
    }
  };

  return (
    <div className="bg-white border border-outline-variant rounded-xl overflow-hidden hover:shadow-sm transition-shadow">
      {/* Header */}
      <div 
        className="p-4 flex items-center justify-between gap-4 bg-slate-50 cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-full bg-primary-container/10 flex items-center justify-center text-primary-container flex-shrink-0">
            <span className="material-symbols-outlined">quiz</span>
          </div>
          <div className="min-w-0">
            <h3 className="text-body-md font-bold text-slate-800">{kp}</h3>
            <p className="text-label-sm text-slate-500 mt-1">共 {count} 道个性化题目</p>
          </div>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <button
            onClick={handleStartPractice}
            className="flex items-center gap-1.5 px-4 py-2 bg-primary-container text-white rounded-xl text-label-sm font-bold hover:brightness-110 active:scale-95 transition-all"
          >
            <span className="material-symbols-outlined text-[16px]">play_arrow</span>
            开始练习 {selectedIds.length > 0 ? `(已选 ${selectedIds.length})` : ''}
          </button>
          <span className="material-symbols-outlined text-slate-400">
            {isExpanded ? 'expand_less' : 'expand_more'}
          </span>
        </div>
      </div>

      {/* Expanded Content */}
      {isExpanded && validQuestionItems.length > 0 && (
        <div className="border-t border-slate-200">
          {/* Toolbar */}
          <div className="px-4 py-2 bg-slate-100 border-b border-slate-200 flex justify-between items-center text-xs">
            <label className="flex items-center gap-2 cursor-pointer text-slate-700 font-medium hover:text-primary">
              <input 
                type="checkbox" 
                className="rounded border-slate-300 text-primary focus:ring-primary cursor-pointer w-4 h-4"
                checked={selectedIds.length === validQuestionItems.length && validQuestionItems.length > 0}
                onChange={handleToggleSelectAll}
              />
              全选本知识点下的 {validQuestionItems.length} 题
            </label>
            <span className="text-slate-500">按最近生成时间排列</span>
          </div>

          {/* Scrollable List */}
          <div className="max-h-[320px] overflow-y-auto">
            {validQuestionItems.map((item, idx) => {
              const q = item.question;
              const isSelected = selectedIds.includes(q.id);
              // 截断内容作为摘要
              const summary = q.content.length > 50 ? q.content.substring(0, 50) + '...' : q.content;
              const diffLabel = { easy: '简单', medium: '中等', hard: '困难' }[q.difficulty] || q.difficulty;
              const sourceLabel = SOURCE_LABEL[item.source_type] || item.source_type;

              return (
                <div 
                  key={q.id} 
                  className={`p-3 border-b border-slate-100 flex items-start gap-3 transition-colors ${isSelected ? 'bg-sky-50/50' : 'hover:bg-slate-50'}`}
                >
                  <input 
                    type="checkbox" 
                    className="mt-1 rounded border-slate-300 text-primary focus:ring-primary cursor-pointer w-4 h-4"
                    checked={isSelected}
                    onChange={() => handleToggleItem(q.id)}
                  />
                  <div className="flex-1 min-w-0" onClick={() => handleToggleItem(q.id)} style={{ cursor: 'pointer' }}>
                    <div className="flex gap-2 items-center mb-1">
                      <span className="text-[10px] bg-red-100 text-red-600 px-1.5 py-0.5 rounded">{sourceLabel}</span>
                      <span className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">难度: {diffLabel}</span>
                    </div>
                    <p className="text-sm font-medium text-slate-800 break-words">{summary}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Run linter and build check**

```bash
npm run lint -- src/pages/PersonalizedResources.jsx
npm run build
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/pages/PersonalizedResources.jsx
git commit -m "feat(frontend): refactor QuizGroupCard to support specific question selection cart"
```
