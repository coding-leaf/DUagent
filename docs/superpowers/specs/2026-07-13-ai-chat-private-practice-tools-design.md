# AI Chat 私有练习工具设计

## 问题

普通 Quiz 的前端渲染与 Backend 判题只形成了单选题和多选题闭环，但生成契约仍允许
`code` 与 `short_answer`。这会把缺少可执行测试用例的伪编程题写入普通题库，最终在答题页
显示为不支持题型。

AI Chat 已有真正的私有编程题工具：草案经 Backend OJ 验证公开与隐藏用例后发布为
`CodeProblem`，并创建 `CodeSandboxCard`。选择题则缺少对应的发布工具，只能绕用普通生题接口。

## 设计

### 普通 Quiz 边界

- 普通题型固定为 `single_choice`、`multi_choice`。
- Agent 请求模型、生成提示词、Backend 请求模型和持久化校验使用同一范围。
- 普通取题接口过滤历史 `code`、`short_answer` 数据，但不删除历史记录。
- 前端个性化生成入口和错题强化只提交单选、多选。

### AI Chat 私有选择题

- AgentScope 工作台新增一个原子写工具，接收完整的选择题草案。
- 工具通过 Backend internal API 发布，不直接访问 MySQL。
- Backend 验证会话归属、课程选课关系、题型、选项键和答案集合。
- 每道题写入 `quiz_questions`，同时写入 `user_personalized_resources`，来源为 `ai_chat`，
  所有权固定为当前学生。
- 发布成功后工具原子创建持久化 `QuizCard`。卡片只保存 `course_id` 与 `question_ids`，
  点击后进入正式 Quiz 页面，沿用已有提交、判分和学习证据链路。

### AI Chat 私有编程题

- 继续使用 `validate_personal_code_problem_draft`。
- 该工具内部负责 OJ 验证、发布及创建 `CodeSandboxCard`。
- 不再向模型单独暴露卡片创建步骤，防止重复装载或在发布失败时创建空卡片。

## 架构取舍

- 选用专用工具与 Backend Service：发布属于有副作用的原子能力，需要结构校验和权限检查。
- 不选用 Team：单批私有练习发布没有并行协作或独立审核收益。
- 不扩展普通 Quiz 支持编程题：代码判题、隐藏用例和参考解需要独立数据模型，复用普通题字段会丢失关键数据。
- 不新增数据库表或第三方依赖。

## 契约变化

- Client API：普通 Quiz 题型从四种收紧为单选、多选。
- Agent API：知识题生成的 `question_types` 收紧为单选、多选。
- 新增 Backend internal AI Chat 选择题发布接口；不直接暴露给前端。

## 验证

- Backend：请求模型、权限校验、选择题落库和历史题型过滤测试。
- Agent Service v2：工具发布、失败降级、卡片校验、工具组权限和提示词测试。
- Frontend：QuizCard 跳转、错题强化 payload、lint 与 build。
