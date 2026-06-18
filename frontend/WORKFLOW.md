# Frontend Workflow

`WORKFLOW.md` 是施工日记和最近验证记录，不再承担功能主线判断职责。

阅读分工：

- 功能主线、状态和下一步：`docs/feature-ledger.md`
- 项目方向、结构和断层恢复：`docs/project-direction.md`
- 页面/API/Backend/Agent/测试证据：`docs/project-coverage-audit.md`
- 单次施工记录和最近验证：`WORKFLOW.md`

## 当前施工状态

- 当前主线以 `docs/feature-ledger.md` 为准。
- KG-node 资源生成已在 C 语言样本完成真实闭环（`108/108 candidate_count>0`），不再作为最高优先级重复验证。
- API 层 KG fallback 和节点资源接口（`get_node_resources`）已修好，前端 LearningPath 节点资源面板已可展示 `weak_point_tutorials` / `exercises` / `chapter_materials`。先前记录"无 LP 记录"的阻塞已实际解除。
- 探针工具 `learning_path_resource_probe.py` 仍落后于 API 实现口径：KG 查找未走 `kg_host_course_id` 链路、无 LP fallback、资源查询未用 `resource_scope_clause`。下次跑探针前需修复。
- C 语言主 catalog `e21d9fdaaa0c43a3`（绑定教学班 `cprogcourse202606120001`）`kg_host_course_id = NULL`，导致 `_synthesize_kg_fallback_path` 无法找到 active KG（KG `c5b437f8701b482a` 35 节点存在但 course_id 直接是教学班 ID）。这是当前 LearningPath KG fallback 的实际阻断点。
- 已确认可操作能力：Admin 课程资源库创建、资料上传、触发入库向量化、任务轮询、知识库状态展示、基于知识切片自动刷新课程知识图谱、按资源库触发学习资源生成、生成资源列表、资料/资源软删除；LearningPath 节点资源展示。
- 当前前端契约作废 / 不接入能力：资源生成 `/resources/generate`、Quiz 生成 `/quiz/generate`；教师端不提供生成资源入口，练习页不提供触发生题入口。**注：个性化资源功能通过新接口 `/personalized-resources/generate` 绕开权限限制，学生可用，见 2026-06-16 设计。**
- 当前待推进：个性化资源功能（设计已完成，待实现）；#29 knowledge_points 元素类型契约审查（对象 vs string）；Evaluation refresh 入口决策；探针口径修复（非阻塞）。
- 当前工作区注意：`AGENTS.md` 已更新为新文档分工入口；未跟踪文件和存储产物不要混入提交。

## 待办事项 (TODO)

- **[Backend/Agent]** 修复答题结束后，未正常生成/返回 AI 题解诊断的问题（目前前端 `PracticeResult` 的 UI 已剥离就绪，但缺失后端数据供给）。

## 最近验证

### 2026-06-17

- Quiz & PracticeResult 页面容器与展现分离重构完成：
  - 核心改动：
    1. 将 `Quiz.jsx` 的厚重状态机、题型派发（`answerUpdaters`）、提交与埋点追踪逻辑剥离至 ViewModel Hook `useQuizEngine.js`，UI 部分肢解为 `<QuizHeader />`、`<QuizSidebar />`、`<QuizFooter />` 三个无状态哑组件，`Quiz.jsx` 退化为薄容器。
    2. 将 `PracticeResult.jsx` 的 5 秒防抖轮询、诊断数据拉取、画像刷新以及错题生成逻辑剥离至 `usePracticeResult.js`（并修复了原有的 `eslint` 依赖隐患，改用函数式更新），UI 部分肢解为 `<ResultLoadingState />`、`<ResultScoreBoard />`、`<QuestionReviewList />` 三个无状态哑组件。
    3. 全面规范化：所有导出的事件函数均已使用 `useCallback` 记忆化，阻断了父组件重渲导致的级联渲染。
  - 后续 Bug 修复与测试增强：
    1. 修复了 `PracticeResult.jsx` 中由 API 错误引发的无限 Loading 动画死循环问题，增加了错误处理兜底卡片。
    2. 修正了 `QuizHeader` 中把 fixed 吸顶导航栏和内容区进度条混在一起并错误塞入 `<main>` 的 HTML 语义问题，已切分为 `<QuizHeader>` 与 `<QuizProgressCard>`。
    3. 补充了 ViewModel 层 Hook（`useQuizEngine` 与 `usePracticeResult`）的专门单元测试，使用 Vitest 和 React Testing Library 验证其内部状态流转与网络 Mock 请求。
  - 改了什么文件：`src/pages/Quiz.jsx`, `src/pages/PracticeResult.jsx`，新增 `src/hooks/useQuizEngine.js`, `src/hooks/usePracticeResult.js`，以及 `src/components/quiz/` 下的 7 个组件，新增 `src/hooks/__tests__/` 单元测试。
  - 测试结果：Frontend `npm run lint` 与 `npm run build` 零报错通过。执行全程经由 AI Spec Reviewer 与 Code Quality Reviewer 双重卡点校验。Hook 层 6 个单元测试全绿通过。
  - 接口漂移：纯前端架构重构，无接口漂移。

### 2026-06-16

- 个性化错题购物车 (Personalized Quiz Cart) 接入完成：
  - 问题分析：原“个性化资源”页面下，知识点的错题是单独一条条的练习入口，用户无法选中多个错题进行一并练习。
  - 修复：
    1. Backend `GET /api/v1/quiz/questions` 新增 `question_ids` 查询参数；若包含此参数，按 ID 过滤并**忽略 limit**、绕过其它过滤条件，只返回指定的题目，同时增加 `len(ids_list) > 100` 的防攻击上限校验。
    2. Frontend `Quiz.jsx` 从 URL 的 `searchParams` 中提取 `question_ids`，并在初始化拉取题目时传入 `extraParams` 以供后端进行精确组卷。
    3. Frontend `PersonalizedResources.jsx` 中将 `QuizGroupCard` 改造成带折叠状态的组件：外层展示知识点和题目数；展开后展示可复选的题目列表（题干自动截断前 50 字符并显示难度/来源）。支持“全选”，点击“开始练习”时携带选中 ID 跳转至 `/quiz?course_id=...&question_ids=id1,id2`。未选中时 fallback 至原有 `knowledge_point` 整组练习路由。
  - 契约说明：API 后端新增了可选的查询参数，前端路由与取参方式对齐，原有请求和参数行为没有破坏，无破坏性契约漂移。
  - 验证：
    - Frontend `npx eslint src/pages/Quiz.jsx src/pages/PersonalizedResources.jsx` 检查修改的文件通过。
    - Frontend `npm run build` 成功。
    - Backend `python3 -m py_compile` 语法通过。

- 修复错题生成打断 KG 图谱节点统计的隐患：
  - 问题分析：原逻辑下，后端在生成新的个性化资源时优先信任 LLM 传回的 `knowledge_point`。由于大模型倾向于追加细节后缀（如 `Input/Output - printf函数`），导致生成的题目脱离了标准的 KG 图谱节点名，进而使其变成了不会被后续效果看板及画像引擎统计到的孤立数据（它们依赖严谨的 `QuizQuestion.knowledge_point IN (KG node)` 匹配）。
  - 修复：
    1. Backend `personalized_resources.py` 的落库逻辑扭转信任：强制转为 `knowledge_point = req.knowledge_point or q.get(...)`，剥夺 LLM 对该字段的创造权，使新题死死挂载在触发它生成的原生图谱主节点上。
    2. Frontend `PersonalizedResources.jsx` 补齐了调用链路：在“购物车”点击开始练习生成 `/quiz` 跳转时，强制附带被编码后的主卡片 `knowledge_point`，以保证答完题后的 `PracticeResult` 可以准确将其传给后端作为原生图谱依据。
    3. 脏数据清理：直接对 MySQL 执行 `UPDATE` 砍掉 `knowledge_point` 中已存的 ` - ` 后缀，让遗留的游离题目重新归属于正确的图谱节点。

- 增加个性化资源软删除功能：
  - 后端：在 `api/v1/personalized_resources.py` 增加 `DELETE /{id}` 接口。同时完成主表 `UserPersonalizedResource` 以及下挂关联资源 `QuizQuestion` 和 `Resource` 的软删除。
  - 前端：更新 `personalizedResources.js` API 层；在 `PersonalizedResources.jsx` 为 `QuizGroupCard` (题目单条)、`ResourceCard` (生成失败卡片、完成的阅读资源卡片) 添加了带二次确认拦截的删除按钮。

### 2026-06-15

- Admin 注册码管理、忘记密码弹窗、Admin 重置密码：
  - 新增 `GET/POST/DELETE /admin/registration-codes` 三个接口（`backend/app/api/v1/admin.py`）；schema 新增 `CreateRegistrationCodeRequest`（`backend/app/schemas/admin.py`）；注册码用 `secrets.token_urlsafe(8)` 随机生成，吊销走软删除。
  - 前端 `AdminConsole.jsx` 新增「注册码管理」tab：列表展示码值/角色/生成时间，支持一键复制（1.5s 回显对勾）和吊销；右上角「生成教师码」「生成学生码」按钮。
  - `AdminConsole.jsx` 用户行新增「重置密码」按钮，点击弹 modal 输入新密码，复用已有 `PUT /admin/users/{id}` + `new_password` 字段（后端早已支持）。
  - `Login.jsx` 「忘记密码」链接改为弹 modal，提示"请联系管理员重置账号密码"，点遮罩或「知道了」关闭。
  - 前端 service `admin.js` 新增 `getRegistrationCodes / createRegistrationCode / revokeRegistrationCode`。
  - 契约说明：新增 `/admin/registration-codes` 接口族，无现有字段改动，无 OpenAPI 漂移。
  - 验证：`python3 -m py_compile backend/app/api/v1/admin.py` → OK；`npm run build` → 通过（仅既有 Vite chunk size warning）。


  - 修复 Backend `profile_refresh` / `evaluation_refresh` 后台任务的 MySQL named lock 生命周期：`GET_LOCK`、写库、`RELEASE_LOCK` 保持在同一 DB session/连接内完成，并在 `commit()` 前释放，避免连接归还连接池后用错误连接释放锁。
  - 同步收口 `profile/initialize` 与 `profile/dialogue-update` 的同名 profile 写锁释放顺序，避免对话补充画像后阻塞后续同步画像。
  - 修复 `profile_refresh` 写 `drive_intent.learning_habits` 和 `drive_intent.knowledge_progress_summary` 时的 JSON 持久化：改为新 dict 合并并显式 `flag_modified`，保留既有 `learning_goal/type/source`。
  - `POST /profile/refresh` 和 `POST /evaluation/refresh` 对同一 user/course 已有 `processing` 任务时复用已有 `task_id`，避免重复点击制造竞争任务。
  - `/learning-effects` 重新评估失败时优先展示 `task.error_message`，其次展示 `error_code`，不再只显示泛化失败文案。
  - 契约说明：未新增请求参数，未删除响应字段；复用既有 `GET /tasks/{task_id}` 的 `error_code/error_message`，无 OpenAPI 漂移。
  - 验证：
    - `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/profile_refresh_red_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_refresh_async.py -q -p no:cacheprovider` → `1 passed`。
    - `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/profile_refresh_red_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_lock_async.py -q -p no:cacheprovider` → `1 passed`。
    - `../.venv/bin/python -m pytest tests/test_profile_rules.py -q -p no:cacheprovider` → `8 passed`。
    - `npm run test:e2e -- e2e/specs.spec.js -g "Learning effects refresh failure shows task error detail"` → `1 passed`。
    - `npm run lint` → 通过。
    - `npm run build` → 通过，仍有既有 Vite chunk size warning。
  - 运行态恢复：检查 MySQL `performance_schema.metadata_locks` 当前无 USER LEVEL LOCK；停止旧 Agent Service `:8002` 进程 `1640316`，并从 `agent_service/` 启动新进程 `1970256`，服务监听 `http://127.0.0.1:8002`。启动时 AgentScope Studio `localhost:3000` 未运行仅产生 warning，应用启动完成。

- Tighten Profile Direction and LLM Evaluation Summary:
  - 将 `/profile/dialogue-update` 的学习方向收紧为枚举：`exam_sprint`（备考冲刺）、`daily_homework`（课后巩固）、`casual`（兴趣拓展）；“我喜欢视频/图解/代码”等资源偏好输入归类到标准模态偏好，不再写入当前学习方向。
  - 扩展 Backend `evaluation/refresh` 传给 Agent 的上下文：用户专业/年级/引导级别、规则画像、KG 节点与节点进度、学习行为统计。
  - Agent Service `evaluation/generate` 改为 LLM 只生成 `summary_text`，表格和核心数值继续由规则结果保护；prompt 要求按“学习范围 / 当前掌握 / 学习行为 / 下一步建议”模板输出总结。
  - 同步扩展 `../docs/20-agent-api/*` 与 `../docs/10-client-api/*` 参考契约。
  - 验证：Backend profile/dialogue 与规则测试 `21 passed`；Agent Service evaluation + OpenAPI alignment `40 passed`；Agent/Backend 语法检查通过；`npm run lint`、`npm run build` 通过（仅 Vite chunk size warning）。

- Complete Profile Capability Chain:
  - 补全 `/profile` 新画像能力：保留扩展契约 `learning_habits`、`knowledge_progress_summary`、`kg_quiz_activity`，并让默认画像返回稳定结构。
  - 修复 KG 节点状态链路：`mastered / weak / learning / pending_practice / unstarted` 现在在 `/profile` 和 `/learning-effects` 前端展示中均有明确中文状态、图标和统计口径。
  - 修复规则引擎真实计算：新增连续学习天数、7 日练习次数、未开始节点和已练习节点汇总；修复最近一次低分不参与 weak 判定的聚合缺口。
  - 扩展 `../docs/10-client-api/API_前端接口规范.md` 与 `Client-API.openapi.json`，记录新画像维度、来源和知识坐标状态。
  - 验证：`tests/test_profile_rules.py tests/test_knowledge_progress.py` 18 passed；`python3 -m json.tool` 校验 OpenAPI JSON 通过；`npm run lint` 通过；`npm run build` 通过（仅 Vite chunk size warning）。

- Implement Profile Rules Engine:
  - 在 `backend/app/services/profile_rules.py` 中实现了 `compute_profile_fields` 函数，用于计算学习画像的各个维度。
  - 将复杂的规则计算逻辑拆分为纯净、可测试的函数（如 `compute_modal_preference`, `compute_knowledge_progress`, `compute_learning_habits`, `compute_discipline_badge`）。
  - 为所有纯净规则计算函数编写了全面的单元测试 `backend/tests/test_profile_rules.py`，测试全部通过。
  - 没有产生契约漂移，完全遵循需求。

### 2026-06-15

- Fix Profile Persistence and Extract Shared KG Aggregation:
  - 提取 `_build_node_progress_rows` 和 `_resolve_evaluation_kg` 从 `backend/app/api/v1/evaluation.py` 到新的共享服务 `backend/app/services/knowledge_progress.py`。
  - 更新 `evaluation.py` 的相关调用和导入。
  - 修复 `backend/app/api/v1/profile.py` 里的画像持久化逻辑，由原来的软删除后插入新行改为直接就地更新，解决了使用软删而唯一索引未过滤导致的 unique key 冲突问题。

### 2026-06-14

- 二次修复 AIChat 短期记忆失效与刷新后 user/assistant 顺序反转：
  - 复查结论：上一轮 `done.conversation_id` 修复后，真实 MySQL 最新会话已出现同一 `conversation_id` 下 6 条消息，说明前端会话续接已生效；继续失效的断点不是“每轮新建会话”，而是短期上下文传给 Agent 后不干净 / 不够明确。
  - 根因：
    1. Backend `_assemble_tutoring_payload()` 在保存当前 user 消息和空 assistant 占位后查询最近消息，导致 `recent_messages` 混入当前轮 user 和空 assistant placeholder。
    2. 历史消息接口只按 `create_time ASC` 排序；user/assistant 同秒写入时数据库返回顺序不稳定，刷新后可出现 assistant 在 user 前面的反转。
    3. Agent ReAct prompt 只是裸拼 `[user] / [assistant]`，没有明确“最近对话（短期上下文）”区块，也没有要求“刚才/上文/之前”类追问优先依据最近对话回答。
  - 修复：
    1. `backend/app/api/v1/tutoring.py`：组装 Agent payload 时排除本轮刚写入的 user 消息和 assistant 占位；最近消息和历史详情统一按 `create_time/update_time/user-before-assistant` 稳定排序。
    2. `agent_service/agents/tutoring_react_flow.py`：将 `recent_messages` 渲染为“最近对话（短期上下文）”区块，并加入追问优先使用最近对话的明确指令。
    3. 回归测试覆盖 payload 排除当前轮、历史刷新排序、Agent prompt 短期上下文指令。
  - 契约说明：未修改 Client API / Agent API schema；仅修复实现和 prompt 组装，无 OpenAPI 漂移。
  - 验证：
    - `cd backend && ../.venv/bin/python -m pytest tests/test_agent_integration.py::TestTutoringChatIntegration tests/test_tutoring_privacy.py -q -p no:cacheprovider` → `8 passed`。
    - `cd agent_service && ../.venv/bin/python -m pytest tests/test_tutoring_react_flow.py tests/test_tutoring_retrieval_personalization.py -q -p no:cacheprovider` → `12 passed`。
    - `npm run lint` → 通过。
    - `npm run build` → 通过，仍有既有 Vite chunk size warning。
  - 剩余风险：本轮增强的是短期上下文 prompt 和历史排序；模型是否严格遵循仍取决于 LLM，但已把“刚才/上文”类追问的可用上下文和指令显式前置。

### 2026-06-14

- 修复 AIChat 新建会话后只能单轮回答、无法延续上下文的问题：
  - 根因：Backend `POST /tutoring/chat` 正常代理 Agent SSE 时原样透传 Agent `done` 事件；Agent Service 的 `DoneEvent` 不包含 Client API 契约要求的 `conversation_id`，前端因此无法在新建对话首轮结束后设置 `activeSession`，第二轮继续以空 `conversation_id` 发起，表现为每次都是新会话。
  - 修复：`backend/app/api/v1/tutoring.py` 在 Backend Client API 边界解析到 `type=done` 后，强制补齐真实 `conversation_id` 和 Backend assistant `message_id`，并保留 Agent 返回的知识点 / 练习建议字段；非 done 事件继续透传。
  - 回归测试：`backend/tests/test_agent_integration.py` 新增 `test_tutoring_chat_done_event_includes_backend_conversation_id`，mock Agent 返回不带 `conversation_id` 的 done，先 RED 失败于 `KeyError: 'conversation_id'`，修复后通过。
  - 契约说明：未修改 OpenAPI / Client API 文档；本轮是实现对齐既有 `done.conversation_id` 契约，无契约漂移。Agent Service 内部 schema 不变。
  - 验证：
    - `cd backend && ../.venv/bin/python -m pytest tests/test_agent_integration.py::TestTutoringChatIntegration::test_tutoring_chat_done_event_includes_backend_conversation_id -q -p no:cacheprovider` → `1 passed`。
    - `cd backend && ../.venv/bin/python -m pytest tests/test_agent_integration.py::TestTutoringChatIntegration -q -p no:cacheprovider` → `4 passed`。
    - `npm run lint` → 通过。
    - `npm run build` → 通过，仍有既有 Vite chunk size warning。
  - 剩余风险：本轮恢复的是当前会话短期上下文续接；长期 memory 压缩仍按当前主线暂缓，不在本次范围。

### 2026-06-14

- 移除 ai-chat（tutoring）链路的规则 Guard，修复 LLM 有效回答被误杀后前端只显示一句摘要的问题：
  - 根因：`generate_tutoring_sse_events` 在 ReAct 产出后调用 `evaluate_tutoring_response_by_rule` 做相关性（off_topic）校验，要求检索可信术语字面出现在回答里；当前素材 OCR 差、资源与 KG 节点对不齐，术语对不上 → 有效回答被判 off_topic 清零 → 落到 `_build_chunk_content` 兜底句（内含 `conversation_summary`），前端因此只显示“结合已有摘要：…”那段摘要，而 LLM 实际已洋洋洒洒输出完整回答。
  - 修复（范围：流程移除、保留文件）：
    1. `agent_service/agents/tutoring.py`：删除首轮/重试/异步审查三处 Guard 调用，删除仅 Guard 使用的 `_empty_response` 与相关 import；ReAct 有产出即采纳；重试仅在 LLM 实际无产出（返回 `None`）时触发；不再发 `review:flagged` 事件（前端琥珀色“该回答可能不准确”徽章相应不再出现）。
    2. 保留 `agent_service/agents/tutoring_response_critic.py` 与 `tests/test_tutoring_response_critic.py` 作为可复用规则工具，暂不挂在链路上。
    3. 测试同步：`test_tutoring_agent.py` 删除 off_topic 拦截用例；`test_tutoring_fast_path.py` 改为“空文本走 build 兜底、不重试、无 review”+“仅 None 才重试”两个用例；`test_tutoring_api.py` 三个规则/降级链路用例去掉末尾 `review` 事件断言。
  - 契约说明：未改 OpenAPI / Client API；`ReviewEvent` schema 保留（仅停止发送），无契约漂移。
  - 影响：off_topic / grounding 不达标的回答不再被拦截，直接展示 LLM 原文（删 Guard 的预期代价）；LLM 真返回空文本时仍有 build 层规则兜底句。
  - 测试：`cd agent_service && uv run pytest tests/test_tutoring*.py -q` → `83 passed`。全量 `uv run pytest -q` 为 `9 failed, 465 passed`，9 个失败属既有问题（`test_aichat_hybrid_retrieval.py` 缺 `pytest-asyncio` 标记、`test_assessment_difficulty_balancer.py` 难度均衡器），均未触碰本次改动源码，与本次无关。

### 2026-06-14

- 修复学习效果看板 `study_duration_seconds` 不更新问题：
  - 根因：`GET /evaluation` 在存在 Evaluation 快照时，用 `stored_node_progress` 覆盖了实时聚合的 `node_progress`
  - 修复：`evaluation.py:298` 改为始终返回实时 `node_progress`，不再依赖旧快照
  - 测试：`test_learning_activities.py` 3 passed, `test_refresh_async.py` 1 passed
  - 影响：用户答完题后回到学习效果页，学习时长即时可见，无需手动"重新评估"

### 2026-06-14

- `/learning-effects` KG 节点学习效果看板接入完成：
  - 问题分析：
    1. 原页面只有局部掌握度来自 `GET /evaluation`，AI 分析报告、学习路径进度表、资源反馈分布、总交互数等仍是硬编码展示。
    2. “重新评估”按钮没有调用 `/evaluation/refresh`，`learningService.refreshEvaluation()` 也没有传 `course_id`。
    3. 用户确认产品口径：没有题目的 KG 节点显示“未测评/默认通过”，不伪装成 A 分；没有真实学习行为采集时，学习耗时显示“暂无记录”。
  - 修复：
    1. Backend `GET /evaluation` 新增 `node_progress`，按 active KG 节点聚合题目数、答题记录、掌握分、评估状态和可用耗时；刷新评估时把同一节点行写入 `progress_table.rows`，避免本轮新增数据库字段。
    2. Client API OpenAPI 和 Markdown 规范补齐 `EvaluationNodeProgress` / `node_progress` 字段与 `scored`、`pending_practice`、`unassessed_default_pass`、`unknown` 状态规则。
    3. Frontend `LearningEffects.jsx` 移除硬编码报告、路径表和资源反馈分布，改为展示概览、学习效果总结、KG 节点学习进度表、掌握度分布；“重新评估”调用 `POST /evaluation/refresh` 并轮询 `GET /tasks/{task_id}`。
    4. `learningService.refreshEvaluation(courseId)` 改为按契约提交 `{ course_id }`。
  - 契约说明：本轮已同步 `../docs/10-client-api/Client-API.openapi.json` 与 `../docs/10-client-api/API_前端接口规范.md`，新增响应字段 `node_progress`；不涉及 Agent API 改动。
  - 验证：
    - Backend RED：`tests/test_refresh_async.py` 先失败于 `eval/get → scored node present`，证明旧接口缺少 `node_progress`。
    - Backend GREEN：`TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/evaluation_node_progress_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_refresh_async.py -q -p no:cacheprovider` 通过，`1 passed`。
    - OpenAPI：`python3 -m json.tool ../docs/10-client-api/Client-API.openapi.json >/tmp/client-api-openapi-check.json` 通过。
    - Frontend RED：`npm run test:e2e -- e2e/specs.spec.js -g "Learning effects"` 先失败于找不到真实总结文本。
    - Frontend GREEN：同一 Playwright 用例通过，`1 passed`。
    - `npm run lint` 通过。
    - `npm run build` 通过，仍有既有 Vite chunk size warning。
  - 剩余风险：
    - 当前学习耗时主要来自已提交 QuizSession 的 `time_spent`，资源阅读/页面停留类 activity 采集尚未设计；无真实来源时前端显示“暂无记录”。
    - KG 节点与题目仍依赖 `QuizQuestion.knowledge_point == KG node.name` 的名称映射，后续若要更稳需增加显式 `node_id` 归属。

- 数据库状态快照与 WORKFLOW 同步：
  - 验证方式：Docker `eduagent-mysql` 直连 `duagent` 库，SQL 逐表核对。
  - C 语言体系实际 ID：主 catalog `e21d9fdaaa0c43a3`（`kg_host_course_id=NULL`）、教学班 `cprogcourse202606120001`、active KG `c5b437f8701b482a`（35 节点/35 边, course_id 直接是教学班 ID）。WORKFLOW 之前引用的 `b2444963f0e54587`、`6c698badb60a4809`、`27c3acb1e98a49d1` 在当前库不存在。
  - 4 个 C catalog 的 `chunk_count` 与 `material.chunk_count` 一致（663=663），无历史不一致残留。
  - Resources: 80 total（40 带 catalog_id 归属 `460778c3b06c4a54`，40 不带 catalog_id 归属 `cprogcourse202606120001`）。Quiz: 0 题。LearningPath: 0 条记录。
  - 探针 `learning_path_resource_probe.py` 落后于 API：KG 查找未走 `kg_host_course_id` 链、无 LP fallback、资源查询未用 `resource_scope_clause`。API（`d63e919` 后）已修好。
  - e21d9fdaaa0c43a3 的 kg_host_course_id=NULL 是 LearningPath KG fallback 的当前阻断点。
  - 契约说明：纯数据库只读查询，无契约漂移。
  - WORKFLOW.md 施工状态节已更新。

- AIChat 聊天回答内嵌 Markdown Mermaid 代码块可视化渲染及 React 19 属性警告修复：
  - 问题分析：
    1. 大模型在回答正文中直接输出的 ````mermaid` 代码块，以往被作为常规的高亮文本代码块渲染，未将其转化为 SVG 关系图，导致页面上直接展示 Mermaid 源码。
    2. React 19 开发环境下，`ReactMarkdown` 在自定义 `code` 渲染组件中带入的 AST 节点 `node` 属性在未剥离的情况下直接传给 DOM 元素，导致 `node="[object Object]"` 属性污染 DOM 并触发控制台警告。
  - 修复：
    1. 在 `ChatMessage.jsx` 的自定义 `code` 组件中，对非 inline 且语言为 `mermaid` 的代码块进行拦截，自动转换为 `MermaidDiagram` 可视化组件进行图形渲染。
    2. 采用结构化参数提取：`code(codeProps)`，显式解构取出 `node`，并将剩余的 `rest` 属性传递给 `<SyntaxHighlighter>` 与 fallback `<code>`，完全消除了属性污染与警告。
  - 契约说明：纯前端 Markdown 图解与渲染属性过滤，不涉及 API 契约机制变更，无契约漂移。
  - 验证：
    - `npm run lint` 通过。
    - `npm run build` 成功。
    - `npx playwright test e2e/specs.spec.js -g "AI Chat renders historical messages"` 通过。

- AIChat 桌面端侧边栏收起后控制按钮丢失问题修复：
  - 问题分析：原 `<aside>` 侧边栏容器在折叠时被赋予了 `lg:overflow-hidden` / `xl:overflow-hidden`，由于绝对定位的折叠控制按钮悬浮在侧边栏容器边缘之外（具有负偏置 `right-[-12px]` / `left-[-12px]`），容器的 `overflow-hidden` 会直接把控制按钮裁剪隐藏，导致折叠后按钮消失，用户无法再次展开。
  - 修复：移除 `<aside>` 侧边栏本身在折叠时的 `overflow-hidden` 样式，使其保持溢出可见。同时在侧边栏内部引入一层自适应的 `<div className="w-full h-full overflow-hidden flex flex-col">` 包装容器，这样在宽度为 0 时能依然利用这层包装裁切隐藏侧边栏的正文，而绝对定位的按钮则因为外层可见而能正常悬浮显示并响应点击。
  - 契约说明：纯前端 UI 布局结构调整，无契约漂移。
  - 验证：
    - `npm run lint` 通过。
    - `npm run build` 成功。
    - `npx playwright test e2e/specs.spec.js -g "AI Chat renders historical messages"` 通过。

- AIChat 聊天对话中 Mermaid 嵌套括号节点渲染报错修复：
  - 问题分析：原 `sanitizeMermaidSource` 采用简单正则进行替换，当节点标签包含嵌套括号时（如 `B[arr[0]=10]`），正则会提前匹配到第一个右中括号 `]`，从而将 `B[arr[0]` 错误替换为 `B["arr[0"]`，其后残留的 `=10]` 导致最终生成非法语法并触发 Mermaid 解析报错（Lexical error）。
  - 修复：重写 `sanitizeMermaidSource`，使用支持嵌套括号/花括号/中括号层级扫描（Nesting-Aware Scanning）算法。通过跟踪 `[` / `]`、`(` / `)` 等括号对的嵌套计数，精确确定节点的最外层闭合位置，完美解决包含嵌套表达式（如数组下标）的标签在自动加引号时被截断的问题。
  - 契约说明：纯前端 Mermaid 语法容错处理，不涉及 API 契约机制变更，不涉及后端与契约漂移。
  - 验证：
    - `npm run lint` 通过。
    - `npm run build` 成功。
    - `npx playwright test e2e/specs.spec.js -g "AI Chat renders historical messages"` 通过。

- AIChat 页面动态推荐资源侧边栏接入完成：
  - 问题分析：原推荐资源侧边栏是静态 Mock，无法根据当前对话上下文推荐相关课程学习资源。
  - 修复：
    1. 引入 `Link` 及 `learningService`。
    2. 新增 `resources` 状态并在 `activeCourseId` 变化时，调用 `learningService.getResources` 拉取当前课程的全部资源（使用 `setTimeout` 规避 `useEffect` 同步设置 state 的 lint 警告）。
    3. 新增 `getActiveKnowledgePoints` 辅助方法过滤出消息历史中最新的 AI 知识点。
    4. 根据活跃知识点 `activeKPs` 过滤 `resources` 得到推荐列表（若无活跃知识点则默认推荐全部，否则按知识点名或标题匹配）。
    5. 右侧 aside 渲染根据推荐资源列表动态生成卡片链接，针对不同资源类型（document, mindmap, reading, code, video）展示对应图标与配色，并在为空时渲染美观的空状态。
  - 契约说明：复用已有的 `GET /resources` 及资源详情跳转，符合契约约定。
  - 验证：
    - `npm run lint` 通过。
    - `npm run build` 成功。
    - `npx playwright test e2e/specs.spec.js -g "AI Chat renders historical messages"` 通过。

- AIChat 页面侧边栏响应式折叠与滑出抽屉重构完成：
  - 问题分析：原侧边栏采用固定隐藏/显示样式，导致移动端完全无法访问历史记录与学习资源，且在桌面端无法由用户收拢以获得更宽的聊天窗口。
  - 修复：
    1. 引入 4 个 React 状态量：`leftCollapsed` (左收起)、`rightCollapsed` (右收起)、`leftDrawerOpen` (左侧滑栏打开)、`rightDrawerOpen` (右侧滑栏打开)。
    2. 顶部 Header 栏添加 Hamburger 和 `menu_book` 按钮，分别作为左右侧滑栏的呼出开关。
    3. 左右侧边栏 `<aside>` 容器重构：结合 Tailwind CSS 实现平滑的折叠与滑出动画，使用内部包裹容器 `min-w-[256px]` / `min-w-[288px]` 隔离宽度变化导致的内容挤压，折叠时隐藏边框和阴影。
    4. 增加 Backdrop 遮罩层以支持点击空白处关闭侧滑栏；新增选取历史会话、重置新建对话时的自动关闭 Drawer 联动。
  - 契约说明：纯前端布局优化，不涉及 API 契约漂移。
  - 验证：
    - `npm run lint` 通过。
    - `npm run build` 成功。

- Tutoring 快速链路 + 异步 review 事件重构完成。
  - 已完成：删除同步 LLM critic、chat fallback、策略 LLM 分支；`generate_tutoring_sse_events` 改为 Retrieval -> ReAct -> 规则 Guard -> 最多一次 ReAct 重试 -> 规则兜底；`done` 之后按规则审查结果可选发送 `review` 事件。
  - 个性化：ReAct prompt 保持长期记忆优先于课程知识；含 `knowledge_weak` 词条的 course chunk 稳定上浮，不丢 chunk。
  - 前端：`chat.js` 显式透传 `review`；`AIChat.jsx` 在 `done` 后记录最终消息 id，`review` 到达时给对应 AI 消息打 `reviewFlagged`；`ChatMessage.jsx` 将整条 AI 回答标灰并提示“该回答可能不准确”。
  - 契约：Client API OpenAPI / 接口规范已包含 `review` SSE 事件；Agent Service OpenAPI 补齐既有 `TutoringChatRequest.active_kg_nodes` 字段，修复 schema 对齐测试漂移。
  - 验证：
    - `../.venv/bin/python -m pytest tests/ -k "tutoring or retrieval_personalization or review_event" -v -p no:cacheprovider` 通过，77 passed。
    - `../.venv/bin/python -m pytest tests/test_aichat_hybrid_retrieval.py -v -p no:cacheprovider` 通过，6 passed。
    - `npm run lint` 通过。
    - `npm run build` 通过，仍有既有 Vite chunk size warning。
    - `python3 -c "import json; json.load(open('docs/10-client-api/Client-API.openapi.json')); json.load(open('docs/20-agent-api/Agent-Service.openapi.json')); print('OK')"` 通过。

- 修复 AI Chat Hybrid Retrieval 的过度完成问题。
  - 引入了 `retrieval_debug` 隔离探针调试信息。
  - 实现了 `_match_kg_nodes` 的 Substring -> Reranker -> Embedding 降级打分机制。
  - 确保提示词不再机械复读所有 KG 节点。
  - 更新探针命令行支持 `--catalog-id`。
  - 测试全部通过。当前状态回调至“真实 Hybrid 闭环待验证”。

- 2026-06-14：Task 4 - AI Chat Hybrid Retrieval Regression Suite:
  - 任务：为 AI Chat 混合检索建立集成回归测试。
  - 修复：在 `agent_service/tests/test_aichat_hybrid_retrieval.py` 新增回归测试集，模拟 CLI 探针逻辑，使用 C 语言样本（指针、数组、malloc）结合 mock 的 KG 节点、embedding 和 vector store 来测试 `build_tutoring_retrieval_context_with_ai` 函数。
  - 契约说明：仅新增测试用例，不涉及 API 契约或实现的修改。
  - 验证：
    - 运行 `uv run pytest agent_service/tests/test_aichat_hybrid_retrieval.py -q`，3/3 passed。
- 2026-06-13：AIChat 页面 3-Column 布局与 Document-style 重构：
  - 问题分析：原 AIChat 仅支持纯文本显示及简单的图解代码块，长回答体验沉闷，且无法直观展示复杂任务（如工具调用）的执行过程。页面布局未体现出“课程上下文”与“推荐资源”的作用，只是一个简单的聊天界面。
  - 修复：
    1. 新增 `ChatMessage.jsx` 与 `ToolCallCard.jsx`。引入 `react-markdown`、`react-syntax-highlighter` 和 `remark-gfm` 支持完整的 Markdown 渲染与代码高亮（带有一键复制）；并为后续展示多智能体思考/调用留出可折叠的 `ToolCallCard` 组件。
    2. 新增 `ChatEmptyState.jsx`，提供 4 种初始场景卡片（解释知识点、分析代码、推荐资源、规划复习），支持点击直接发送。
    3. 重构 `AIChat.jsx` 布局为 3-column 结构：左侧“历史记录”列表，中间为会话区（输入框固定底部且支持自适应高度），右侧展示“相关资源推荐”与当前学习上下文（CourseName）。
  - 契约说明：纯前端 UI 升级，复用现有 API 字段（`content`, `suggestions`, `knowledge_points`, `diagrams`），不存在后端或契约漂移。
  - 验证：
    - Frontend `npm run lint` 通过（清理了所有不再使用的变量，如旧版静态数据）。
    - 确保 `npm run build` 通过。
- 2026-06-13：个人资料页接入静默同步画像：
  - 赛题口径确认：个人画像应分为“对话式画像构建”和“随学随新静默更新”；不把 `/profile/refresh` 做成用户输入 prompt。
  - 修复：`StudentProfile.jsx` 在六维画像区新增“同步画像”按钮，调用 `POST /profile/refresh` 创建 `profile_refresh` task，轮询 `GET /tasks/{task_id}`；`completed` 后重新拉取 `GET /profile`，`failed/partial` 显示错误且不覆盖旧画像。
  - 保留：原“补充学习画像”输入框继续走 `POST /profile/dialogue-update`，用于学生主动补充学习目标、薄弱点和资源偏好。
  - 契约说明：未修改 OpenAPI / Client API；复用已有 `/profile/refresh`、`/tasks/{task_id}` 和 `profile_dimensions`。
  - 验证：
    - Frontend `npm run lint` 通过。
    - Frontend `npm run build` 通过，仍有既有 Vite chunk size warning。
- 2026-06-13：Admin 保底题库拆分请求兜底：
  - 根因确认：最新真实父任务 `852bd3532a9d448a` 为 `partial`，`20` 个节点中 `4` 成功、`16` 个子任务因 `skeleton_rejected` 失败；失败点已不在前端数量或 quality gate，而是 Agent 单节点一次生成 `7` 题时未产出有效题，降级骨架后被 Backend 过滤。
  - 修复：Backend 保留原单节点 `7` 题批量请求；当批量结果全为骨架 / 无有效题时，自动拆成 `single_choice count=3` 与 `multi_choice count=4` 两次小请求，分别过滤骨架后落库；多选答案落库改为稳定逗号格式（如 `A,C`），避免 Python list 字符串进入判分链路。
  - 契约说明：未改变 Client API 路径、请求体、响应字段、任务类型或状态枚举；未改变 Agent API 路径或字段，仅调整 Backend 调用粒度。
  - 验证：
    - Backend RED：新增 `test_admin_catalog_quiz_child_splits_large_mixed_request_when_batch_returns_skeleton`，修复前按预期失败（当前实现直接 `skeleton_rejected`）。
    - Backend MySQL `tests/test_admin_catalog_resource_generation.py` 28/28 passed。
    - Backend MySQL `tests/test_quiz_async.py` 1/1 passed。
- 2026-06-13：Quiz 前端题型渲染收口（单选/多选）：
  - 根因确认：`Quiz.jsx` 原先把所有题都按单选处理，题型标签只识别 `single_choice`，答案状态固定为单值，选项控件固定为 `radio`；因此保底题库里的 `multi_choice` 题虽然能被后端返回，但前端不能正确作答。
  - 修复：新增 `src/components/quiz/` 下的题型分发层，`QuestionRenderer` 按 `question.type` 分发到 `SingleChoiceQuestionCard`、`MultiChoiceQuestionCard` 或 `UnsupportedQuestionCard`；`Quiz.jsx` 的答案状态改为按题型保存 `string | string[]`，提交时原样透传；取题 `useEffect` 补入 `node_id` 依赖，并在切题时重置题目索引和答案状态。
  - 扩展口径：当前仅正式支持 `single_choice` 与 `multi_choice`；未来 `code` 等题型已有明确前端扩展点，但本轮不接入 UI 主流程。
  - 验证：
    - Frontend `npm run lint` 通过。
    - Frontend `npm run build` 通过，仍有既有 Vite chunk size warning。
- 2026-06-13：Admin 保底题库 `partial` 终态前端修复：
  - 根因确认：真实开发库 C 语言资源库父 `quiz_generation` 任务 `8adbdc49dd2f400a` 已在 `2026-06-13 03:11:55` 完成，状态为 `partial`，汇总 `20` 个节点中 `8` 成功、`12` 失败、共生成 `56` 题；前端 `CourseCatalogDrawer.jsx` 轮询只把 `completed/failed` 当终态，导致按钮一直显示“生成中”。
  - 修复：题库生成状态文案补齐 `partial -> 部分失败`；题库轮询把 `partial` 视为终态，停止轮询并恢复“生成题库”按钮可点击；状态卡片显示部分失败时的节点/题目汇总。
  - 契约说明：本轮按工作区约束未修改 `../docs/10-client-api/*`，因此 `/tasks/{task_id}` 对 `partial` 的文档漂移仍存在，后续如要收口需单独走契约更新。
  - 验证：
    - Frontend `npm run build` 通过，仍有既有 Vite chunk size warning。
    - Frontend `npm run lint` 退出码为 0；存在既有 warning：`src/pages/Quiz.jsx` `react-hooks/exhaustive-deps` 缺少 `nodeId` 依赖，非本轮引入。
    - 尝试新增 Playwright 回归 `npm run test:e2e -- e2e/specs.spec.js -g "Admin baseline quiz generation stops polling on partial task status"`，当前环境下卡在 `page.goto('/admin')` 导航超时，已撤回该不稳定测试，避免把失败用例留在工作区。
- 2026-06-12：资源库 KG 宿主课兼容层落地：
  - Backend `CourseCatalog` 新增 `kg_host_course_id`，通过 `backend/migrations/2026-06-12-add-catalog-kg-host-course-id.sql` 持久化资源库对应的隐藏宿主课。
  - Admin `POST /admin/course-catalogs/{catalog_id}/knowledge-graphs/generations` 不再要求资源库先绑定真实教学班；当资源库尚无宿主课时，Backend 会创建或复用隐藏宿主课，并基于该宿主课生成 active KG。
  - Admin `GET /admin/course-catalogs/{catalog_id}/knowledge-graphs` 改为按资源库宿主课读取 active KG 和任务状态；未绑定教学班的新资源库不再固定显示“资源库尚未绑定教学班 / 暂无 active 知识图谱”。
  - Backend `/courses` 教师列表、学生列表和 `POST /courses/join` 已显式过滤 KG 宿主课，避免隐藏宿主课出现在真实课程流、课程码加入流和学生可见课程列表中。
  - Frontend `CourseCatalogDrawer.jsx` 的 KG 区文案改为资源库中心口径：空态显示“当前资源库暂无 active 知识图谱”，生成完成后显示“当前显示的是该资源库的 active 知识图谱”。
  - 验证：
    - Backend MySQL `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/host_course_transition_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_kg_generation.py::test_catalog_kg_generation_reuses_existing_hidden_host_course_when_no_offering tests/test_admin_catalog_kg_generation.py::test_catalog_kg_generation_without_offering_returns_202_not_40915 tests/test_admin_catalog_kg_generation.py::test_catalog_kg_generation_creates_hidden_host_course_with_long_catalog_title tests/test_admin_catalog_kg_generation.py::test_catalog_kg_generation_truncates_hidden_host_course_name_for_long_catalog_title tests/test_admin_catalog_kg_generation.py::test_admin_catalog_kg_generation_rejects_duplicate_processing_task tests/test_admin_catalog_kg_generation.py::test_catalog_kg_status_reads_active_graph_from_host_course tests/test_courses_async.py -q -p no:cacheprovider` 7/7 passed。
    - Frontend `npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog KG generation refreshes active graph from declared endpoint"` 1/1 passed。
    - Frontend `npm run lint` 通过。
    - Frontend `npm run build` 通过，仍有既有 Vite chunk size warning。
- 2026-06-12：资源消费模型切换为资源库中心共享：
  - Backend `Resource` 新增 `catalog_id` 归属字段；Admin 资源库级生成和教师历史 `/resources/generate` 的 webhook 落库不再按 `fanout_course_ids` 为每个教学班写多份资源，而是只写一份资源库共享资源，`course_id` 仅保留首个绑定教学班作为兼容字段。
  - `GET /resources`、`GET /resources/{id}`、`GET /learning-path/nodes/{node_id}/resources`、evaluation/profile 里的资源统计统一改为：先校验当前 `course_id` 的教学班访问权限，再解析绑定 `catalog_id`，优先读取 `Resource.catalog_id = catalog_id` 的共享资源，同时兼容当前教学班下 `catalog_id IS NULL` 的 legacy 资源。
  - Admin 资源列表改为聚合资源库共享资源，并兼容同 catalog 绑定班级下仍未迁移的 legacy 资源。
  - Frontend `TeacherConsole.jsx` 持久展示课程码并提供复制入口；`CourseContext.jsx` 在当前用户无课程时清空 `activeCourseId` 和本地 `course_id`，修复未加入课程学生因残留上下文误见资源的问题；Admin 资源区文案改为“教学班绑定资源库 / 资源库共享资源”口径。
  - 迁移文件：`backend/migrations/2026-06-12-add-resource-catalog-id.sql`。
  - 契约注意：本轮修改了 Backend 资源读取/归属语义，但按工作区约束未改 `../docs/10-client-api/*`；当前代码与外部 Client API 文档存在待同步漂移。
  - 验证：
    - Frontend `npm run test:e2e -- e2e/specs.spec.js -g "Student dashboard clears stale course context when current user has no courses|Teacher console shows catalog-bound class resources and opens detail"` 2/2 passed。
    - Frontend `npm run lint` 通过。
    - Frontend `npm run build` 通过，仍有既有 Vite chunk size warning。
    - Backend `../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py tests/test_resource_detail.py tests/test_node_resources.py -q -p no:cacheprovider` 26/26 passed。
- 2026-06-12：Admin KG 刷新补齐 backend LLM 配置读取：
  - 根因确认：`backend/app/services/kg_generation.py` 直接读取 `os.environ["LLM_API_KEY"]`，而不是统一走 backend `Settings`；在某些启动方式下即使 `backend/.env` 有值，`kg_generation` 后台任务仍会因为进程环境未导出 `LLM_API_KEY` 而失败，前端显示 `task_id=94f2e75b5d3a4fe9`、`status=失败`、`progress=100%`。
  - 修复：`backend/app/core/config.py` 补齐 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`，`backend/app/services/kg_generation.py` 改为优先读进程环境、缺失时回退到 backend `settings`；`start_all.sh` 启动 backend 前增加 `. ./.env` 导出，避免本地联调再次因环境未注入而失败。
  - TDD：新增 `backend/tests/test_generate_kg.py::test_generate_kg_from_llm_uses_backend_settings_when_env_missing`，先验证现状无 `settings` 入口会失败，再以最小实现修复。
  - 契约：未修改 Client API、未修改 Agent API、未新增字段或错误码。
  - 验证：Backend `../.venv/bin/python -m pytest tests/test_generate_kg.py -q -p no:cacheprovider` 12/12 passed；Backend MySQL `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/admin_catalog_kg_generation_task1?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_kg_generation.py -q -p no:cacheprovider` 15/15 passed；Frontend `npm run build` 通过，仍有既有 Vite chunk size warning。
- 2026-06-12：Admin 自动 KG 与资源挂载主流程调整：
  - Backend `POST /admin/course-catalogs/{catalog_id}/knowledge-graphs/generations` 支持空请求体，默认 `source_type=catalog_chunks`、`activate=true`，从 Qdrant `course_knowledge_v1_1024` 按 catalog_id scroll 读取知识切片，拼接上下文后复用 LLM KG 生成与版本落库。
  - 自动 KG 增加前置校验：必须已绑定 CourseOffering，资源库 `knowledge_status in ready/partial` 且 `chunk_count > 0`；新增 / 同步错误码 `knowledge_base_not_ready`、`knowledge_base_empty`、`kg_context_empty`、`llm_kg_generation_failed`。
  - Frontend `CourseCatalogDrawer.jsx` 移除“大纲文本 / KG JSON / 设为 active”主流程输入，保留“刷新图谱”、active KG 摘要和任务状态；生成学习资源区在有 active KG 且未手动填目标时提示“将按 KG 节点自动生成并挂载资源”，无 active KG 时禁用默认自动生成。
  - Client API OpenAPI 与 Markdown 已同步：KG generation 请求体改为可空，`catalog_chunks` 为默认来源；`kg_json` 保留后端调试兼容但不在 Admin UI 暴露。
  - 验证：Backend MySQL `tests/test_admin_catalog_kg_generation.py` 15/15 passed；Backend MySQL KG + 资源生成回归 `tests/test_admin_catalog_kg_generation.py tests/test_admin_catalog_resource_generation.py` 38/38 passed；Frontend `npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning；Playwright `Admin course catalog KG generation|Admin course catalog resource generation` 2/2 passed；OpenAPI JSON 语法检查通过。
- 2026-06-12：Admin 预置账号登录修复：
  - 根因确认：`schema.sql` 中 `admin@admin.com / Admin123456` 的预置 bcrypt hash 与注释密码不匹配，`verify_password("Admin123456", schema_hash)` 返回 false；当前开发库手动插入账号复用了这条错误 hash。
  - 额外数据问题：当前 MySQL `duagent.users` 中 `admin@admin.com` 曾为 `is_active=0`，即使密码修对也会被禁用检查拒绝。
  - 修复：替换 `schema.sql` 预置 admin hash，并对开发库 `admin@admin.com` 更新 `password_hash`、`is_active=1`、`is_deleted=0`、`role='admin'`。
  - 回归：新增 `tests/test_security_password_hash.py`，覆盖当前 bcrypt backend 下 `hash_password -> verify_password` 和 schema 预置 hash 必须匹配 `Admin123456`。
  - 说明：`passlib==1.7.4` + `bcrypt==4.1.3` 仍会打印 `bcrypt.__about__` warning，但当前验证显示有效 hash 可正常通过，不是本次登录失败主因；后续如要消除日志噪声，可单独评估 pin `bcrypt<4.1` 或迁移密码库。
  - 验证：Backend `../.venv/bin/python -m pytest tests/test_security_password_hash.py -q -p no:cacheprovider` 2/2 passed；ASGITransport + MySQL `duagent` 真实调用 `/auth/captcha` + `/auth/login`，`admin@admin.com / Admin123456` 返回 `login_status=200`、`role=admin`、`has_token=True`。
- 2026-06-11：Admin 课程资源库 KG 生成入口接入完成：
  - Backend 新增 Admin KG 生成服务与接口：`GET /admin/course-catalogs/{catalog_id}/knowledge-graphs`、`POST /admin/course-catalogs/{catalog_id}/knowledge-graphs/generations`，通过 `CourseOffering` 解析绑定 course，创建 `kg_generation` AsyncTask，任务完成后写入新的 `course_knowledge_graphs` 版本。
  - CLI `tools/generate_knowledge_graph.py` 已复用同一套 KG 生成 / 校验 / 保存服务，避免 CLI 与 Admin API 双实现漂移。
  - Client API OpenAPI 与 Markdown 已补齐 KG status / generation 契约，并把 `kg_generation` 纳入 `/tasks/{task_id}` 轮询任务类型。
  - Frontend `CourseCatalogDrawer.jsx` 新增“知识图谱”区：打开抽屉加载 active KG 状态，可输入大纲文本或 KG JSON 手动刷新 active KG，独立轮询 `kg_generation` task，完成后刷新图谱摘要。
  - 本轮不接学生个性化图谱刷新，不把 KG 生成塞进资源生成接口；Admin 需要先刷新 KG，再按现有资源生成入口生成 KG-node 资源。
  - 验证：Backend MySQL `tests/test_admin_catalog_kg_generation.py` 13/13 passed；Backend MySQL 资源生成 / KG 版本回归 23 passed / 1 skipped；CLI 回归 `tests/test_generate_kg.py` 11/11 passed，MySQL combo 28 passed；Frontend `npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog KG generation"` 1/1 passed；`Admin course catalog resource generation` 1/1 passed；`Admin course catalog ingestion` 1/1 passed；`npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning。
- 2026-06-11：KG 生成入口产品记录：
  - 当前 Admin 资源生成接口不会自动生成 KG；不传 `chapter/knowledge_point` 时只消费绑定教学班已有 active KG，并自动选择核心 KG 节点生成资源。
  - 清库重导后，若 catalog 已入库 ready 且已绑定教学班，但 `course_knowledge_graphs` 没有 active KG，资源生成会返回父任务失败 `kg_not_ready / 课程知识图谱未就绪`。
  - 后续产品化建议不是在资源生成里静默补 KG，而是新增独立 Admin “生成知识图谱”入口和任务状态：先 KG generation，完成后再允许 KG-node 资源生成；这样任务边界、失败提示和重复点击幂等更清晰。
  - 本轮手动处理：新 C catalog `dbf6306dbe8746be` 已 ready，绑定 course `cc451af9bdb24f51`；LLM 大纲抽取命令因模型调用失败未生成，随后用旧 C 语言 KG JSON `/tmp/kg-resource-probe/c-language-active-kg-v1.json` 导入新 course，创建 active KG `bf9b8704e2da4ec1`，`116` nodes / `115` edges。
- 2026-06-11：开发库业务数据清空并保留管理员账号：
  - 按用户确认执行开发环境清库，用于重新导入 C 语言样本并排除历史 dirty/chunk/Qdrant 残留干扰。
  - MySQL `duagent` 清空业务表：`course_catalogs`、`course_catalog_materials`、`course_offerings`、`courses`、`resources`、`course_knowledge_graphs`、`learning_paths`、`async_tasks`、Quiz/Profile/Evaluation/Conversation 等均精确 `COUNT(*)=0`。
  - `users` 表保留所有 `role='admin'` 且未删除账号，当前剩余 `42` 个管理员用户；未保留教师/学生/注册邀请码。
  - Qdrant 已删除 `course_knowledge_v1_1024` collection，`GET /collections` 返回空列表。
  - `backend/storage/course_catalogs` 下旧上传资料目录已清空。
  - 注意：首次核验 `information_schema.tables.table_rows` 仍显示旧估算值，这是 InnoDB 统计延迟；后续用逐表 `COUNT(*)` 确认为 0。
  - 下一步：重启 Backend/Agent 后，用保留的 admin 账号重新创建 C catalog、上传资料、入库、生成 KG、生成 KG-node 资源，再生成 / 评估 LearningPath。
- 2026-06-11：Admin 删除 CourseCatalog 资料后 catalog chunk/status 一致性修复：
  - 根因：`DELETE /admin/course-catalogs/{catalog_id}/materials/{material_id}` 只软删除 material 并重算 `material_count`，没有按剩余未删除 material 重算 `catalog.chunk_count`；旧测试还固化了“删除资料不改变 chunk_count”的错误期望。
  - 修复：删除资料后按剩余未删除 `CourseCatalogMaterial.chunk_count` 重新计算 `catalog.chunk_count`，并保持 `ready/partial -> dirty` 的状态转换；不改入库流程，不清理 Qdrant，不新增 Client API。
  - 测试：更新 Admin 删除资料回归，要求删除最后一个带 chunk 的有效资料后 `material_count=0`、`knowledge_status=dirty`、`chunk_count=0`；补充 repair recheck 测试，确认无有效 material 时 `repairable=false` 且原因包含 `materials_missing/material_chunks_missing`。
  - 验证：`TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_version_service_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py::test_admin_soft_deletes_material_marks_catalog_dirty_and_recalculates_chunks tests/test_course_catalog_knowledge_repair.py -q -p no:cacheprovider` 6/6 passed。
  - 真实 C catalog 只读 check：`b2444963f0e54587` 当前仍是历史不一致数据，`knowledge_status=ready`、`catalog_chunk_count=665`，但未删除 material `material_chunk_count=0`；repair check 返回 `repairable=false`，原因 `knowledge_status_not_dirty`、`material_chunks_missing`。后续继续 LearningPath 前，需要单独修正开发库这条数据或重新上传有效资料并入库。
- 2026-06-11：LearningPath-KG 资源命中评估 probe 接入并跑真实 C 样本基线：
  - 新增 Backend 只读评估服务 `app/services/learning_path_resource_probe.py`，复用现有 LearningPath 节点资源接口口径：LearningPath 节点按 `node_id` 匹配 active KG 节点，知识点资源按 `Resource.knowledge_point == node_name`，章节材料按 active KG `chapter`，练习按 `QuizQuestion.knowledge_point == node_name`。
  - 新增 CLI `tools/probe_learning_path_resources.py`，支持 `--catalog-id`、`--course-id`、`--user-id`、`--out` 导出 JSON，用于 LearningPath ready gate 前的只读评估。
  - 单测覆盖：active KG 两个节点、LearningPath 三个节点，其中两个匹配 KG，一个路径独有；确认非删除资源、章节资源、练习、KG tag 汇总和空节点统计正确。
  - 真实 C catalog `b2444963f0e54587` / course `6c698badb60a4809` 已跑基线报告 `/tmp/learning-path-resource-probe-c-language.json`：`active_kg_node_count=108`、`resource_count=84`、`kg_tagged_resource_count=80`，但 `learning_path_id=null`、`learning_path_node_count=0`。
  - 只读 MySQL 复核：该 course 当前 `learning_paths` 非删除记录数为 `0`；因此当前不能判定 LearningPath 节点资源挂载质量，也不能进入 LearningPath ready gate 设计。
  - 验证：`TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/learning_path_resource_probe_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_learning_path_resource_probe.py -q -p no:cacheprovider` 1/1 passed；CLI `--help` 通过；真实只读 probe 命令通过。
- 2026-06-11：CourseCatalog knowledge_status repair + KG-node 资源生成真实闭环：
  - 新增 Backend 维护能力：`app/services/course_catalog_knowledge_repair.py` 和 `tools/repair_course_catalog_knowledge_status.py`，支持只读 recheck 与 `repair --apply`；只在 `status=ready`、`knowledge_status=dirty`、非删除资料全部 `ingested`、catalog/material chunk 正常、Qdrant 能按 catalog_id 查到 chunk 时执行 `dirty -> ready`。
  - 不修改第 527 行新增资料标 dirty 逻辑；该逻辑属于新增资料后的正确状态转换。本轮未新增 Client API，未改 OpenAPI。
  - 真实 C catalog `b2444963f0e54587` 只读检查：`material_count=2`、`ingested_material_count=2`、`material_chunk_count=663`、`catalog_chunk_count=665`、Qdrant probe 命中，`repairable=true`。
  - 已执行 `repair --apply`：`knowledge_status dirty -> ready`，不删除材料、不重建、不重复入库。
  - 调用 Admin 资源库级资源生成接口，不传 `chapter/knowledge_point`，父任务 `d364a3a0af294dfa` 进入 `kg_node_targets` 模式，选中 10 个 KG 核心节点，fan-out course `6c698badb60a4809`；最终父任务 `completed`，`completed_child_count=10`、`failed_child_count=0`、`successful_node_count=10`。
  - KG-Resource probe 导出 `/tmp/kg-resource-probe-after-repair-generation.json` 共 `108` 行；汇总结果 `gt0=108`、`zero=0`、`max=4`，即 active KG 节点候选从全 0 变为全量有候选。
  - 验证：`TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/course_catalog_repair_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_course_catalog_knowledge_repair.py -q -p no:cacheprovider` 4/4 passed；`TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_version_service_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py tests/test_course_catalog_knowledge_repair.py -q -p no:cacheprovider` 27/27 passed。
- 2026-06-11：Route A 可用阈值版 KG-Resource 对齐探针复验：
  - 重新盘点 `/tmp/kg-resource-probe/inventory-after-route-a-usable.json`：C 语言 catalog `b2444963f0e54587` / course `6c698badb60a4809` 已具备正式探针条件，`chunk_count=665`、`kg_node_count=108`、`resource_count=4`、`eligible_for_formal_probe=true`。
  - 导出正式探针 `/tmp/kg-resource-probe/c-language-route-a-usable-kg-resource-probe.csv`，共 `108` 行，全部来自 active KG。
  - 探针结果：`candidate_count=0` 的节点 `108/108`，即新版 KG 节点虽然正文支撑明显改善，但当前资源挂载规则仍无法命中任何资源或题目。
  - 只读核验资源元数据：当前 4 个课程资源全部为 `chapter=课程整体`、`knowledge_point=综合知识点`，而 KG 节点是具体章节/知识点；零命中原因是资源生成 metadata 粒度与 KG 节点体系不一致，不是 KG active 版本未生效。
  - 验证：`DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/duagent?charset=utf8mb4 ../.venv/bin/python tools/probe_kg_resource_alignment.py inventory --format json --out /tmp/kg-resource-probe/inventory-after-route-a-usable.json` 通过；同库 `probe --catalog-id b2444963f0e54587 --course-id 6c698badb60a4809 --sample-mode all --format csv` 通过。
  - 附注：`../.venv/bin/python -m pytest tests/test_kg_resource_alignment_probe.py -q -p no:cacheprovider` 在当前工具会话中无结果输出，但进程表确认无 pytest 子进程残留；本次结论基于只读 MySQL probe 命令和导出 CSV。
- 2026-06-11：Route A 可用正文支撑阈值实现并生成新 active KG：
  - Backend Route A 裁剪默认线从强支撑 `0.70` 调整为可用支撑 `0.60`，并保留 `strong/good/weak_but_usable/unsupported` 分档 metrics。
  - `body_support_pass_ratio` 继续按传入阈值计算；`usable_support_ratio` 固定按 `0.60` 计算，避免后续 ready gate 把 weak support 当作 strong support。
  - CLI `--grounding-threshold` 默认改为 `0.60`；默认 Route A 版本写入 `generation_strategy=route_a_prune_usable_060`，显式非 `0.60` 阈值仍写 `route_a_prune_unsupported`。
  - 真实 C 语言样本已在开发库 `duagent` 生成新 active KG：`graph_id=27c3acb1e98a49d1`，`version=3`，`108` nodes / `100` edges，明显高于旧 Route A `22` nodes / `2` edges。
  - metrics 核验：`candidate_node_count=116`、`kept_node_count=108`、`pruned_node_count=8`、`body_support_pass_ratio=0.9310344827586208`、`support_band_counts={strong:57, good:34, weak_but_usable:17, unsupported:8}`。
  - `pruned_nodes` 详细列表暂保留，未来大图需要做限长或外部诊断产物。
  - 验证：Backend `../.venv/bin/python -m pytest tests/test_kg_body_grounding.py tests/test_generate_kg.py -q -p no:cacheprovider` 19/19 passed；MySQL versioning 回归 8/8 passed；真实生成命令成功。
- 2026-06-11：KG residual TOC/index 过滤漏网小补丁完成：
  - 按补点决策文件中的 `filter_review_first` 结论，增强 Agent Service KG grounding 过滤，新增英文索引页码串、单行稀疏点线页码、`索引/目录 + 点线/页码` 噪声识别。
  - TDD 覆盖：`expression ...，52，200` 这类英文索引、`...30 1.5.1 文件复制 ...31` 单行点线目录、`252 索引 ...` 尾部索引残留均会 fallback 到下一个正文候选。
  - 真实 C 语言样本复验：`/tmp/kg-resource-probe/c-language-route-a-grounding-filtered-expanded-best-v3.json`；原 7 个 `residual_toc_or_index_noise` 节点均换成非索引候选，但整体 `>=0.70` 仍为 `57/116=49.14%`，说明过滤漏网已清理，下一步仍需正文补点/聚类。
  - 验证：Agent `./.venv/bin/pytest tests/test_kg_body_grounding.py tests/test_kg_body_grounding_tool.py tests/test_vector_store.py -q` 20/20 passed。
- 2026-06-10：KG 正文候选过滤 + query 扩展探针完成：
  - Agent Service `memory/kg_body_grounding.py` 增强目录/索引噪声过滤，新增点线页码目录、附录目录/索引识别；`tools/kg_body_grounding.py` 新增可选 `--query-expansion`，默认行为不变。
  - query 扩展策略不是替换单节点名，而是同时检索 `node.name` 和 `chapter + node_name + 相邻节点名`，取最高正文候选，避免已支持节点回退。
  - 真实 C 语言样本复验：baseline `22/116=18.97%`；仅过滤后 `18/116=15.52%`（纠正目录误判但不提分）；过滤 + query 扩展取最优后 `57/116=49.14%`，baseline `0.65-0.70` 的 49 个边缘节点有 23 个过线，且无已支持节点回退。
  - 结论：第 1、2 步有效但仍未达到固定成功线 `>=70%`；下一步应进入正文补点 / 正文聚类策略设计，不继续调阈值。
  - 验证：Agent `./.venv/bin/pytest tests/test_kg_body_grounding.py tests/test_kg_body_grounding_tool.py tests/test_vector_store.py -q` 19/19 passed；真实探针输出 `/tmp/kg-resource-probe/c-language-route-a-grounding-filtered.json`、`/tmp/kg-resource-probe/c-language-route-a-grounding-filtered-expanded-best.json`。
- 2026-06-10：Route A no-go 归因完成：
  - 已分析 `/tmp/kg-resource-probe/c-language-route-a-grounding.json` 的 116 个节点 grounding 结果。
  - 分数分布：`>=0.70` 22 个；`0.65-0.70` 49 个；`0.60-0.65` 33 个；`<0.60` 12 个；无候选 0 个。
  - 启发式归类：`toc_or_index_noise` 47 个、`near_threshold_body_match` 21 个、`low_score_body_match` 17 个、`near_threshold_unclear` 6 个、`low_score_or_wrong_candidate` 3 个、`supported` 22 个。
  - 结论：no-go 不是资料缺失，主要是目录/索引噪声仍进入候选、单节点名 query 太弱、目录候选直接裁剪会把 KG 变成碎片图。下一步先加强正文候选过滤和 query 扩展探针，再决定是否做正文补点 / 正文驱动候选生成。
  - 归档报告：`docs/superpowers/specs/2026-06-10-route-a-no-go-attribution-report.md`。
- 2026-06-10：Route A 真实 C 语言样本闭环验收：
  - 已对开发库 `duagent` 执行已提交迁移 `backend/migrations/2026-06-10-version-course-knowledge-graphs.sql`，旧目录版 KG 成为 `version=1,is_active=1`，`116` nodes / `115` edges。
  - 从 active KG 导出 `/tmp/kg-resource-probe/c-language-active-kg-v1.json`，用 Agent CLI 真实检索 Qdrant catalog `b2444963f0e54587`，输出 `/tmp/kg-resource-probe/c-language-route-a-grounding.json`。
  - Grounding 结果：`116` 节点中 `body_top1_score>=0.70` 的节点 `22` 个，占比 `18.97%`，median `0.6618`，未达到跑前固定成功线 `>=70%`。
  - Backend CLI 用 `--kg-json /tmp/kg-resource-probe/c-language-active-kg-v1.json --grounding-file /tmp/kg-resource-probe/c-language-route-a-grounding.json` 创建 Route A 新 KG：`graph_id=1801d8e677d04a43`，`version=2,is_active=1`，`source_type=route_a_body_grounded`，`generation_strategy=route_a_prune_unsupported`，`22` nodes / `2` edges，parent 指向旧 `f36b0d8580724805`。
  - 数据库只读核验：version 1 已 inactive，version 2 active，`metrics.body_support_pass_ratio=0.1896551724137931`、`kept_node_count=22`、`pruned_node_count=94`。
  - 结论：Route A 第一版“只裁剪无支撑节点”工具链可跑通，但真实样本验收 **no-go**；KG 生成还不能算完成。下一步不是测试收尾，而是改生成策略：分析被裁剪节点和正文覆盖，推进正文补点 / 更稳的正文驱动候选生成。
  - 额外修复：`backend/tools/generate_knowledge_graph.py` 增加 `--kg-json`，避免真实闭环重新调 LLM 导致 grounding 节点 id 不匹配；CLI 结束时显式 `engine.dispose()`，收口 aiomysql event loop closed 噪声。
  - 验证：Backend `../.venv/bin/python -m pytest tests/test_generate_kg.py tests/test_kg_body_grounding.py -q` 15/15 passed；Backend MySQL `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_version_service_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_kg_cli_versioning.py tests/test_course_knowledge_graph_versions.py -q -p no:cacheprovider` 8/8 passed。
- 2026-06-10：KG 版本化与 Route A 工具链阶段性接入：
  - 已完成 KG 版本 / 回滚基础设施：`course_knowledge_graphs` 支持 `version/is_active/source_type/generation_strategy/metrics/parent_graph_id`，LearningPath 默认读取 active KG，`generate_knowledge_graph.py` / `import_knowledge_graph.py` 不再覆盖旧 KG，而是创建版本或切换 active。
  - 已完成 Agent 侧只读正文支撑 scorer：`agent_service/memory/kg_body_grounding.py` 对 KG 节点逐个 embedding，检索 Qdrant `course_knowledge`，过滤目录型 chunk，输出 `body_top1_score/chunk_id/source_file/preview/supported`。
  - 已完成两段式 Route A 工具链：Agent CLI `agent_service/tools/kg_body_grounding.py` 导出 grounding JSON；Backend CLI `backend/tools/generate_knowledge_graph.py --grounding-file ...` 读取该 JSON，调用纯裁剪层保留正文支撑节点、裁掉悬空边，并写入 `route_a_body_grounded / route_a_prune_unsupported` 新版本。
  - 架构边界：Backend 不导入 Agent Service、不直接访问 Qdrant；Agent Service 不读写 Backend SQL；本阶段未新增 Client API / Agent HTTP API。
  - 已运行：Agent `./.venv/bin/pytest tests/test_kg_body_grounding.py tests/test_kg_body_grounding_tool.py tests/test_vector_store.py -q` 14/14 passed；Backend `../.venv/bin/python -m pytest tests/test_generate_kg.py tests/test_kg_body_grounding.py -q` 13/13 passed；Backend MySQL `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_version_service_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_kg_cli_versioning.py tests/test_course_knowledge_graph_versions.py -q -p no:cacheprovider` 8/8 passed。
  - Commits：`705ae8f 增加KG版本化表结构`、`b89449e 增加KG版本切换服务`、`c1d2575 切换KG读取为active版本`、`5404b5e 改造KG导入工具保留版本`、`33599f4 增加KG正文支撑裁剪逻辑`、`a90cac6 新增KG正文支撑度评分模块`、`0bec53e 新增KG正文支撑导出工具`。Backend Route A CLI 接入提交见本轮后续 commit。
  - 未完成：尚未对真实 C 语言 `116` 节点样本生成 Route A 新版本，也尚未重跑成功线验收；固定成功线仍是排除目录型 chunk 后 `body_top1_score>=0.70` 节点占比从 `21.6%` 提升到 `>=70%`。
- 2026-06-10：KG 生成方式真实探针与返工方向确认：
  - 真实运行现有 CLI `../backend/tools/generate_knowledge_graph.py`，对 catalog `b2444963f0e54587` 绑定教学班 `6c698badb60a4809` 生成 SQL KG：`116` 个节点、`115` 条边。该 CLI 只从外部 `--file/--outline` 大纲文本生成 KG，未自动读取 CourseCatalog 正文 chunk。
  - 资源挂载探针：`/tmp/kg-resource-probe/c-language-after-kg.csv`。20 个核心 KG 节点样本 `candidate_count=0`；当前课程 4 个资源全部是 `chapter=课程整体`、`knowledge_point=综合知识点`，与 KG 具体节点名 / 章节不在同一命名体系。
  - KG 初筛对账：116 个 KG 节点检索 665 个 Qdrant chunks，`nodes_with_exact_name_in_top5=99/116=85.3%`，但 `top1_toc_like_count=112/116=96.6%`，说明表面命中主要来自 PDF 目录 / 索引。
  - 正文支撑对账：`/tmp/kg-resource-probe/kg-to-body-chunk-probe-c-language.json`、`.csv`。跑前固定判据为“排除目录型 chunk 后，`body_top1_score>=0.70` 的节点占比 `>=70%` 才算 KG 有内容支撑”；实际 `25/116=21.6%`，`body_top1_score_median=0.668`，决策为 `toc_replica_needs_generation_rework`。
  - 正文 chunk 密度确认：`/tmp/kg-resource-probe/body-chunk-density-c-language.json`。剔除 52 个目录型 chunk 后，正文 chunk `613` 个，知识型正文 `465/613=75.9%`；第 1-8 章知识型覆盖分别为 `48/29/26/40/50/27/32/26`，决策为 `materials_dense_enough_for_route_a`。
  - 结论：资料本身够厚，不需要先补资料；当前 KG 不合格的根因是生成方式主要复刻目录、没有正文验证。暂停 KG ready gate、审核 / 签字流程、LearningPath refresh UI、资源继承 KG 节点名落地。
  - 下一步顺序：先做 KG 版本 / 回滚基础设施；再按路线 A 返工 KG 生成（目录给骨架，正文 chunk 验证节点并补充正文中真实存在的知识点）；新 KG 生成后重跑正文支撑对账和 KG-Resource 对齐探针。
  - 归档报告：`docs/superpowers/specs/2026-06-10-kg-body-grounding-probe-report.md`。
- 2026-06-10：KG-Resource 对齐探针真实盘点与校准执行：
  - 已新增只读 KG-Resource 对齐探针 service/CLI，用于盘点 catalog/course 数据、导出 KG/LearningPath 节点候选、汇总人工标注；未新增 API route，未修改前端页面，未修改 OpenAPI。
  - 当前服务状态：Backend `8001`、Agent Service `8002`、Frontend `5173` 均返回 200；MySQL、Qdrant 容器在线。探针 CLI 本身只读 MySQL，不调用 Agent Service。
  - 数据底盘盘点输出：`/tmp/kg-resource-probe/inventory.json`，共 10 个 catalog/course 组合。
  - `89f51dfbdedc4995` 盘点结果：course `59360ad8b8f445b7`，`chunk_count=1`，`kg_node_count=0`，`learning_path_node_count=0`，`resource_count=1`，`quiz_count=0`，`eligible_for_formal_probe=false`。
  - 已对 `89f51dfbdedc4995` 执行 calibration 导出：`/tmp/kg-resource-probe/89f51-calibration.csv`；导出命令成功，必需列完整，节点行数为 0。该 catalog 当前只能证明探针流程和表头可跑，不能产出命中率或 go/no-go。
  - 正式第二 catalog 选择结果：当前 inventory 中 `eligible_for_formal_probe=true` 的第二 catalog 数量为 0；因此本轮不能输出 KG-Resource 对齐 go/no-go。
  - 上线前置条件：补充或构造足量真实样本，要求 KG/LearningPath 节点可抽取 10-15 个核心节点，且资源或题目存在可匹配的 `knowledge_point` 或 `chapter` 元数据。
  - CLI 运行态修复：真实 MySQL inventory 首次暴露 `aiomysql RuntimeError: Event loop is closed` 退出噪声，已在 CLI 结束时显式 `engine.dispose()`，重跑 inventory 不再出现该警告。
  - 已运行：
    - `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_resource_probe_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_kg_resource_alignment_probe.py -q -p no:cacheprovider`：13/13 passed。
    - `../.venv/bin/python tools/probe_kg_resource_alignment.py inventory --format json --out /tmp/kg-resource-probe/inventory.json`：通过。
    - `../.venv/bin/python tools/probe_kg_resource_alignment.py probe --catalog-id 89f51dfbdedc4995 --calibration --sample-mode all --format csv --out /tmp/kg-resource-probe/89f51-calibration.csv`：通过，`wrote 0 calibration probe rows`。
    - `../.venv/bin/python` 校验 `/tmp/kg-resource-probe/89f51-calibration.csv` 必需列：`missing=[]`，`row_count=0`。
    - `../.venv/bin/python` 检查 `/tmp/kg-resource-probe/inventory.json` 正式样本候选：`eligible_count=0`。
    - `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/node_resources_probe_regression?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_node_resources.py -q -p no:cacheprovider`：1/1 passed；测试初始化补充 `engine.dispose()` 以适配 MySQL async engine。
  - Commits：`58dec7e 新增KG资源对齐探针服务`、`361b3a7 新增KG资源对齐探针命令行工具`、`988c463 修复KG探针命令连接释放`。
- 2026-06-09：CourseCatalog 资源消费闭环前端落地完成：
  - 学生端 `Dashboard.jsx` 仅把“有课程但无资源”空态文案改为“课程资源正在准备中 / 请稍后查看”，`data-testid="resources-empty"` 保留不变，无课程空态仍是“暂无课程 / 请先加入一门课程”。
  - 教师端 `TeacherConsole.jsx` 新增只读“本班学习资源”区，按当前教学班 `course_id` 调 `GET /resources?course_id=...&page=1&page_size=50`，展示绑定资源库状态、资源卡片，并可跳转现有 `/resource/:id` 详情。
  - 教师端未恢复生成 / 上传 / 删除入口，仍不调用 deprecated `/resources/generate`。
  - E2E 回归通过：`npm run test:e2e -- e2e/specs.spec.js -g "Student dashboard shows preparation copy|Teacher console shows catalog-bound class resources|Teacher console shows no-resource fallback|Teacher console does not expose"` 通过 4/4。
  - 前端检查通过：`npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning。
  - 契约检查：未修改 Backend / OpenAPI / `../docs/`，继续按班存、按班读，不引入 catalog-level resource API。
  - Commit：`998b29d 调整学生资源准备空态`、`e6421d9 新增教师只读资源面板`。
  - 剩余风险：`ResourceDetail.jsx` 仍无显式 404/403 错误态；教师资源区 E2E 存在重复路由设置，后续测试扩展时可再抽 helper。
- 2026-06-09：Admin CourseCatalog 入库 / 资源生成 / 教师绑定 / 学生消费真实多服务冒烟验收通过：
  - 真实服务：Backend `8001`、Agent Service `8002`、MySQL、Qdrant 均在线；Agent health 返回 `qdrant_connected=true`、`model_loaded=true`。
  - 首次 live smoke 暴露运行态配置问题：Agent Service 未带共享上传目录，入库 task `b09513e51aef4431` 失败，错误为 `material does not exist`。根因是 Backend 文件在 `../backend/storage/course_catalogs`，Agent 默认从自身 `storage/course_catalogs` 解析。重启 Agent 时显式设置 `COURSE_CATALOG_STORAGE_ROOT=/home/yezisama/workspace/workflow/EDUagent/backend/storage/course_catalogs` 后通过。
  - 通过正式 Client API 创建 Admin/Teacher/Student，创建资源库 `89f51dfbdedc4995`，上传真实 md 资料 `2ff62f2a34134655`，触发入库 task `d0b234d74df94822`，任务 `completed`，资源库 `status=ready`、`knowledge_status=ready`、`chunk_count=1`。
  - 教师可见 ready CourseCatalog，并绑定创建教学班 `59360ad8b8f445b7`，确认 `CourseOffering.id == Course.id`。
  - Admin 触发资源库级资源生成 task `39dfbd5feb9a4cb7`，任务 `completed`，fan-out 到课程 `59360ad8b8f445b7`，生成资源 `c9faf2f4ce304d3d`（document）和 `2ca8a6af636f4b20`（mindmap）。
  - 学生加入教学班后，`GET /resources` 可见生成资源，`GET /resources/{id}` 可打开真实内容；软删除 `2ca8a6af636f4b20` 后 Admin/Student 列表均隐藏，数据库只读核验该资源 `is_deleted=1`，未软删 document 仍保留。
  - Qdrant 只读核验：按 `course_id=89f51dfbdedc4995` 过滤 `course_knowledge_v1_1024` count 为 1。
  - 回归验证：`../.venv/bin/pytest tests/test_admin_catalog_resource_generation.py tests/test_course_catalog_ingestion.py tests/test_resources_async.py tests/test_course_catalog_ready_gate.py -q` 通过 54/54；`npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog resource generation|Teacher console does not expose"` 通过 2/2；`npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning；`python3 -m json.tool ../docs/10-client-api/Client-API.openapi.json` 通过。
- 2026-06-09：Admin 课程资源库资源生成和软删除前端接入完成：
  - `CourseCatalogDrawer.jsx` 新增 Admin-only 生成学习资源表单、生成任务独立轮询、生成资源列表、资料软删除和生成资源软删除。
  - 前端只调用已写入 Client API 的 Admin 端点：`GET /admin/course-catalogs/{catalog_id}/resources`、`POST /admin/course-catalogs/{catalog_id}/resources/generations`、`DELETE /admin/resources/{resource_id}`、`DELETE /admin/course-catalogs/{catalog_id}/materials/{material_id}`。
  - 教师端保持无生成资源入口，不调用 deprecated `/resources/generate`。
  - 验证：`npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog resource generation|Teacher console does not expose"` 通过 2/2；`npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning。
- 2026-06-09：纠正生成接口前端契约主线：
  - 将 `/resources/generate`、`/quiz/generate` 标记为当前前端契约作废 / 不接入，保留历史后端能力背景但不再作为教师端 UI 或下一步联调主线。
  - 当前主线回到 Admin 资源库创建、资料上传、触发入库 / 向量化、教师绑定 ready CourseCatalog 创建教学班，以及学生 / 教师如何消费入库后的资源和知识库内容。
  - 同步修正 `docs/feature-ledger.md`、`docs/project-direction.md`、`docs/project-coverage-audit.md`、Client API Markdown 与 OpenAPI 描述。
  - 验证：文档语义扫描、OpenAPI JSON 格式检查、`git diff --check`。
- 2026-06-09：重建功能进度主线看板：
  - 新增 `docs/feature-ledger.md`，按“用户实际能操作什么”重建开发进度账本。
  - 逐页核查真实前端调用，区分 `已可操作`、`后端闭环`、`联调待验收`、`前端无入口`、`待设计`、`暂缓`。
  - 确认资源生成和 Quiz 生成当前没有前端正式入口；Admin 资料上传和向量化已可操作。
  - 验证：占位符扫描无匹配；`git diff --check -- docs/feature-ledger.md` 通过。
  - Commit：`e7f1104 重建功能进度主线看板`。
- 2026-06-09：修正项目覆盖审计实际功能：
  - 修正 `docs/project-coverage-audit.md`，明确 Admin 界面已支持上传 `txt/md/pdf` 资料并触发 Agent 切片、embedding、Qdrant upsert，Backend 回写 `chunk_count/knowledge_status`，前端轮询刷新状态。
  - 验证：`cd ../backend && ../.venv/bin/pytest tests/test_course_catalog_ingestion.py -q` 通过 22/22；`cd ../agent_service && ../.venv/bin/pytest tests/test_knowledge_ingestion_api.py -q` 通过 13/13；`cd ../agent_service && ../.venv/bin/pytest tests/test_ingest_knowledge.py tests/test_course_knowledge_store.py -q` 通过 11/11；`npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog ingestion polling"` 通过 1/1。
  - Commit：`4c6ccf7 修正项目覆盖审计实际功能`。
- 2026-06-08：Phase B 资源生成 / Quiz 生成前置 CourseCatalog ready gate 完成：
  - Backend 新增共享 ready gate：教学班 `course_id` 解析到 `CourseOffering.catalog_id`，`CourseCatalog.status=ready` 且 `knowledge_status=ready|partial` 且 `chunk_count>0` 才允许生成。
  - `/resources/generate` 和 `/quiz/generate` 共用同一套校验；Agent payload 使用 `CourseCatalog.id`，Backend 持久化仍使用教学班 id。
  - OpenAPI、接口规范和前端 orphan service 清理已同步。
  - 验证：`cd ../backend && ../.venv/bin/pytest tests/test_course_catalog_ready_gate.py tests/test_resources_async.py tests/test_agent_integration.py::TestQuizGenerateIntegration -q` 通过 20/20；`python3 -m json.tool ../docs/10-client-api/Client-API.openapi.json` 通过；`npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning。
  - Commits：`f6b8b19`、`04107e4`、`1f8d765`、`7cf6a36`、`9778020`。
- 2026-06-08：AIChat 历史消息对象知识点白屏修复：
  - `AIChat.jsx` 对历史消息、SSE `knowledge_points` 和 `suggestions` 做可展示文本归一化，避免对象直接进入 React child。
  - 验证：`npm run test:e2e -- e2e/specs.spec.js -g "AI Chat renders historical messages"` 通过 1/1；`npm run lint` 通过；`npm run build` 通过。
  - 契约注意：OpenAPI 仍声明 `messages[].knowledge_points[]` 为 string，真实历史响应出现对象元素；前端当前只做兼容防白屏。
- 2026-06-08：CourseCatalogDrawer 入库任务轮询与状态文案修复：
  - `/tasks/{task_id}` 查询异常不再被本地改写为任务失败，继续轮询并展示“任务状态查询失败，正在重试”。
  - 资源库、知识库、资料、上传队列和任务状态按设计展示中文标签。
  - 验证：`npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog ingestion polling"` 通过；`npm run lint` 通过；`npm run build` 通过。
- 2026-06-08：AdminConsole 课程资源库入库 UI 接入完成：
  - 新增资源库详情抽屉，支持资料列表、知识库状态、批量选择文件逐个上传、手动触发入库和 `GET /tasks/{task_id}` 轮询。
  - 上传请求使用 `FormData`，不直连 Agent Service，不使用 mock 数据补字段。
  - 验证：`npm run lint` 通过；`npm run build` 通过。
- 2026-06-08：Phase B1 CourseCatalog 资料入库后端编排完成：
  - Backend 新增 `POST /admin/course-catalogs/{catalog_id}/ingestions`，创建 `course_catalog_ingestion` AsyncTask，后台调用 Agent `/agent/v1/knowledge/ingestions`，并回写资料和资源库状态。
  - 验证：Agent `test_knowledge_ingestion_api.py` 通过 13/13；Backend `test_course_catalog_ingestion.py test_course_catalogs.py` 通过 23/23；OpenAPI JSON 校验通过。

## 历史摘要

- 阶段一真实 Backend 主链路已完成 E2E 验收：登录、注册、课程、资源列表、学习路径基础展示、Quiz、AI Chat、教师基础学情、管理员基础页面。
- 阶段二已完成多项契约收口：学生端数据契约审查、P0 假展示清理、ResourceDetail 内容、LearningPath 节点资源、教师端学生聚合、AdminConsole 既有契约对齐。
- CourseCatalog 主线已完成：三表、教学班绑定、Admin 创建资源库、Admin 上传资料、Agent 入库向量化、知识库状态展示、Admin 资源库资源生成、资料/资源软删除、历史资源/Quiz 生成前 ready gate。
- TeacherConsole 曾短暂接入资源生成 UI；CourseCatalog 主线调整后已移除。当前教师资源生成和 Quiz 生成在前端契约中作废 / 不接入，不是当前主线。
- 详细历史请回看 git 提交、`docs/superpowers/specs/`、`docs/superpowers/plans/` 和 `docs/project-coverage-audit.md`。

## 本地联调注意事项

- 浏览器前端如果使用真实 Backend，请优先使用 `http://localhost:5173`，避免 `127.0.0.1` 与 Backend CORS origin 不一致。
- 推荐启动方式：`VITE_USE_MOCK=false VITE_API_BASE_URL=http://localhost:8001/api/v1 npm run dev`。
- Admin CourseCatalog 入库和资源生成真实验收需要 Backend、Agent Service、MySQL、Qdrant/storage、embedding provider 配置同时可用。
- Agent Service 必须带共享上传目录运行：`COURSE_CATALOG_STORAGE_ROOT=/home/yezisama/workspace/workflow/EDUagent/backend/storage/course_catalogs`。缺失时入库会失败为 `material does not exist`。

## 2026-06-12 LearningPath KG Fallback

- **问题**: `learning_paths` 表为空（0 行），`GET /learning-path` 永远返回空 `{nodes:[]}`，LearningPath 页面始终空白
- **方案**: 无 LP 记录时，从 active KG 拓扑排序合成路径骨架，全节点 recommended
- **改动**:
  - `backend/app/api/v1/learning_path.py`: 新增 `_topo_sort_kg_nodes()`（Kahn 拓扑排序）+ `_synthesize_kg_fallback_path()`（Offering→Catalog→KG 链合成），修改 `get_learning_path()` 空 LP 分支加 fallback 调用；LP 分支加 `source` 字段
  - `backend/app/services/kg_generation.py`: 加 `max_tokens: 32768` 防止 deepseek-v4-flash 无限生成
  - `backend/app/api/v1/catalogs.py`: `admin_generate_catalog_resources` 查 KG 改为用 `catalog.kg_host_course_id`（修复 CourseOffering.id 无法匹配 KG 的 bug）；删除死代码 `_active_kg_for_catalog_generation()`
  - `backend/tests/test_learning_path_fallback.py`: 6 单元测试 + 2 集成测试，全部通过
  - DB: `ALTER TABLE course_catalogs ADD COLUMN kg_host_course_id VARCHAR(32)`（修复 commit f1981ce 遗漏的迁移）
- **验证**: `pytest tests/test_learning_path_fallback.py -v` 8 passed
- **前端**: 零改动
- **Commit**: `a052c38` `9040d26` `9406747` `8907d51` `3783958`

## 2026-06-13 Admin 批量生成保底题库

- **问题**: `quiz_questions` 表 0 题，Quiz 页面无题可答
- **方案**: Admin 在 CourseCatalogDrawer 一键批量生成（按 KG 全部节点，每节点 7 题），学生按节点进入答题
- **改动**:
  - `backend/app/api/v1/catalogs.py`: 新增 `POST /admin/course-catalogs/{id}/quiz/generations` 端点
  - `backend/app/api/v1/quiz.py`: `GET /quiz/questions` 加 `node_id` filter，source 过滤加 `baseline`
  - `frontend/src/api/services/admin.js`: `startQuizGeneration()`
  - `frontend/src/api/services/quiz.js`: `getQuestions` 改为 `(courseId, nodeId)` 签名
  - `frontend/src/pages/LearningPath.jsx`: "进入练习" 链接带 `node_id`
  - `frontend/src/pages/Quiz.jsx`: 从 URL 读取 `node_id` 传给 API
  - `frontend/src/components/admin/CourseCatalogDrawer.jsx`: 新增"生成题库"按钮 + 轮询
  - `backend/tests/test_learning_path_fallback.py`: 新增 quiz node_id 过滤测试
- **验证**: `pytest tests/test_learning_path_fallback.py -v` 9 passed
- **Commit**: `f426ff6` `66fca5d` `6e30ab6` `04f282d` `3a54ec8` `15c2b12` `16525b9` `3f35a34`

## 2026-06-13 Admin 保底题库生成稳定性修复

- **问题**: Admin 题库生成先软删除旧 baseline 题，Agent 60 秒超时或 skeleton fallback 后会导致 LearningPath 无题；Agent payload 使用教学班 id，无法命中按 catalog id 入库的 Qdrant 切片。
- **方案**: Agent 检索使用 `catalog.id`，落库仍 fanout 到绑定教学班；后台子任务并发限制为 2；至少有新题成功落库后再替换旧 baseline；识别 skeleton 兜底题并拒绝落库。
- **改动**:
  - `backend/app/api/v1/catalogs.py`: quiz generation 子任务记录 `agent_course_id`，payload `course_id` 改为 catalog id；`class_course_ids` 保留教学班 fanout；旧题替换延后到父任务汇总阶段；每个子任务独立 DB session；新增 skeleton 题检测。
  - `backend/tests/test_admin_catalog_resource_generation.py`: 新增旧题保留、Agent RAG scope、skeleton 拒绝 3 个回归测试；修正资源生成 KG host fixture。
- **验证**: `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/admin_catalog_quiz_fix_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py -q -p no:cacheprovider` 26 passed；`npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning。
- **契约**: 无 OpenAPI 变更；Admin 外部接口路径和响应不变。

## 2026-06-13 学生画像基础闭环

- **问题**: 学生画像页只能读取刷新后的结构化画像，缺少自然语言补充入口；前端也无法直接展示稳定的六维画像摘要。
- **方案**: 新增 `/profile/dialogue-update`，由 Agent 解析学生补充文本并合并到当前课程画像；`GET /profile` 返回 `profile_dimensions`，前端按来源展示六维摘要。
- **改动**:
  - `backend/app/api/v1/profile.py`: 新增对话补充请求模型、画像合并逻辑、六维摘要生成和 `POST /profile/dialogue-update`；Agent 失败不覆盖旧画像。
  - `backend/tests/test_refresh_async.py`: 增加对话补充成功、Agent 失败不污染旧画像的回归测试，并补齐测试断言。
  - `frontend/src/api/services/profile.js`: 新增 `updateProfileByDialogue()`。
  - `frontend/src/pages/StudentProfile.jsx`: 新增六维画像卡片、自然语言补充输入区，并兼容对话补充产生的薄弱点结构。
  - `docs/10-client-api/API_前端接口规范.md`、`docs/10-client-api/Client-API.openapi.json`: 同步新增接口和 `profile_dimensions` 契约。
- **验证**: `python -m json.tool ../docs/10-client-api/Client-API.openapi.json` 通过；`TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/student_profile_loop_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_refresh_async.py -q -p no:cacheprovider` 1 passed；`npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning。
- **契约**: OpenAPI 与前端接口规范已同步新增 `/profile/dialogue-update` 和 `profile_dimensions`，无静默字段删除。

## 2026-06-13 画像和练习页闭环修复

- **问题**: Backend 已调用 Agent `/agent/v1/profile/dialogue-update` 但 Agent 缺路由；保底题库 skeleton fallback 字符串选项仍可能落库；Quiz 页面外壳仍写死“数据结构 / 树形结构 / 节点索引关系示意图”。
- **方案**: Agent Service 补齐画像对话补充路由；Backend 扩展 skeleton 题检测，拒绝字符串选项模板题；`GET /quiz/questions` 返回题目章节、知识点、难度；前端 Quiz 页面改为使用课程名和题目元数据渲染上下文。
- **改动**:
  - `agent_service/api/v1/profile.py`、`agent_service/schemas/profile.py`: 新增 `/agent/v1/profile/dialogue-update` 和画像补充响应结构。
  - `backend/app/api/v1/catalogs.py`: skeleton 题检测兼容字符串 options，避免“正确表述 / 易混淆表述 / 相关补充表述 / 无关表述”落库。
  - `backend/app/api/v1/quiz.py`: `GET /quiz/questions` 题目项新增 `chapter`、`knowledge_point`、`difficulty`。
  - `frontend/src/pages/Quiz.jsx`: 用课程、章节、知识点、来源、难度替换静态题目外壳，保留通用 `QuestionRenderer`。
- **验证**: `../.venv/bin/python -m pytest tests/test_profile_agent.py -q -p no:cacheprovider` 16 passed；`TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/student_profile_loop_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_refresh_async.py -q -p no:cacheprovider` 1 passed；`TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/admin_catalog_quiz_fix_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py -q -p no:cacheprovider` 27 passed；`TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/quiz_async_meta_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_quiz_async.py -q -p no:cacheprovider` 1 passed；`npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning。
- **契约**: 本批只新增响应字段并补齐 Agent 内部路由，未删除既有字段；正式 OpenAPI 在上一批画像闭环中已同步，本批未继续扩大契约文档修改。
- **Commits**: `a09ef6b`、`c5ad3fd`、`55d4026`、`d6b2cb6`、`b47bfc1`。

## 2026-06-13 学生画像展示降噪

- **问题**: `GET /profile` 已能返回课程画像，但个人资料页会直接展示内部枚举和结构字段，例如 `daily_homework`、`code_practice`、`L1`、`starter` 以及 `subject: 课程ID`。
- **方案**: 仅在前端渲染层做字段翻译和降噪，不改接口、不改后端数据；画像刷新仍走静默 `POST /profile/refresh` + `GET /tasks/{task_id}`。
- **改动**:
  - `src/pages/StudentProfile.jsx`: 新增画像枚举中文映射；六维画像按维度 key 友好渲染；学习纪律对象显示为“状态 / 课程 / 连续学习天数”；课程 ID 优先映射为当前课程名，无法识别的裸 ID 不展示。
- **验证**: `npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning。
- **契约**: 无 OpenAPI 变更；无新增字段、无删除字段。

## 2026-06-13 学生画像学习档案命名优化

- **问题**: 个人资料页画像摘要仍使用偏系统的字段名和值，例如“学习目标：每日作业”和 `L1`，学生侧理解成本较高。
- **方案**: 只在前端展示层将画像摘要调整为“学习档案”口径，不改接口、不改后端数据。
- **改动**:
  - `src/pages/StudentProfile.jsx`: 将六维画像展示名改为“当前学习方向 / 待提升内容 / 学习资料偏好 / 辅导方式 / 掌握进度 / 学习习惯”；将来源标签和枚举值改为学生可读文案。
- **验证**: `npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning。
- **契约**: 无 OpenAPI 变更；只修改前端渲染文案。

## 2026-06-13 学习资料偏好字符串枚举展示修复

- **问题**: 后端 `profile_dimensions.resource_preference.value` 返回 `code_practice、text_analysis、chart_logic` 这类已拼接字符串，前端只映射数组项和单个枚举值，导致学习资料偏好仍显示内部枚举。
- **方案**: 前端格式化字符串值时识别 `、`、`,`、`/` 分隔的枚举列表，逐项映射后再拼回中文展示。
- **改动**:
  - `src/pages/StudentProfile.jsx`: 新增 `formatProfileTextValue()`，兼容拼接字符串枚举。
- **验证**: `npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning。
- **契约**: 无 OpenAPI 变更；只修改前端渲染文案。

## 2026-06-14 AI Chat Hybrid Retrieval 代码热修

- **问题**: 最近的 Hybrid Retrieval 接入在 Backend `_assemble_tutoring_payload()` 中误读 `CourseKnowledgeGraph.graph_data`，但真实模型字段是 `nodes` / `edges`，导致课程对话 `POST /api/v1/tutoring/chat` 在存在 active KG 时直接 500；同时 probe CLI 的 `--json` 会混入人工日志，控制台输出也缺少 Qdrant chunk 的 score / metadata。
- **方案**: 仅修代码错误，不处理数据库脏数据；Backend 从 `CourseKnowledgeGraph.nodes` 安全提取 `active_kg_nodes`，继续只透传 `id/name/chapter`；probe CLI 在 JSON 模式下只向 stdout 输出 JSON，日志走 stderr，并在控制台模式展示 chunk score 与白名单 metadata；同步修正 Agent 旧测试中低分 KG 节点仍被保留的过期断言。
- **改动**:
  - `backend/app/api/v1/tutoring.py`: 修复 active KG 节点字段读取，移除不存在的 `graph_data` 访问。
  - `backend/tools/probe_aichat_hybrid_retrieval.py`: 修复 `--json` 输出污染，并补充 Qdrant chunk score / metadata 输出。
  - `backend/tests/test_tutoring_privacy.py`: 新增 MySQL 回归测试，覆盖 CourseOffering -> CourseCatalog -> active KG -> `active_kg_nodes` payload 组装链路。
  - `agent_service/tests/test_tutoring_retrieval.py`: 将 KG reranker 低分节点断言对齐当前 `score >= 0.35` 策略。
- **验证**:
  - `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/tutoring_payload_kg_fix?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_tutoring_privacy.py::test_tutoring_payload_uses_active_kg_nodes_field -q -p no:cacheprovider` 通过，1 passed。
  - `./.venv/bin/python -m pytest agent_service/tests/test_aichat_hybrid_retrieval.py -q -p no:cacheprovider` 通过，6 passed。
  - `./.venv/bin/python -m pytest agent_service/tests/test_tutoring_retrieval.py -q -p no:cacheprovider` 通过，9 passed。
  - `PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -B -c "... ast.parse ..."` 通过，相关 Python 文件语法正常。
- **契约**: 不改前端 UI，不改 Client API/OpenAPI；`retrieval_probe` 仍为 Agent 内部诊断端点。
- **运行态注意**: 8002 Agent 服务需要重启以加载 `/agent/v1/tutoring/retrieval_probe` 新路由；否则 probe 仍可能 404。

## 2026-06-14 AI Chat 输出污染与体感等待修复

- **问题**: Agent SSE 会先把规则 fallback 正文作为 `chunk` 发给前端，模型成功后又发送真实回答，导致同一条 AI 消息混入“兜底模板 + 正常回答”；模型若返回 ```json fenced JSON，parser 会把整段 JSON 代码块当正文，前端 Markdown 渲染后暴露 `model_text/knowledge_points/suggestion`；同时真实链路不是 token streaming，用户在检索/生成期间缺少可信进度反馈。
- **方案**: 移除“先发 fallback 正文”的假流式，改为先发 `status` 进度事件；只有 ReAct/Chat 都失败时才发送规则 fallback chunk；parser 支持 Markdown fenced JSON 并只提取 `model_text` 作为正文；前端 AIChat 接收 `status` 事件后显示为运行中的工具/检索状态，不写入正文、不入库。
- **改动**:
  - `agent_service/agents/tutoring.py`: 新增 fenced JSON 解析；SSE 先发 retrieval/generation 状态事件，模型成功时只发真实模型 chunk，失败时才发 fallback chunk。
  - `agent_service/tests/test_tutoring_agent.py`: 覆盖 fenced JSON 解析、不再发送双 chunk、diagram 顺序等回归。
  - `agent_service/tests/test_tutoring_api.py`: 将 API SSE 测试调整为区分 status 事件和正文事件。
  - `src/pages/AIChat.jsx`: 处理 `status` 事件并显示为运行中的 `ToolCallCard`，首个正文 chunk 到达后清理状态。
- **验证**:
  - `./.venv/bin/python -m pytest agent_service/tests/test_tutoring_agent.py -q -p no:cacheprovider` 通过，19 passed。
  - `./.venv/bin/python -m pytest agent_service/tests/test_tutoring_api.py -q -p no:cacheprovider` 通过，10 passed。
  - `./.venv/bin/python -m pytest agent_service/tests/test_aichat_hybrid_retrieval.py -q -p no:cacheprovider` 通过，6 passed。
  - `npm run lint` 通过。
  - `npm run build` 通过，仍有既有 Vite chunk size warning。
- **契约**: 不改 Client API/OpenAPI；新增的 `status` 为 Agent SSE 内部事件，Backend 只透传并不入库，正文仍通过 `chunk` 事件传递。

## 2026-06-14 AI Chat trailing JSON 代码块清理

- **问题**: 部分模型输出是“自然语言正文 + 末尾 ```json 结构化结果代码块”，上一轮 parser 只处理“整段都是 fenced JSON”的情况，导致末尾 `model_text/knowledge_points/suggestion/diagram` JSON 仍被前端 Markdown 渲染出来。
- **方案**: `parse_tutoring_model_response()` 在任意位置搜索 fenced JSON；只有 JSON object 含 `model_text`、`knowledge_points`、`suggestion` 或 `diagram` 等结构化字段时才接管解析；优先使用 payload 内的 `model_text` 作为正文，否则使用剥离 JSON 代码块后的自然语言正文。
- **改动**:
  - `agent_service/agents/tutoring.py`: fenced JSON parser 从整段 `fullmatch` 改为安全 `finditer`，避免 trailing JSON 泄露。
  - `agent_service/tests/test_tutoring_agent.py`: 增加“正文 + trailing fenced JSON”回归测试，断言正文不含 ```json 和 `"model_text"`。
- **验证**:
  - `./.venv/bin/python -m pytest agent_service/tests/test_tutoring_agent.py -q -p no:cacheprovider` 通过，20 passed。
  - `./.venv/bin/python -m pytest agent_service/tests/test_tutoring_api.py -q -p no:cacheprovider` 通过，10 passed。
  - `./.venv/bin/python -m pytest agent_service/tests/test_aichat_hybrid_retrieval.py -q -p no:cacheprovider` 通过，6 passed。
  - `npm run lint` 通过。
  - `npm run build` 通过，仍有既有 Vite chunk size warning。
- **契约**: 无 OpenAPI/Client API 变更；仅修正 Agent 内部模型输出解析。

## 下一步指针

下一步队列不在本文件维护，统一查看 `docs/feature-ledger.md` 的“当前下一步队列”。

## 2026-06-14 学习行为采集与学习效果耗时闭环

- **问题**: `/learning-effects` 节点学习耗时此前只能从 `QuizSession.time_spent` 兜底，资源阅读和节点浏览没有真实行为来源。
- **改动**:
  - Backend 新增 `LearningActivity` 模型、迁移和 `POST /api/v1/learning-activities`。
  - `/evaluation` 节点进度聚合优先读取学习行为表累计时长、资源访问次数和最近活动时间；没有学习行为时兼容旧练习耗时。
  - `GET /resources/{id}` 返回 `course_id`，支持资源详情页上报课程上下文。
  - Frontend 新增 `learningActivityService`，在资源详情、LearningPath 节点选择、Quiz 节点练习开始/提交处做非阻塞上报。
  - Quiz 提交从硬编码 `time_spent: 120` 改为页面真实 elapsed seconds。
  - Client API Markdown 和 OpenAPI 同步新增 `/learning-activities` 契约。
- **验证**:
  - `../.venv/bin/python -m pytest tests/test_learning_activities.py tests/test_resource_detail.py -q -p no:cacheprovider` 通过，4 passed。
  - `npm run lint -- --max-warnings=0` 通过。
  - `python3 -m json.tool docs/10-client-api/Client-API.openapi.json` 通过。
  - `git diff --check` 通过。
- **契约**: 新增 `POST /learning-activities`；资源详情响应新增兼容字段 `course_id`。

- 2026-06-14：AIChat 假数据清理与课程上下文修正 (A+)：
  - 问题分析：前一版本 AIChat 引入了写死的资源推荐卡片（如“深入理解指针内存模型”）和写死的 C 语言 ChatEmptyState prompt，且错用了 `course.title` 而不是 `course.name`，这违反了“不允许 mock / 假数据内容”的约束，且可能掩盖 Agent 尚未实现真实检索能力的事实。
  - 修复：
    1. 在 `AIChat.jsx` 中将 `activeCourseName` 获取逻辑改为 `course.name || course.title || '未选择课程'`。
    2. 将动态的 `courseName` 传给 `ChatEmptyState`，并使用泛化提示词替换掉所有硬编码的 C 语言提示词。
    3. 清除右侧边栏的所有静态资源卡片，替换为真实空态，提示：“完成检索能力验证后，这里会展示与本轮知识点相关的课程资源。”
  - 契约说明：纯前端 UI 修理，不涉及任何接口调用修改，无 OpenAPI 漂移。
  - 验证：
    - Frontend `npm run lint` 通过。

### 2026-06-14 Task 3 完成记录
1. **当前完成 / 实现状态**：完成 AI Chat Hybrid Retrieval 的 Task 3，实现了 `agent_service/api/v1/tutoring.py` 的 `/retrieval_probe` 探针接口，并新增了 `backend/tools/probe_aichat_hybrid_retrieval.py` 命令行工具。
2. **修改文件**：
   - `agent_service/api/v1/tutoring.py`
   - `backend/tools/probe_aichat_hybrid_retrieval.py`
3. **测试结果**：在 backend 目录下成功运行了 `uv run ruff check tools/probe_aichat_hybrid_retrieval.py` 并修复了 f-string 问题。运行 `uv run python -m tools.probe_aichat_hybrid_retrieval --help` 成功输出帮助信息。
4. **OpenAPI/契约是否漂移**：否。
5. **git commit 信息**：已提交。commit hash `9f00ab3`。
6. **剩余风险**：需要在有数据的环境下实际运行探针工具来验证 Qdrant 和 Agent 组合的行为，目前仅测试了工具能成功加载及请求装配。
7. **下一步建议**：根据计划进入实际检索效果的联调或执行下一个任务。

### 2026-06-14 修复 AI 对话框代码渲染问题
- **状态**: 已完成
- **内容**: 修复 AI 响应返回 JSON 时，`getDisplayText` 无法正确提取 `model_text` 导致直接渲染 JSON 字符串（进而使得 markdown 代码块换行失效和语法高亮失效）的问题。
- **文件**: `src/pages/AIChat.jsx`, `src/components/chat/ChatMessage.jsx`
- **测试**: 运行 `npm run lint` 通过，已确认语法正常。

### 2026-06-14 优化智能问答 Tool Call 进度展示逻辑
- **状态**: 已完成
- **内容**: 剔除了非工具调用的“正在生成回答...”的 ToolCall 渲染（该进度已由默认打字机和泡泡内的 loading dot 展现），并修复了 RAG 检索状态（“检索课程知识库”）在生成首个 chunk 后闪烁消失的问题，使其保留为已完成（`check_circle`）状态。
- **文件**: `src/pages/AIChat.jsx`
- **测试**: 运行 `npm run lint` 通过。

### 2026-06-14 集成 AI 对话 Mermaid 可视化渲染与语法容错
- **状态**: 已完成
- **内容**: 
  - 在 `ChatMessage.jsx` 中新增 `MermaidDiagram` 渲染组件，替代原先简单的 `<pre>` 文本标签，使图解模式能够直接显示可视化关系图。
  - 新增 `sanitizeMermaidSource` 自动容错逻辑，使用正则检测并为大模型输出中括号内包含 `<br>`/`:`/空格等保留字符但未包裹双引号的节点标签（如 `A[变量a<br>值: 10]`）自动加盖双引号（如 `A["变量a<br>值: 10"]`），从前端层面彻底规避由于未转义特殊字符引起的 Mermaid 语法解析白屏（`Parse Error`）。
- **文件**: `src/components/chat/ChatMessage.jsx`
- **测试**: 运行 `npm run lint` 通过。

### 2026-06-14 锁定 AI 问答页面与侧边栏高度
- **状态**: 已完成
- **内容**: 
  - 锁定外层容器高度为视口高度（`h-screen`），并隐藏外层溢出滚动（`overflow-hidden`）。
  - 将左侧历史侧边栏和右侧资源侧边栏在桌面端的高度设置为占满容器（`lg:h-full` / `xl:h-full`），确保中间对话区域可以进行独立滚动。
- **文件**: `src/pages/AIChat.jsx`
- **测试**: 运行 `npm run lint` 成功。

### 2026-06-14 tutoring ReAct 结构化输出修复（JSON泄露 / 超时检索失效 / 慢）
1. **当前完成 / 实现状态**：已完成。改用 AgentScope `structured_model`（新增 `TutoringStructuredOutput`）让 ReActAgent 产出已校验结构化对象，从源头消除前端 JSON 块泄露；ReAct 主路径的 `OpenAIChatModel` 应用有界 `timeout` 与 `stream`（此前超时守卫只在 `AgentScopeChatProvider.complete()`、ReAct 用裸 model 绕过，导致 APITimeoutError 长挂起 + retrieve 被中断 + 降级）；修复 `tutoring_react_flow` 无条件打 "Tutoring ReAct succeeded" 的误导日志；兜底解析器从非贪婪正则改为括号配平（正确跳过 `model_text` 内嵌 ```c 围栏，不再把整段 JSON 当正文）；前端两份重复 `getDisplayText` 抽成共享 `extractModelText` 防御层，兜旧脏数据。
2. **修改文件**：
   - 后端 `agent_service/`：`core/config.py`、`core/ai.py`、`schemas/tutoring.py`、`agents/tutoring.py`、`agents/tutoring_react.py`、`agents/tutoring_react_flow.py`、`prompts/tutoring.py` 及对应 7 个 `tests/` 文件。
   - 前端：`src/utils/chatContent.js`（新增）、`src/components/chat/ChatMessage.jsx`、`src/pages/AIChat.jsx`。
   - 文档：`docs/superpowers/specs/2026-06-14-tutoring-react-structured-output-fix-design.md`、`docs/superpowers/plans/2026-06-14-tutoring-react-structured-output-fix.md`。
3. **测试结果**：后端 in-scope 7 个测试文件 `uv run pytest` → 80 passed；全量 → 9 failed / 461 passed，9 个失败为既有且与本次无关（`test_assessment_difficulty_balancer` 3 个 + `test_aichat_hybrid_retrieval` 6 个，后者为 `pytest.mark.asyncio` 未注册的环境问题）。前端 node 逻辑脚本 7 条全 PASS；`npm run lint`、`npm run build` 通过。
4. **OpenAPI/契约是否漂移**：否。SSE 事件与 Client API 字段不变，未改 `../docs/`，未改 `.env`。
5. **git commit**：`3c261df`(spec)、`7f63fbf`(plan)、`522c044`(前端防御层)、`c9e38b1`(后端超时/stream)、`c1b9a10`(后端结构化输出)。未 push。
6. **剩余风险**：依赖模型稳定调用 `generate_response`（未调用时回退文本兜底 + 规则兜底）；结构化输出为原子返回，正文非逐字流式（已与用户确认取舍）；既有 9 个失败测试（assessment 难度均衡 + KG 混合检索 pytest-asyncio）待另行处理。
7. **下一步建议**：在有真实 LLM/Qdrant 的环境对 /ai-chat 做端到端联调，确认不再泄露 JSON、超时可控、检索生效；另起任务修 `pytest-asyncio` 配置与既有失败测试。

### 2026-06-15
- **Task**: 实现基于规则的画像刷新 (Task 3: Backend API, Task 4: Frontend Display)
- **Modified Files**:
  - `backend/app/api/v1/profile.py`: 移除 agent 调用，直接调用 `compute_profile_fields`，更新 `_profile_dimensions`，替换 `discipline` 为 `learning_habits`
  - `frontend/src/pages/StudentProfile.jsx`: 增加 `learning_habits` 和 `knowledge_progress` 的前端定制化渲染逻辑
- **Status**: 已完成
- **Testing**: 后端运行 `uv run python -m py_compile` 语法检查通过，前端运行 `npm run lint` 检查通过
- **Git**: 提交消息 `feat(profile): integrate evidence-based profile rules into API and update frontend display`

## 2026-06-15 学习路径节点状态实时计算

### 修改文件
- `backend/app/api/v1/learning_path.py`：新增 `_map_assessment_to_status`、`_apply_progress_to_nodes`、`_build_current_position_from_nodes`；改写 `get_learning_path` 为 Merge 策略

### 新增文件
- `backend/tests/test_learning_path_realtime.py`：映射函数和 merge 逻辑单元测试（13 个测试）

### 变更说明
GET /learning-path 每次调用 build_node_progress_rows 实时计算节点状态，用 assessment_state→前端 status 映射后 merge 到快照节点，mastery_score 同步更新进度条。快照的 reason/order/edges/current_position 全部保留。KG fallback 路径也改为实时状态映射，current_position 取第一个非 pending 节点（全 pending 时取第一个）。

### 测试结果
- test_learning_path_fallback.py: 同步测试 PASS（异步测试因环境缺 pytest-asyncio 跳过，改动前已存在）
- test_learning_path_realtime.py: 13/13 PASS
- 总计：19 passed, 3 failed (async, pre-existing)

### 契约漂移
无。响应结构不变，source 字段新增 "realtime_merged"/"kg_realtime" 值（前端未使用该字段）。

### 剩余风险
build_node_progress_rows 每次 GET 同步查多张表，高并发场景可后续加 Redis TTL 缓存。

### git commit
`docs: 更新 WORKFLOW.md，记录实时节点状态改造施工`

---

## 2026-06-15 教师报告页小修复

### 改动文件
- `src/pages/TeacherStudentReport.jsx`

### 核心改动
1. **avg_time 显示**：`< 60s` 时改为显示 `< 1m`（原先 `Math.round(秒/60)` 导致不足1分钟全显示 `0m`）
2. **modal_preference 中文化**：前端加映射表 `{ video_animation: '视频/动画', chart_logic: '图表/逻辑', text_analysis: '文本阅读', code_practice: '代码练习', formula_derivation: '公式推导' }`，后端 key 不变

### 存档（未改动，留后续）
- 教师报告路径进度卡片：大部分学生无 `learning_paths` 记录（因为从未触发 Agent 生成），后续需考虑基于 KG 节点重新定义语义
- `POST /api/v1/learning-path/refresh`：后端完整，前端 service 有方法（`learningService.refreshPath`）但无 UI 入口，后续加"刷新路径"按钮时直接调用

### 测试结果
- `npm run build` 通过，无报错

### 2026-06-16

- 个性化资源功能（spec：`docs/superpowers/specs/2026-06-16-personalized-resources-design.md`，plan：`docs/superpowers/plans/2026-06-16-personalized-resources.md`）：
  - 新建表 `user_personalized_resources`（DDL 已执行），新增 `UserPersonalizedResource` SQLAlchemy model（`backend/app/models/others.py`）
  - 新建 `backend/app/schemas/personalized.py`：`PersonalizedResourceGenerateRequest`
  - 新建 `backend/app/api/v1/personalized_resources.py`：`GET /api/v1/personalized-resources`（全量 processing_count 统计）、`POST /api/v1/personalized-resources/generate`（quiz 同步路径 + resource 异步 Webhook 路径）
  - 修改 `backend/app/main.py`：注册 `personalized_resources.router`
  - 修改 `backend/app/api/v1/webhooks.py`：resource_generation 回调补全 `user_personalized_resources.resource_id`，使用 `scalars().first()` 防多行崩溃
  - 新建 `frontend/src/api/services/personalizedResources.js`
  - 新建 `frontend/src/pages/PersonalizedResources.jsx`：独立页面，3s 轮询，筛选栏，空/loading/processing/failed/question/resource 卡片
  - 新建 `frontend/src/components/personalized/GenerateModal.jsx`：三步引导（章节→知识点→资源类型），全失败时保持 Modal 开启
  - 修改 `frontend/src/pages/PracticeResult.jsx`：accuracy<60 显示橙黄横幅，fallback 路径也可触发（不强依赖 wrongQuestionIds，后端用历史错题上下文）
  - 修改 `frontend/src/components/Sidebar.jsx`：添加"个性化资源"导航入口（psychology 图标）
  - 修改 `frontend/src/App.jsx`：注册 `/personalized-resources` 路由
  - 接口漂移：新增 `/api/v1/personalized-resources` 接口族（学生可用），`personalization_context.wrong_points` 新增 `content` 字段
  - 验证：`py_compile` 全通过（5/5）；`npm run build` 通过（774ms）；lint 无新增 error

- 答题后加载动画与动态文案优化：
  - 修改了 `frontend/src/pages/PracticeResult.jsx`，增加了 `LOADING_TEXTS` 和 `currentTextIndex` 状态，将等待时间从 1.5 秒延长到 5 秒，每 1.25 秒轮询更新加载状态文字，在第 4 步后停止。
  - 优化了加载卡片样式以适配原生的浅色主题（显示“智能教练评估中”，配以 outer spin 进度环和 inner pulse 机器人图标）。
  - 验证：`npm run build` 成功通过，无编译报错；`src/pages/PracticeResult.jsx` 无新增 lint 问题。

2026-06-16 AI Chat 交互增强
- 后端: TutoringChatRequest 新增 action 字段 (d1caeeb); /chat 三路分流(chat/edit/regenerate) (328984f); 复审修复 last_user 为空守卫 (7837624); DELETE /conversations/{id} 软删除会话 (24c6a7c)
- 前端: chatService 支持 action 参数 + deleteSession (dd7a526); 停止生成按钮 (4a04179); 编辑消息/重新生成/复制消息 (5f741cd); 删除历史对话 (d59ae4d)
- 关键改动: streamTargetIdRef 替代硬编码 'ai-placeholder'; SSE 回调提取为 ref 模式 (streamOnMessageRef/streamOnDoneRef/streamOnErrorRef)
- 架构变化: handleSendMessage / handleRegenerate / handleEditSubmit 复用同一组 SSE 回调 ref，仅 targetId 不同
- 验证: py_compile全通过; npm run build通过; lint无新增error

### 2026-06-17
- **修改文件**：`frontend/src/components/chat/ChatMessage.jsx`
- **核心改动**：在 `sanitizeMermaidSource` 增加正则表达式，用于捕获包含空格、引号或方括号等无效字符的非法 `subgraph` 标题（例如 `subgraph 数组 int arr["5"] 的内存布局`），并自动将其转换为带双引号的合法语法（`subgraph "..."`）。
- **测试结果**：无代码运行报错，成功解决 Mermaid 因为语法解析异常导致的渲染失败。
- **接口漂移**：无

### 2026-06-17 (前端标题修改)
- **修改文件**：`index.html`, `src/components/Navbar.jsx`, `src/pages/Success.jsx`, `src/pages/AdminConsole.jsx`
- **核心改动**：根据反馈将过于狭窄的前端标题“数据结构智能助手”（及相关的 DS_MASTERY_AI 等）统一修改为“智能学习助手”，以匹配业务需求（保持和登录注册页一致的文案）。
- **测试结果**：无代码运行报错。
- **接口漂移**：无

### 2026-06-17 (前端UI重构-全局去除学生端侧边栏)
- **修改文件**：`src/pages/Dashboard.jsx`, `src/pages/LearningEffects.jsx`, `src/pages/StudentProfile.jsx`, `src/pages/LearningPath.jsx`, `src/pages/PersonalizedResources.jsx`, 删除 `src/components/Sidebar.jsx`
- **核心改动**：彻底清理了学生端所有页面中冗余的侧边栏组件。移除了 `<Sidebar />` 引用以及硬编码的 `<aside>`，统一采用全局顶部 `Navbar` 导航模型。同步移除了对应 `<main>` 容器预留的左侧边距（如 `lg:ml-64`、`lg:pl-64`、`md:pl-64`），使主内容区在宽屏下重新恢复居中显示。
- **测试结果**：无代码运行报错，组件删除无遗留依赖。
- **接口漂移**：无

### 2026-06-17
- **更新文件**: `src/utils/mermaid.js`, `src/components/common/MarkdownViewer.jsx`, `src/components/chat/ChatMessage.jsx`, `src/pages/ResourceDetail.jsx`
- **核心改动**: 提取全局复用的 `MarkdownViewer` 组件解决 `ResourceDetail` Markdown 解析失效问题。将散落的 mermaid 配置统一收拢至工具包，同时彻底清理 ChatMessage 和 ResourceDetail 内部耦合的富文本渲染逻辑。
- **测试结果**: 前端 lint/build 成功。
- **接口漂移**: 无。跨组件接口重构成功。

---

## 全局重构与技术债清理计划 (Agenda)
- [ ] 抽取全局状态管理和重复的 Context
- [ ] 标准化接口请求层（Axios）与统一错误处理
- [ ] 梳理冗余 UI 组件并迁移至统一组件库

### 2026-06-17 (前端AIChat解耦与架构梳理)
- **修改文件**: `src/pages/AIChat.jsx`, `src/context/ChatContext.jsx`, `src/App.jsx`, `src/utils/chatContent.js`, `tests/e2e/chat-persistence.spec.js`, `tests/unit/chatContent.test.js`
- **核心改动**: 创建全局 `ChatContext` 剥离 `AIChat.jsx` 中超过 500 行的流状态管理代码。修复因组件卸载导致的连接中断 Bug。引入基于 Node 的单元测试与 Playwright E2E 自动化测试保障流功能稳定性。顺带清理了原有的 `setTimeout` 状态管理反模式、渲染性能抖动问题。
- **测试结果**: 单元测试、E2E 测试通过，lint 与 build 全绿。
- **接口漂移**: 无。

---

# 阶段二：全栈架构重构与规范化 (Phase 2)
*(自 2026-06-17 开启)*

> **Git 状态标记**：大重构启动前的项目快照已被安全封存至 Git Tag `v1.0.0-pre-refactor` 中。若未来的架构调整中出现不可逆问题，可随时退回该版本以恢复一阶段打通的基础功能。

由于前期的“功能打通阶段”已实现闭环，后续开发正式迈入“架构治理与重构阶段”。
未来的任务核心为：通过以下五大重构方向，持续推动架构的高内聚和低耦合，最终让项目架构清晰明了、提升开发者阅读与维护体验。

**重构五大核心方向（AI 行动指南）：**
1. **整理目录**：消除臃肿的大文件，强制推行 `Router -> Service -> DB` 等清晰分层。
2. **提取公共组件**：统一提炼散落的 UI 元素、冗余 Context 和 Axios 请求拦截器。
3. **加测试**：伴随逻辑剥离，补全并维护相关的自动化单元测试/E2E 测试。
4. **清环境变量**：审查并统一前后端和 Agent 中的重复配置，清理虚拟环境残余。
5. **规范后端和 Agent 边界**：剥离 Agent 中的业务 CRUD 逻辑，数据流需全由标准 Backend API 接管。

*(注：负责后续任务的 AI 应在以上框架指引下，自行发掘代码坏味道，撰写单模块的 Spec，并自动推进实现，切勿死板等待被动指令。总指导方针位于 `docs/superpowers/specs/2026-06-17-phase2-architecture-refactoring-master-plan.md`)*

### 2026-06-17 (前端传统分层架构试点：CourseCatalogDrawer 纵向切片重构)

- **改了什么文件**:
  - **新增（测试基建）**: `vitest.setup.js`, `src/utils/__tests__/apiError.test.js`
  - **新增（Service 层）**: `src/api/services/catalog.js`, `src/api/services/__tests__/catalog.test.js`
  - **新增（Hook 层）**: `src/hooks/useCatalog.js`
  - **新增（子组件）**: `src/components/admin/catalog/` 目录下共 11 个文件（`formatters.js` + `TaskStatusPanel.jsx` + 9 个业务 Section 组件）
  - **修改（缩减）**: `src/components/admin/CourseCatalogDrawer.jsx`（1331 → 129 行，缩减 90%）
  - **修改（清理）**: `src/api/services/admin.js`（删除已迁移的 catalog stub 方法）
  - **修改（同步迁移）**: `src/pages/AdminConsole.jsx`（改用 `catalogService`）
  - **删除（废弃组件）**: `src/components/Sidebar.jsx`，同步清理 Dashboard/LearningEffects/LearningPath/PersonalizedResources 中内联的侧边栏 JSX
  - **修改（配置）**: `vite.config.js`, `package.json`（引入 Vitest 测试框架）

- **核心改动**:
  按"传统分层架构（Pages → Hooks → Services）"纵向切片重构 `CourseCatalogDrawer`，作为整个前端分层重构的**黄金样板间**。
  - **Service 层**：将 14 个 catalog HTTP 方法从 `adminService` 大杂烩中独立提取为 `catalogService`，对齐 `admin.js`/`auth.js` 命名规范，补全 14 个方法的单元测试
  - **Hook 层**：将组件内全部 22 个 state、12 个 ref、10 个 effect、9 个 handler 迁入 `useCatalog.js`；同时修复 3 个隐藏 bug（`handleDeleteResource` 缺 `onChanged` 回调、quiz 轮询用 `setInterval` 存在并发请求风险、`refreshDetails` 的 `open` 依赖导致轮询 effect 无谓重启）
  - **组件层**：将 1331 行巨石组件拆分为 9 个职责单一的展示子组件（平均 60 行），`CourseCatalogDrawer.jsx` 主文件仅保留 useCatalog 调用 + 子组件装配（129 行）
  - **测试**：建立 Vitest 测试框架，Service 层单测 14 个方法，工具函数单测 5 个场景，共 19 个测试全部通过

- **测试结果**: `npm run test:unit` 19/19 通过，`npm run build` 无错误

- **是否有接口漂移**: 无（纯架构解耦，不涉及后端接口）

- **遗留 backlog**:
  - `GET /course-catalogs`（公开非 admin 接口）仍使用内联查询，后续迁移时可参照本次样板
  - `admin.js` 中 `getCourseCatalogs`/`createCourseCatalog` 已完全迁移，实际上`AdminConsole.jsx` 已改用 `catalogService`，admin.js 中这两个方法已清理
  - 下一个纵向切片目标：`StudentProfile.jsx`（约 900 行）

### 2026-06-17 (后端三层架构重构与异常拦截试点)
- **改了什么文件**: `backend/app/exceptions/__init__.py`, `backend/app/exceptions/base.py`, `backend/app/exceptions/handlers.py`, `backend/app/exceptions/catalog_exceptions.py`, `backend/app/main.py`, `backend/app/services/catalog_service.py`, `backend/tests/test_catalog_service.py`, `backend/app/api/v1/catalogs.py`
- **核心改动**: 根据 Phase 2 重构方针，以 `catalogs.py` 为试点推进三层架构。搭建了基于 FastAPI 生命周期拦截的 `DomainException` 异常处理框架；创建了 `CatalogService` 承载数据库底层查询（分离 Controller 与 Service）；彻底移除了长达数千行的路由文件中混杂的辅助函数 `_get_admin_catalog_or_404`，完成全量替换。
- **测试结果**: TDD 测试用例编写及语法通过，Code Review 审查代码一致性通过，无潜在故障点。
- **是否有接口漂移**: 无（只做架构解耦，不影响外部调用的接口协议）。

### 2026-06-18 (前端 LearningEffects 页面展示与容器分离重构完成)
- **改了什么文件**: `src/pages/LearningEffects.jsx`, `src/hooks/useLearningEffects.js`, `src/hooks/__tests__/useLearningEffects.test.js`, `src/components/effects/EffectsOverviewCards.jsx`, `src/components/effects/EffectsSummaryCard.jsx`, `src/components/effects/MasteryDistributionCard.jsx`, `src/components/effects/KnowledgeProgressTable.jsx`
- **核心改动**: 根据 Phase 2 重构方针，将 `LearningEffects.jsx` 中的逻辑状态、评估任务双 SWR 轮询与派生状态计算逻辑完整抽取为 `useLearningEffects` 自定义 Hook；将展现 UI 拆分为 `EffectsOverviewCards`、`EffectsSummaryCard`、`MasteryDistributionCard` 与 `KnowledgeProgressTable` 4 个展示性组件，`LearningEffects.jsx` 仅作为容器组装。
- **测试结果**: Hook 单元测试通过，Vite 生产构建成功，Vite / ESLint 零报错。
- **是否有接口漂移**: 无。
- **修复与优化**: 解决 Code Review 问题，包括删除 `useLearningEffects.js` 渲染阶段同步调用 `setRefreshTask` 的 React 警告隐患，并移除了全局 `globalRefreshCounter` 变量，改用 Hook 实例内局部 `useState(0)` 进行 SWR Key 重新挂载，并补齐了 `getLearningEffects` 的单元测试 mock 配置以及 `waitFor` 测试异步等待逻辑，单元测试与打包均通过。

### 2026-06-18 (前端网络层拦截器测试补齐)
- **改了什么文件**: `src/api/__tests__/client.test.js`, `WORKFLOW.md`
- **核心改动**: 为 `src/api/client.js` 补齐 Axios 实例行为测试，覆盖请求自动注入 Bearer token、成功响应 `data` 解包、401 清理 token 并跳转登录、403/5xx/网络错误触发全局 toast，以及其他 4xx 不触发全局 toast 的约定。
- **测试结果**: `npm run test:unit -- src/api/__tests__/client.test.js` 通过，7/7 passed。
- **是否有接口漂移**: 无。纯前端网络层测试补齐。

### 2026-06-18 (后端 catalogs.py 响应格式化提取)
- **改了什么文件**: `backend/app/api/v1/catalogs.py`, `backend/app/services/catalog_presenters.py`, `backend/tests/test_catalog_presenters.py`。
- **核心改动**: 按 catalogs 模块化重构计划 Task 1，将 `_catalog_item`、`_material_item`、`_knowledge_graph_summary`、`_knowledge_graph_task_summary` 从胖路由提取到 `catalog_presenters.py`。`catalogs.py` 保留原响应包装调用，不移动 DB 查询或业务状态逻辑。
- **测试结果**: RED: `../.venv/bin/python -m pytest tests/test_catalog_presenters.py -q -p no:cacheprovider` 因缺少 `app.services.catalog_presenters` 失败；GREEN: `tests/test_catalog_presenters.py` 3/3 passed；语法检查: `PYTHONPYCACHEPREFIX=/tmp/eduagent_pycache ../.venv/bin/python -m py_compile app/api/v1/catalogs.py app/services/catalog_presenters.py` 通过；回归: `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/catalog_task1_presenters_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_catalog_presenters.py tests/test_course_catalogs.py -q -p no:cacheprovider` 7/7 passed。
- **是否有接口漂移**: 无。响应 key、HTTP 状态码、Client API / Agent API 路径均未改变。
- **代码审查结果**: Diff 仅包含 presenter 函数搬迁和调用替换；未移动查询逻辑，未新增后台任务，未触碰文件系统/上传目录。
