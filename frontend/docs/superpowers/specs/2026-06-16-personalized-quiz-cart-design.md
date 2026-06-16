# 个性化错题购物车 (Personalized Quiz Cart) 设计方案

## 1. 目标
优化“个性化资源”页面的错题练习体验。将目前独立的错题按“知识点 (Knowledge Point)”进行聚合，并引入类似购物车的“勾选组卷”功能，允许用户一次性合并多道错题进行练习，避免每道题单独点开的繁琐。

## 2. 约束与核查
经过严格核查当前代码链路，**本方案不需要修改任何数据库表结构（无需新增字段）**，也不会影响现有的其他测验和学习路径功能。
- **关于题目标识/摘要**：为避免数据库字段更新，我们将直接使用题目原有的 `content`（截取前 50 个字，超长补 `...`）作为列表主标题，结合原有的 `type`（题型）和 `difficulty`（难度）以及 `source_type` 作为标识，足以满足用户的识别需求。
- **关于接口兼容性**：仅需在现有的 `GET /api/v1/quiz/questions` 接口上增加一个**可选的** `question_ids` 查询参数，对所有既有调用方完全透明。

## 3. 具体修改范围

### 3.1 前端：`src/pages/PersonalizedResources.jsx`
- 重构 `QuizGroupCard` 组件，改为**可展开/折叠**的卡片（默认折叠）。
- 展开后列表渲染该知识点下的题目项，提供 `checkbox`。
- 增加父级状态 `selectedIds` 维护选中的题目。
- 增加“全选本知识点”功能。
- 展开区域限制 `max-height` (例如 `320px`) 并设置 `overflow-y: auto` 以防止数据过多撑爆页面。
- 点击“开始练习”时，判断是否勾选了具体题目：
  - 如果未勾选任何题目：维持原有逻辑，跳转 `/quiz?course_id=...&knowledge_point=...`（基于整个知识点组卷）。
  - 如果勾选了具体题目：跳转 `/quiz?course_id=...&question_ids=id1,id2,id3`（基于选中项精确组卷）。

### 3.2 前端：`src/pages/Quiz.jsx`
- 从 URL 参数中提取 `question_ids`。
- 将其传入 `quizService.getQuestions(..., { question_ids })`。

### 3.3 后端：`backend/app/api/v1/quiz.py`
- 修改 `get_questions` 接口，增加 `question_ids: str = Query(None)`。
- 如果存在 `question_ids`，解析为列表并通过 `QuizQuestion.id.in_(...)` 进行过滤，同时 **忽略原有的 `limit` 参数**（因为勾选数量已经由用户决定，后端不应截断）。

## 4. 影响面评估
- **安全性**：查询仅限于当前用户拥有的题目（`owner_user_id == current_user.id` 或公共题库），已有数据权限拦截，通过 ID 批量查题不会存在越权问题。
- **旧功能兼容**：旧版通过 `knowledge_point` 直接拉题的逻辑不受影响；测验提交逻辑 `/api/v1/quiz/submit` 对数据来源无强感知，无需修改。
