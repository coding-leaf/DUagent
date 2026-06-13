# Admin 批量生成保底题库 + 节点级答题 Design

## 问题

`quiz_questions` 表 0 题，学生 Quiz 页面无题可答。个性化出题依赖 Agent 实时生成且前端不接入口，基础答题链路完全断裂。

## 方案

Admin 在 CourseCatalogDrawer 一键批量生成保底题库（`source=baseline`），按 KG 全部节点出题。学生按节点进入答题（`/quiz?node_id=xxx`），个性化题阶段二后置。

---

## 一、Admin 批量生成

### 入口

CourseCatalogDrawer 新增"生成题库"按钮，与"生成学习资源"并列。仅 `catalog.status=ready` 且有 active KG 时可点击。

### 接口

```
POST /api/v1/admin/course-catalogs/{catalog_id}/quiz/generations
Request: 空（Backend 自行取 KG 节点）
Response: 202 { task_id, catalog_id, status: "processing" }
```

### Backend 流程

1. 取 active KG 全部节点
2. 为每个节点创建 1 个子 task（`task_type="quiz_generation"`, `parent_task_id`）
3. `asyncio.create_task` 后台并发调 Agent `/agent/v1/assessment/generate-questions`
4. Agent 返回的题校验后落库 `quiz_questions`
5. 子 task 完成后更新进度，父 task 汇总

### 每节点出题参数

```json
{
  "course_id": "<CourseOffering.id>",
  "node_name": "基本数据类型",
  "chapter": "第2章 数据类型、运算符与表达式",
  "knowledge_point": "基本数据类型",
  "question_types": ["single_choice", "single_choice", "single_choice",
                     "multi_choice", "multi_choice", "multi_choice", "multi_choice"],
  "count": 7,
  "difficulty": "medium",
  "source": "baseline"
}
```

### 落库字段

| 字段 | 值 |
|------|-----|
| `course_id` | CourseOffering.id（该 catalog 绑定的教学班） |
| `chapter` | KG node.chapter |
| `knowledge_point` | KG node.name |
| `type` | `single_choice` / `multi_choice` |
| `source` | `baseline` |
| `personalized` | `0` |
| `owner_user_id` | `null` |
| `difficulty` | `medium` |

### 约束

- 每个 catalog 每种 `source=baseline` 题库最多一份（重复生成前软删旧题）
- 如 catalog 未绑定任何 CourseOffering，拒绝并返回 409

---

## 二、节点级答题

### URL 参数

```
/quiz?course_id=xxx&node_id=yyy    → 节点模式（只拿该节点题）
/quiz?course_id=xxx                → 自由模式（全量题）
```

### Backend 改动

`GET /api/v1/quiz/questions?course_id=x` 加可选参数 `node_id: str | None = Query(None)`。

有 `node_id` 时：按 `course_id + knowledge_point(node_name)` 过滤（从 KG 查 `node.name`）。
无 `node_id` 时：保持现有行为，返回课程全量题。

### 前端改动

| 文件 | 改动 |
|------|------|
| `LearningPath.jsx` | "进入练习" `<Link to={`/quiz?course_id=...&node_id=...`}>` |
| `Quiz.jsx` | 从 URL 读取 `node_id`，传给 `GET /quiz/questions` |

### 答题流程

1. LearningPath 点节点 → 节点资源面板显示该节点题摘要（已有 `get_node_resources`）
2. 点"进入练习" → `/quiz?course_id=x&node_id=y`
3. GET 该节点 7 题 → 逐题作答 → POST submit → GET result
4. 做完留在结果页，手动返回节点面板

### `get_node_resources` 不动

保持摘要展示职责，不掺答题 session 逻辑。

---

## 三、个性化题（阶段二，本次不实现）

```
学生做完节点 7 道保底题 → score < 60%
  → 节点面板出现"针对性练习"按钮
  → POST /quiz/generate → Agent 实时出 3 道纠偏题
  → source=personalized, personalized=1, owner_user_id=当前学生
  → 独立 session，分数不混入保底评估
```

URL 可扩展：`/quiz?course_id=x&node_id=y&mode=personalized`

---

## 四、代码题（阶段二，本次不实现）

阶段一用"阅读代码选输出"（single_choice）+ "多选分析题"（multi_choice）替代代码编程。
阶段二接第三方判题 API（Judge0 等），`quiz_questions` 表新增 `code_template` / `test_cases` 字段。

---

## 五、改动范围

| 层 | 文件 | 改动 |
|----|------|------|
| Backend | `catalogs.py` | 新增 `POST /admin/course-catalogs/{id}/quiz/generations` + 子任务后台 |
| Backend | `quiz.py` | `GET /quiz/questions` 加可选 `node_id` query param |
| Frontend | `CourseCatalogDrawer.jsx` | 新增"生成题库"按钮 + 轮询 task 进度 |
| Frontend | `admin.js` | 新增 `startQuizGeneration()` + `getQuizGenerationTask()` |
| Frontend | `LearningPath.jsx` | "进入练习"链接带 `node_id` |
| Frontend | `Quiz.jsx` | 读 URL `node_id`，传给 `GET /quiz/questions` |
| 不动 | `quiz_questions` 表 | 已有所有必需字段 |
| 不动 | `get_node_resources` | 保持摘要展示 |
| 不动 | `POST /quiz/generate` | 保留，阶段二使用 |

---

## 六、未覆盖

- 代码编程题（需要沙箱/Judge0）
- 个性化题生成触发（阶段二）
- 错题本/错题强化（阶段二）
- 教师查看班级题库统计（阶段二）
