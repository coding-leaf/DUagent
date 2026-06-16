# 个性化资源功能 — 详细设计 spec

**日期：** 2026-06-16  
**方案：** B（错题上下文增强 + 手动引导生成，独立页面）  
**状态：** 待实现  

---

## 0. 目标与约束

### 目标
为学生提供两条个性化资源生成路径：
1. **被动触发**：答题完成后正确率 < 60%，系统提示并自动基于错题生成针对性练习题，后台异步生成，前端跳转个性化资源页等待
2. **主动生成**：学生在"个性化资源"页面主动触发，引导式表单选章节 → 知识点 → 资源类型，按 admin 生成逻辑执行

所有个性化资源（题目 + 其他类型）均归属于 `(user_id, course_id)`，独立存储，与公共资源隔离。

### 约束（来自 CLAUDE.md）
- 最小修改原则，跨 3+ 文件时先与用户确认
- 不允许 mock 数据；不修改 `.env`；不切换 git 分支
- 改动接口同步修改前后端对应调用点，在 `WORKFLOW.md` 记录漂移
- 大改（涉及数据结构）须先出 spec 走设计流程 ← 本文档即是

---

## 1. 功能范围概览

| 路径 | 触发 | 生成内容 | Agent 接口 |
|------|------|---------|-----------|
| 错题触发（PracticeResult → 个性化页） | 正确率 < 60% 弹提示 | 个性化练习题（quiz） | 复用 `POST /agent/v1/assessment/generate-questions`，传入 `personalization_context.wrong_questions` |
| 手动生成（个性化资源页引导表单） | 用户点击"生成资源" | document/mindmap/reading/code/video/quiz 任选 | 资源类：复用 `POST /agent/v1/resources/generate`；题目类：复用 `POST /agent/v1/assessment/generate-questions` |

---

## 2. 数据库层

### 2.1 新建表：`user_personalized_resources`

```sql
CREATE TABLE user_personalized_resources (
    id          VARCHAR(32)  PRIMARY KEY,
    user_id     VARCHAR(32)  NOT NULL REFERENCES users(id),
    course_id   VARCHAR(32)  NOT NULL REFERENCES courses(id),
    resource_id VARCHAR(32)  NULL REFERENCES resources(id),      -- 资源类型时非NULL
    question_id VARCHAR(32)  NULL REFERENCES quiz_questions(id),-- 题目类型时非NULL
    source_type VARCHAR(30)  NOT NULL,  -- 'quiz_wrong_answer' | 'manual'
    task_id     VARCHAR(32)  NULL REFERENCES async_tasks(id),   -- 生成来源任务
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted  BOOLEAN      NOT NULL DEFAULT FALSE,

    INDEX idx_upr_user_course (user_id, course_id, is_deleted),
    INDEX idx_upr_task (task_id)
);
```

**字段说明：**
- `resource_id` 和 `question_id` 二选一：资源类填 resource_id，题目类填 question_id
- `source_type`：区分触发来源，前端可按此筛选展示
- `task_id`：关联 `async_tasks` 表，可通过 task 状态判断是否生成中

**与现有表关系：**
- 不修改 `resources` 表（无 owner 字段概念）
- 不修改 `quiz_questions` 表（已有 `personalized=True` + `owner_user_id`）
- `async_tasks` 表无需改动，直接关联

### 2.2 新增 SQLAlchemy Model

**文件：** `backend/app/models/others.py`（追加在现有 Model 后）

```python
class UserPersonalizedResource(Base):
    __tablename__ = "user_personalized_resources"
    __table_args__ = (
        Index("idx_upr_user_course", "user_id", "course_id", "is_deleted"),
        Index("idx_upr_task", "task_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    course_id: Mapped[str] = mapped_column(String(32), ForeignKey("courses.id"), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("resources.id"), nullable=True)
    question_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("quiz_questions.id"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("async_tasks.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
```

### 2.3 数据库迁移

需执行 `CREATE TABLE` DDL。本项目使用 `alembic` 或手动执行——由实现时确认方式（见 WORKFLOW.md 记录）。

---

## 3. 后端 API

### 3.1 新增接口：`GET /api/v1/personalized-resources`

列出当前用户在指定课程下的个性化资源。

**权限：** `get_current_user`（任意已登录用户）

**请求参数（Query）：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|-----|------|
| course_id | str | 是 | 课程 ID |
| source_type | str | 否 | 'quiz_wrong_answer' \| 'manual'，不传返回全部 |
| page | int | 否 | 默认 1 |
| page_size | int | 否 | 默认 20，最大 50 |

**响应体：**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "upr_id",
        "source_type": "quiz_wrong_answer",
        "created_at": "ISO8601",
        "task_id": "task_id_or_null",
        "task_status": "processing|completed|failed|null",
        "resource": {               // resource_id 非 null 时
          "id": "resource_id",
          "title": "...",
          "type": "document|mindmap|reading|code|video",
          "description": "...",
          "chapter": "...",
          "knowledge_point": "..."
        },
        "question": {               // question_id 非 null 时
          "id": "question_id",
          "type": "single_choice|multi_choice|code|short_answer",
          "content": "...",
          "options": [],
          "knowledge_point": "...",
          "chapter": "...",
          "difficulty": "easy|medium|hard"
        }
      }
    ],
    "total": 42,
    "page": 1,
    "page_size": 20,
    "processing_count": 2   // 仍在生成中的任务数，前端据此决定是否轮询
  }
}
```

**实现要点：**
- JOIN `user_personalized_resources` → 按需 LEFT JOIN `resources` + `quiz_questions` + `async_tasks`
- `task_status` 字段：若 `task_id` 非 null，直接从 JOIN 的 `async_tasks.status` 取；否则 null
- `processing_count`：统计 `task_id` 非null 且 `async_tasks.status='processing'` 的行数

### 3.2 新增接口：`POST /api/v1/personalized-resources/generate`

触发生成个性化资源（资源类或题目类均走此接口）。

**权限：** `get_current_user`（任意已登录用户）

**请求体 Schema（新建 `backend/app/schemas/personalized.py`）：**

```python
class PersonalizedResourceGenerateRequest(BaseModel):
    course_id: str
    generate_type: Literal["quiz", "resource"]   # 区分题目生成 vs 资源生成
    source_type: Literal["quiz_wrong_answer", "manual"]

    # 以下字段 quiz 和 resource 共用
    chapter: Optional[str] = None
    knowledge_point: Optional[str] = None

    # quiz 专用
    wrong_question_ids: Optional[list[str]] = None  # 错题 ID 列表，source_type='quiz_wrong_answer' 时传入
    question_types: Optional[list[str]] = None
    count: int = 5
    difficulty: Optional[str] = None

    # resource 专用
    resource_types: Optional[list[str]] = None
```

**响应体：**
```json
{
  "code": 202,
  "message": "accepted",
  "data": {
    "task_id": "xxx",
    "generate_type": "quiz"
  }
}
```

**实现逻辑（`backend/app/api/v1/personalized_resources.py`，新文件）：**

```
1. 解析 req.generate_type
2. resolve_generation_catalog(db, req.course_id) 得到 catalog_context
3. 创建 AsyncTask（task_type: "quiz_generation" 或 "resource_generation"）
4. 组装 Agent payload：
   - quiz: 调用 quiz_service.assemble_generate_payload()，
           若 wrong_question_ids 非空则额外查询这些题目的 knowledge_point 和 content，
           写入 personalization_context.wrong_questions = [{"id":..., "content":..., "knowledge_point":...}]
   - resource: 直接组装 resource generate payload（复用 resources.py 的 _webhook_url 逻辑）
5. 调用 Agent:
   - quiz: agent_client.post_json("/agent/v1/assessment/generate-questions", payload)
   - resource: agent_client.post_json("/agent/v1/resources/generate", payload)
6. 同步写入 user_personalized_resources 行（status pending，无 resource_id/question_id，仅 task_id）
   - 等 Webhook 回调时补全 resource_id/question_id
7. 返回 202
```

**错题查询（步骤 4 quiz 路径）：**

若 `wrong_question_ids` 非空：
```python
wrong_r = await db.execute(
    select(QuizQuestion.id, QuizQuestion.content, QuizQuestion.knowledge_point, QuizQuestion.chapter)
    .where(
        QuizQuestion.id.in_(wrong_question_ids),
        QuizQuestion.is_deleted == False,
    )
)
wrong_questions_context = [
    {"id": r.id, "content": r.content, "knowledge_point": r.knowledge_point}
    for r in wrong_r.all()
]
ctx["wrong_questions"] = wrong_questions_context
```

这比 assemble_generate_payload 的历史错题查询更精准——直接传本次答错的题目内容，Agent 的 `build_question_generation_user_message` 已在 `personalization_context` 中处理 `wrong_points`，此字段 key 改为 `wrong_questions` 即可，格式兼容（list of dict）。

> **Agent 侧无需改动**：`agent_service/prompts/assessment.py:144` 已处理 `context.get("wrong_points")`，将 `wrong_questions` 作为 `wrong_points` 的补充字段传入即可，或在 Backend 中将 key 统一命名为 `wrong_points`（推荐），格式为 `[{"name": kp, "content": q_content}]`。

### 3.3 Webhook 扩展：写入 `user_personalized_resources`

**文件：** `backend/app/api/v1/webhooks.py`

**修改点：** 在 `agent_webhook` 处理 `resource_generation` completed 路径后，检查关联的 task 是否有对应的 `user_personalized_resources` 行（`task_id=task.id`），若有则更新 `resource_id`。

```python
# 在写完 Resource 对象、flush 后，补全 user_personalized_resources
upr_result = await db.execute(
    select(UserPersonalizedResource).where(
        UserPersonalizedResource.task_id == task.id,
        UserPersonalizedResource.is_deleted == False,
    )
)
upr = upr_result.scalar_one_or_none()
if upr:
    for resource in newly_created_resources:
        upr.resource_id = resource.id   # 若多资源，逐条插入新行
```

**题目生成无需 webhook**：quiz_generation 已同步写入 `quiz_questions`（`POST /quiz/generate` 路径），在 personalized_resources.py 步骤 6 的 task 完成后直接在同一个事务内写 `user_personalized_resources`（`question_id=new_q.id`）。

> 注：当前 `POST /quiz/generate` 是同步等待 Agent 返回并写库的（不走 Webhook），所以题目生成可以在 `personalized_resources.py` 的 generate 接口中同步拿到 question_ids，直接写关联表。

### 3.4 新增路由注册

**文件：** `backend/app/api/v1/__init__.py` 或路由聚合文件

新增 `personalized_resources.py` 的 router 注册。

### 3.5 资源生成权限修改（重要）

**文件：** `backend/app/api/v1/resources.py:131`

当前 `POST /resources/generate` 权限为 `require_role("teacher")`，学生无法调用。  
但个性化资源生成走新的 `POST /api/v1/personalized-resources/generate` 接口，不调用此接口。  
**因此不需要修改现有 resources.py 的权限。** 新接口自带 `get_current_user`（学生可用）。

---

## 4. 前端层

### 4.1 新增 API Service：`src/api/services/personalizedResources.js`

```js
import apiClient from '../client';

export const personalizedResourcesService = {
  list(courseId, params = {}) {
    return apiClient.get('/personalized-resources', { params: { course_id: courseId, ...params } });
  },
  generate(data) {
    return apiClient.post('/personalized-resources/generate', data);
  },
};
```

### 4.2 修改 PracticeResult.jsx — 错题触发提示

**触发条件：** `accuracy < 60`（accuracy 已在文件第 51 行计算）

**位置：** Modal Footer（第 172 行 `px-xl py-lg` div 内），在现有两个按钮之后，条件渲染。

**新增 UI 元素：**

```jsx
{accuracy < 60 && resultData?.per_question_results && (
  <WrongAnswerPromptBanner
    wrongQuestionIds={
      resultData.per_question_results
        .filter(q => !q.is_correct)
        .map(q => q.question_id)
    }
    courseId={activeCourseId}
    onGenerated={(taskId) => navigate('/personalized-resources', { state: { newTaskId: taskId } })}
  />
)}
```

**WrongAnswerPromptBanner 组件逻辑（内联或抽取为组件）：**

```
State: generating=false, error=null

UI:
- 黄色/橙色提示横幅："检测到本次正确率较低，是否生成针对错误题目的个性化练习？"
- 按钮"生成针对性练习"（disabled when generating）
- 点击后：
  1. setGenerating(true)
  2. 调用 personalizedResourcesService.generate({
       course_id: courseId,
       generate_type: "quiz",
       source_type: "quiz_wrong_answer",
       wrong_question_ids: wrongQuestionIds,
       count: 5,
     })
  3. 成功（202）→ onGenerated(res.data.task_id)，即 navigate 到个性化资源页
  4. 失败 → setError(msg)，显示错误，不跳转
```

**注意：** `per_question_results[i].question_id` 来自已有 submit 响应，确认字段名匹配（当前 PracticeResult.jsx:151 用 `q.question_id`，与 quiz_questions.id 对应）。

### 4.3 新增页面：`src/pages/PersonalizedResources.jsx`

**路由：** `/personalized-resources`（在 `App.jsx` 中注册，加 `<ProtectedRoute>`）

**页面结构：**

```
<Navbar />
<Sidebar />
<main>
  ┌─────────────────────────────────────────────────────┐
  │  个性化资源                         [+ 生成资源按钮]  │
  │  ─────────────────────────────────────────────────  │
  │  [筛选: 全部 | 练习题 | 学习资源]   [来源: 全部|错题触发|手动生成] │
  │                                                     │
  │  ┌──────────────────────────────────────────────┐  │
  │  │ 🔄 生成中... (如有 processing 任务时展示)        │  │
  │  └──────────────────────────────────────────────┘  │
  │                                                     │
  │  [ResourceCard 列表]                               │
  │  ...                                               │
  └─────────────────────────────────────────────────────┘
</main>

[GenerateModal 弹窗，点击"生成资源"时显示]
```

**State 设计：**

```js
const [items, setItems] = useState([]);
const [loading, setLoading] = useState(true);
const [processingCount, setProcessingCount] = useState(0);
const [filterType, setFilterType] = useState('all');       // 'all'|'quiz'|'resource'
const [filterSource, setFilterSource] = useState('all');   // 'all'|'quiz_wrong_answer'|'manual'
const [showGenerateModal, setShowGenerateModal] = useState(false);
const [page, setPage] = useState(1);
const [total, setTotal] = useState(0);
```

**轮询策略：**

- 若 `processingCount > 0`，每 3 秒自动 `fetchItems()`（useEffect + setInterval）
- 清理：当 `processingCount === 0` 时 clearInterval
- 进入页面时若 `location.state?.newTaskId` 存在，立即拉一次，并在 UI 顶部高亮"正在为你生成练习..."卡片

**fetchItems 实现：**

```js
const fetchItems = async () => {
  const res = await personalizedResourcesService.list(activeCourseId, {
    page,
    page_size: 20,
    ...(filterSource !== 'all' ? { source_type: filterSource } : {}),
  });
  if (res.code === 200) {
    setItems(res.data.items);
    setTotal(res.data.total);
    setProcessingCount(res.data.processing_count);
  }
};
```

**ResourceCard 子组件：**

每张卡片根据 item 类型渲染：
- `item.question` 存在 → 题目卡（显示知识点、题型、难度、题目内容前 80 字）
  - 点击 → 跳转到 `/quiz?course_id=xxx&question_id=xxx`（或详情弹窗，待定）
- `item.resource` 存在 → 资源卡（复用 Dashboard 资源卡样式，显示类型图标、标题、描述、知识点）
  - 点击 → `<Link to="/resource/${item.resource.id}">`
- `item.task_status === 'processing'` → 骨架加载卡（带动画）
- `item.task_status === 'failed'` → 错误卡（显示"生成失败，可重新尝试"）

### 4.4 GenerateModal 组件（引导式表单）

**文件：** `src/components/personalized/GenerateModal.jsx`（新建目录）

**三步引导流程：**

```
Step 1: 选章节
  - 从 learningPath.nodes 中提取 distinct chapter 列表
  - 渲染为可点击的选项卡（或 Select 下拉）
  - 用户选择 → 进入 Step 2

Step 2: 选知识点
  - 根据 Step 1 选的 chapter，从 learningPath.nodes 过滤 name（即 KG 节点名，等同于 knowledge_point）
  - 渲染为标签列表，可多选（多个知识点时，逐个生成或合并生成取决于用户选择数量）
  - 用户选择 → 进入 Step 3

Step 3: 选资源类型
  - 两组：
    * 练习题：单选题、多选题、代码题、问答题（对应 question_types）
    * 学习资源：文档、思维导图、阅读材料、代码示例、视频（对应 resource_types）
  - 至少选一个
  - [确认生成] 按钮

State:
  step: 1 | 2 | 3
  chapter: string | null
  knowledgePoints: string[]
  resourceTypes: string[]   // 资源类型
  questionTypes: string[]   // 题目类型
  generating: boolean
  error: string | null
```

**数据来源：**

章节和知识点从 `learningService.getLearningPath(courseId)` 的 nodes 中获取：
```js
const chapters = [...new Set(nodes.map(n => n.chapter).filter(Boolean))];
const kpsByChapter = nodes
  .filter(n => n.chapter === selectedChapter)
  .map(n => ({ id: n.id, name: n.name }));
```

**提交逻辑：**

```js
const handleSubmit = async () => {
  setGenerating(true);
  const promises = [];

  // 若有 questionTypes 选择
  if (questionTypes.length > 0) {
    promises.push(
      personalizedResourcesService.generate({
        course_id: courseId,
        generate_type: "quiz",
        source_type: "manual",
        chapter: selectedChapter,
        knowledge_point: knowledgePoints[0],  // 每次一个知识点
        question_types: questionTypes,
        count: 5,
      })
    );
  }

  // 若有 resourceTypes 选择
  if (resourceTypes.length > 0) {
    promises.push(
      personalizedResourcesService.generate({
        course_id: courseId,
        generate_type: "resource",
        source_type: "manual",
        chapter: selectedChapter,
        knowledge_point: knowledgePoints[0],
        resource_types: resourceTypes,
      })
    );
  }

  await Promise.allSettled(promises);
  setShowGenerateModal(false);
  fetchItems();  // 刷新列表，processing 状态卡片会立即出现
};
```

### 4.5 Sidebar 修改

**文件：** `src/components/Sidebar.jsx`

在现有导航列表中追加一项：

```jsx
{ path: '/personalized-resources', label: '个性化资源', icon: 'psychology' }
```

图标：`psychology`（Google Material Symbols，契合 AI 个性化语义）

### 4.6 App.jsx 路由注册

```jsx
<Route path="/personalized-resources" element={
  <ProtectedRoute>
    <PersonalizedResources />
  </ProtectedRoute>
} />
```

---

## 5. 数据流全图

### 5.1 错题触发路径

```
用户完成答题 → PracticeResult.jsx
  └─ accuracy < 60%
       └─ 展示 WrongAnswerPromptBanner
            └─ 用户点击"生成针对性练习"
                 └─ POST /api/v1/personalized-resources/generate
                      { generate_type: "quiz", source_type: "quiz_wrong_answer",
                        wrong_question_ids: [...] }
                      │
                      ├─ Backend: 查询错题 content + knowledge_point
                      ├─ 组装 personalized_context.wrong_points = [{name, content}]
                      ├─ 调用 Agent /assessment/generate-questions（同步等待）
                      ├─ Agent 返回 questions → 写入 quiz_questions（personalized=True）
                      ├─ 写入 user_personalized_resources（source_type="quiz_wrong_answer"）
                      └─ 返回 202 {task_id}
                           │
                           └─ navigate('/personalized-resources', { state: { newTaskId }})
                                └─ 页面加载 → 拉列表 → 展示新题目卡片
```

### 5.2 手动生成路径（题目类）

```
个性化资源页 → 点击"生成资源"
  └─ GenerateModal 三步引导
       └─ Step3 选 questionTypes → 提交
            └─ POST /api/v1/personalized-resources/generate
                 { generate_type: "quiz", source_type: "manual", chapter, knowledge_point, question_types }
                 │
                 ├─ 同上错题路径（无 wrong_question_ids，仅靠 chapter/kp 生成）
                 └─ 返回 202 → 关闭 Modal → 刷新列表（新 processing 卡出现）
```

### 5.3 手动生成路径（资源类）

```
个性化资源页 → 点击"生成资源"
  └─ GenerateModal 三步引导
       └─ Step3 选 resourceTypes → 提交
            └─ POST /api/v1/personalized-resources/generate
                 { generate_type: "resource", source_type: "manual", chapter, knowledge_point, resource_types }
                 │
                 ├─ Backend: resolve_generation_catalog → 创建 AsyncTask
                 ├─ 写入 user_personalized_resources（task_id, 无 resource_id）
                 ├─ 调用 Agent /resources/generate（异步，立即返回）
                 └─ 返回 202
                      │
                      后续：
                      ├─ Agent 完成 → POST /api/v1/webhooks/agent
                      ├─ Webhook: 写入 resources 表，补全 user_personalized_resources.resource_id
                      └─ 前端轮询（processingCount>0时每3秒拉列表）→ 卡片从"生成中"变为正常卡片
```

---

## 6. Agent 侧说明（无需改动）

当前 `agent_service/prompts/assessment.py` 中：
- `build_question_generation_user_message` 已读取 `personalization_context.wrong_points`（第 144-148 行）
- 格式：`[{"name": kp_name}]` 或扩展支持 `{"name": kp_name, "content": "题目原文"}`

**Backend 侧组装格式（统一写法）：**
```python
wrong_points = [
    {"name": q.knowledge_point, "content": q.content[:200]}
    for q in wrong_questions
]
ctx["wrong_points"] = wrong_points
```

Prompt 第 144 行直接取 `item.get("name")`，`content` 字段额外写入 prompt 文本，让 Agent 看到具体错题内容。

**`agent_service/api/v1/resources.py`：** 无需修改，复用现有 `/resources/generate`。

---

## 7. 文件改动清单（汇总）

### 后端（`backend/`）

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/models/others.py` | 追加 | 新增 `UserPersonalizedResource` model |
| `app/schemas/personalized.py` | 新建 | `PersonalizedResourceGenerateRequest` |
| `app/api/v1/personalized_resources.py` | 新建 | GET + POST 两个接口 |
| `app/api/v1/__init__.py` 或路由聚合 | 修改 | 注册新 router |
| `app/api/v1/webhooks.py` | 修改 | 补全 resource 类 user_personalized_resources 行 |
| DB migration | 执行 | 建表 `user_personalized_resources` |

### 前端（`frontend/src/`）

| 文件 | 操作 | 说明 |
|------|------|------|
| `api/services/personalizedResources.js` | 新建 | list + generate |
| `pages/PersonalizedResources.jsx` | 新建 | 独立页面 |
| `components/personalized/GenerateModal.jsx` | 新建 | 三步引导 Modal |
| `pages/PracticeResult.jsx` | 修改 | 添加 accuracy<60 触发提示 |
| `components/Sidebar.jsx` | 修改 | 添加导航入口 |
| `App.jsx` | 修改 | 注册路由 |

**总计：6 个后端文件（含新建）+ 6 个前端文件（含新建）**

---

## 8. 校验与测试计划

### 后端语法校验
```bash
python3 -m py_compile backend/app/models/others.py
python3 -m py_compile backend/app/schemas/personalized.py
python3 -m py_compile backend/app/api/v1/personalized_resources.py
python3 -m py_compile backend/app/api/v1/webhooks.py
```

### 前端构建校验
```bash
npm run lint
npm run build
```

### E2E 验收用例（手动）

| 场景 | 操作 | 预期结果 |
|------|------|---------|
| 错题触发 | 故意全部答错，提交，查看结果页 | 正确率 < 60% 时出现黄色提示横幅 |
| 点击生成 | 点"生成针对性练习" | 跳转至个性化资源页，顶部出现"正在生成..."卡片 |
| 等待完成 | 留在页面约 10s | 卡片变为具体题目，可展开查看题目内容 |
| 手动生成 | 点"生成资源"→ 三步表单 → 选资源类型 → 提交 | Modal 关闭，资源卡出现（processing 态）→ 3s 后刷新变为正常卡 |
| Sidebar 入口 | 从任意页面点 Sidebar "个性化资源" | 跳转至 /personalized-resources |

---

## 9. Phase C 扩展点（未来迭代）

> 本版本不实现，此处记录，以免日后割断。

当 `StudentProfile` 中的 `weak_points`（`cognitive_blindspots`）和 `knowledge_coordinates` 数据积累充分后，可在"个性化资源"页顶部增加"基于画像推荐生成"入口：

- 读取 `GET /profile` 返回的 `cognitive_blindspots` 列表
- 展示"你的薄弱知识点：XX、YY、ZZ，是否生成针对性资源？"
- 触发逻辑与手动生成完全相同，只是 chapter/knowledge_point 由 profile 自动填入

**改动仅需：**
- PersonalizedResources.jsx 增加 Profile 数据拉取
- 渲染推荐横幅（<ProfileRecommendBanner>）
- 无需新接口，无需改后端逻辑

---

## 10. 接口漂移记录

| 原始约束 | 实际实现 | 漂移描述 |
|---------|---------|---------|
| `POST /resources/generate` 仅 teacher | 引入新接口 `/personalized-resources/generate`，学生可用，底层复用相同 Agent | 权限模型扩展，新路径对学生开放；原接口不变 |
| quiz 生成不直接传错题内容 | `personalization_context.wrong_points` 新增 `content` 字段 | Agent prompt 已支持（即使 agent 不读 content，knowledge_point 精准度已大幅提升） |

---

## 11. 实现顺序建议

1. **DB 建表** → 验证 Model import 无报错
2. **后端 GET 接口** → 空列表可返回，前端可先联调
3. **后端 POST 接口（quiz 路径）** → 单元测试：错误题目 ID 列表 → 正确组装 wrong_points
4. **前端 PersonalizedResources.jsx + Sidebar** → 确认空列表页面可渲染
5. **前端 PracticeResult.jsx 修改** → 确认 accuracy<60 显示提示，点击生成跳转
6. **后端 POST 接口（resource 路径）** → Webhook 扩展一起做
7. **前端 GenerateModal.jsx** → 三步表单完整联调
8. **轮询逻辑** → 确认 processing 状态卡→完成卡的状态转换

每步完成后：`py_compile` + `npm run build` 通过，记录至 `WORKFLOW.md`。
