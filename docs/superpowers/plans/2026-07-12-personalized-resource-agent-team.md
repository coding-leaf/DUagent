# 个性化资源 Agent Team 与资源库优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化公共与个性化资源库，修复学情事实，使用 AgentScope 2.0.3 官方 Agent Team 完成五类个性化资源生成、验证、宽松审核、正式入库和前端展示，并在全量验证后审计赛题疑点与 TODO。

**Architecture:** Backend 继续拥有 MySQL 业务事实、验证和发布事务；Agent Service v2 使用官方 `agentscope.app.create_app`、Leader session 和两个 `SubAgentTemplate` Worker；Frontend 只通过 Backend 使用稳定 EDU API/SSE。公共资源和个性化资源共享底层 RAG/格式/OJ 能力，但业务协议与隐私上下文分离。

**Tech Stack:** React 19、SWR、FastAPI、SQLAlchemy async、MySQL、Pydantic、pytest、Vitest、AgentScope 2.0.3、Qdrant、Judge0。

## Global Constraints

- 当前分支必须保持 `ai-dev/agentscope-v2`；不得 push、force push、reset hard 或 clean。
- 不修改任何 `.env`、密钥、MySQL volume、Qdrant 数据或用户上传文件。
- Frontend 不直连 Agent Service；Agent Service 不写 MySQL；Backend 不导入 Agent Service；Backend 不访问 Qdrant。
- Agent Service v2 只新增或修改 `/agent/v2/...`；不恢复 `/agent/v1/...`。
- AgentScope 实施事实以本地 2.0.3 introspection 为准；`create_app` 使用已验证的 `custom_subagent_templates` 参数。
- 所有生产行为修改必须先出现对应失败测试并确认 RED，再写最小实现达到 GREEN。
- 所有 Agent Tool 必须同时注册到 Toolkit/ToolGroup 和角色 PermissionContext 白名单，并有配置一致性测试。
- 正式资源必须具备确定性 `validation_report` 和审核 `review_decision`；审核软建议不得阻止发布。
- 公共资源遍历全部有效 KG 节点，不保留十节点业务上限。
- 本计划执行时保留当前工作树已有修改，每次提交仅暂存本任务文件。
- 每阶段完成后更新 `WorkLine.md`，记录测试命令、结果和契约漂移。

---

## Phase A：学情事实与公共资源语义

### Task 1: 修复学情事实聚合

**Files:**
- Modify: `backend/app/services/evaluation_service.py`
- Modify: `backend/app/services/knowledge_progress.py`
- Test: `backend/tests/test_evaluation_facts.py`
- Test: `backend/tests/test_evaluation_service_refactored.py`

**Interfaces:**
- Consumes: `LearningActivity`, `QuizAnswer`, `QuizQuestion`, `build_node_progress_rows()`。
- Produces: `EvaluationService._assemble_evaluation_payload(user_id, course_id) -> dict`，其中章节进度、近期趋势和资源使用均来自学生事实。

- [ ] **Step 1: 写章节进度、近期十次和资源使用的失败测试**

```python
@pytest.mark.asyncio
async def test_evaluation_payload_uses_real_activity_and_latest_answers(db_session):
    service = EvaluationService(db_session)
    payload = await service._assemble_evaluation_payload("student-1", "course-1")

    assert payload["learning_progress"]["chapter_progress"][0]["time_spent"] > 0
    assert payload["quiz_results"][0]["recent_trend"] == pytest.approx(80.0)
    assert payload["resource_usage"]["by_type"]["lesson"] == 2
```

测试 fixture 创建十二条按时间递增的答题记录，前两条错误、后十条八对两错；创建两条学生实际查看 `lesson` 的 `LearningActivity`，同时创建更多未查看公共资源，确保统计不会读取资源库存量。

- [ ] **Step 2: 运行测试确认 RED**

Run: `cd backend && python3 -m pytest tests/test_evaluation_facts.py -v`

Expected: FAIL，当前章节时间为零、趋势读取错误窗口或资源使用等于库存数量。

- [ ] **Step 3: 最小实现真实事实聚合**

在 `EvaluationService` 中提取小函数：

```python
async def _build_chapter_progress(self, user_id: str, course_id: str) -> list[dict]: ...
async def _build_quiz_results(self, user_id: str, course_id: str) -> list[dict]: ...
async def _build_resource_usage(self, user_id: str, course_id: str) -> dict[str, int]: ...
```

近期趋势必须按 `QuizAnswer.create_time DESC` 选每个知识点最近十条，再按选中集合计算；资源使用只读取当前学生 `LearningActivity.resource_id` 对应资源类型；章节时间按活动节点或资源章节聚合，无法归属的行为不伪造章节完成度。

- [ ] **Step 4: 运行相关测试确认 GREEN**

Run: `cd backend && python3 -m pytest tests/test_evaluation_facts.py tests/test_evaluation_service_refactored.py tests/test_learning_activities.py -v`

Expected: PASS。

- [ ] **Step 5: 语法检查并提交**

Run: `python3 -m py_compile backend/app/services/evaluation_service.py backend/app/services/knowledge_progress.py`

Commit: `修复学情评估事实统计`

### Task 2: 建立结构化学情快照

**Files:**
- Modify: `agent_service_v2/src/agent_service_v2/schemas/evaluation.py`
- Modify: `agent_service_v2/src/agent_service_v2/agents/evaluation.py`
- Modify: `agent_service_v2/src/agent_service_v2/api/evaluation.py`
- Modify: `backend/app/models/others.py`
- Create: `backend/migrations/2026-07-12-add-evaluation-insight.sql`
- Modify: `backend/app/services/evaluation_service.py`
- Test: `agent_service_v2/tests/test_evaluation_api.py`
- Test: `backend/tests/test_evaluation_service_refactored.py`

**Interfaces:**
- Produces Agent response fields: `summary_text`, `strengths`, `weak_points`, `learning_preferences`, `next_actions`, `facts_version`, `generated_at`。
- Persists the structured object in `Evaluation.insight` JSON while retaining existing table fields.

- [ ] **Step 1: 写结构化输出与事实保护失败测试**

```python
def test_evaluation_enrichment_keeps_rule_tables_and_returns_insight():
    response = client.post("/agent/v2/evaluation/generations", json=payload)
    data = response.json()["data"]
    assert data["mastery_table"] == expected_rule_mastery
    assert data["insight"]["weak_points"][0]["evidence"]
    assert data["insight"]["facts_version"] == payload["facts_version"]
```

- [ ] **Step 2: 运行 Agent 与 Backend 测试确认 RED**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_evaluation_api.py -v`

Expected: FAIL，当前 schema 没有 `insight`。

- [ ] **Step 3: 增加 Pydantic insight schema 和安全 enrichment**

定义 `LearningInsight`, `InsightPoint`，LLM 只允许生成解释字段；`progress_table`、`mastery_table`、`resource_usage_table` 始终来自规则结果。解析失败继续返回规则 summary 和空数组。

- [ ] **Step 4: 增加数据库列和 Backend 持久化**

Migration:

```sql
ALTER TABLE evaluations ADD COLUMN insight JSON NULL AFTER summary_text;
```

ORM 增加 `insight: Mapped[dict | None]`，读写接口返回该字段。执行 migration 前必须由用户明确授权真实数据库变更；未授权时先完成代码和测试，记录待执行状态。

- [ ] **Step 5: 运行测试与提交**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_evaluation_api.py -v`

Run: `cd backend && python3 -m pytest tests/test_evaluation_service_refactored.py tests/test_evaluation_routes_refactored.py -v`

Expected: PASS。

Commit: `增加结构化学情快照`

### Task 3: 公共资源覆盖全部有效 KG 节点

**Files:**
- Modify: `backend/app/services/catalog_resource_generation_service.py`
- Modify: `backend/app/services/kg_resource_targets.py`
- Test: `backend/tests/test_admin_catalog_resource_generation.py`
- Test: `backend/tests/test_kg_resource_targets.py`

**Interfaces:**
- Produces: `select_valid_resource_targets(nodes) -> {targets, skipped}`，不接受业务数量上限。

- [ ] **Step 1: 写超过十节点仍全部选择的失败测试**

```python
def test_select_valid_resource_targets_keeps_all_supported_nodes():
    nodes = [supported_node(index) for index in range(14)]
    result = select_valid_resource_targets(nodes)
    assert len(result["targets"]) == 14
```

- [ ] **Step 2: 运行确认 RED**

Run: `cd backend && python3 -m pytest tests/test_kg_resource_targets.py tests/test_admin_catalog_resource_generation.py -v`

Expected: FAIL，当前只返回十个。

- [ ] **Step 3: 移除数量上限并保留有效性过滤**

重命名入口为 `select_valid_resource_targets(nodes)`；保留缺字段、重复和 `unsupported` 节点过滤；返回 `skipped` 及稳定原因，删除 `KG_RESOURCE_TARGET_LIMIT`。

- [ ] **Step 4: 验证每个有效节点创建子任务**

新增 service 测试断言 14 个有效节点产生 14 个 child task payload。

- [ ] **Step 5: 运行测试和提交**

Run: `cd backend && python3 -m pytest tests/test_kg_resource_targets.py tests/test_admin_catalog_resource_generation.py -v`

Expected: PASS。

Commit: `公共资源覆盖全部有效知识节点`

### Task 4: 修订公共资源类型和生成器

**Files:**
- Create: `agent_service_v2/src/agent_service_v2/schemas/resources.py`
- Create: `agent_service_v2/src/agent_service_v2/generators/public_resources.py`
- Modify: `agent_service_v2/src/agent_service_v2/api/knowledge.py`
- Modify: `backend/app/services/catalog_resource_generation_service.py`
- Modify: `backend/app/api/v1/webhooks.py`
- Modify: `frontend/src/components/admin/catalog/formatters.js`
- Modify: `frontend/src/components/admin/catalog/ResourceGenerationSection.jsx`
- Test: `agent_service_v2/tests/test_public_resource_generation.py`
- Test: `backend/tests/test_admin_catalog_resource_generation.py`
- Test: `frontend/src/components/admin/catalog/ResourceGenerationSection.test.jsx`

**Interfaces:**
- Public types: `lesson`, `diagram`, `example`。
- Agent result: `{title, type, format, content, description, chapter, knowledge_point, tags, sources}`。

- [ ] **Step 1: 写三类资源 schema 和映射失败测试**

```python
@pytest.mark.parametrize("resource_type,format_name", [
    ("lesson", "markdown"),
    ("diagram", "mermaid"),
    ("example", "markdown"),
])
def test_public_resource_type_has_truthful_format(resource_type, format_name): ...
```

- [ ] **Step 2: 运行各层测试确认 RED**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_public_resource_generation.py -v`

Run: `cd backend && python3 -m pytest tests/test_admin_catalog_resource_generation.py -v`

- [ ] **Step 3: 实现分类型 typed 生成器**

`lesson` 输出 Markdown，`diagram` 输出 Mermaid 源码并声明 `diagram_kind`，`example` 输出含可编译完整示例的 Markdown。不得保留 unknown 类型自动降级到 reading；未知类型应返回 schema validation failure。

- [ ] **Step 4: 同步 Backend allowlist、Webhook 和管理端选项**

所有调用点一次性改为三种新类型；旧数据库值通过 presenter 兼容显示，但新请求不得继续产生 `document/mindmap/reading/code`。

- [ ] **Step 5: 运行 Agent、Backend、Frontend 测试和提交**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_public_resource_generation.py tests/test_knowledge_api.py -v`

Run: `cd backend && python3 -m pytest tests/test_admin_catalog_resource_generation.py -v`

Run: `cd frontend && npm test -- --run src/components/admin/catalog/ResourceGenerationSection.test.jsx && npm run lint && npm run build`

Expected: PASS。

Commit: `统一公共资源类型语义`

## Phase B：个性化草案、验证、审核与发布

### Task 5: 建立个性化资源状态模型

**Files:**
- Create: `backend/app/models/personalized_resource_generation.py`
- Create: `backend/app/schemas/personalized_resource_generation.py`
- Create: `backend/migrations/2026-07-12-add-personalized-resource-generations.sql`
- Create: `backend/app/services/personalized_resource_generation_service.py`
- Test: `backend/tests/test_personalized_resource_generation_service.py`

**Interfaces:**
- States: `drafted`, `validating`, `validated`, `reviewing`, `approved`, `approved_with_advice`, `rejected`, `published`, `failed`。
- Service methods: `create_draft()`, `record_validation()`, `record_review()`, `publish()`。

- [ ] **Step 1: 写非法状态跳转和发布门槛失败测试**

```python
async def test_publish_requires_validation_and_review(service):
    draft = await service.create_draft(...)
    with pytest.raises(ResourcePublicationError, match="validation_required"):
        await service.publish(draft.id)
```

- [ ] **Step 2: 运行确认 RED**

Run: `cd backend && python3 -m pytest tests/test_personalized_resource_generation_service.py -v`

- [ ] **Step 3: 实现最小状态实体和 service**

草案只保存业务安全字段；代码题敏感草案继续使用专用 `CodeProblem` 边界。发布时在同一事务内创建正式资源/题目及 `UserPersonalizedResource` 关联。

- [ ] **Step 4: 增加迁移与导入检查**

Migration 创建 generation、artifact draft、validation、review 所需表或 JSON 字段及索引；真实 DB 执行仍需单独授权。

- [ ] **Step 5: 测试和提交**

Run: `cd backend && python3 -m pytest tests/test_personalized_resource_generation_service.py -v`

Run: `python3 -m py_compile backend/app/models/personalized_resource_generation.py backend/app/services/personalized_resource_generation_service.py`

Commit: `建立个性化资源发布状态机`

### Task 6: 拆分代码题验证与发布

**Files:**
- Modify: `backend/app/services/code_problem_service.py`
- Modify: `backend/app/api/v1/internal_ai_chat.py`
- Modify: `backend/app/schemas/code_problem.py`
- Modify: `agent_service_v2/src/agent_service_v2/tools/personal_code_problem.py`
- Test: `backend/tests/test_code_problem_service.py`
- Test: `backend/tests/test_internal_ai_chat.py`
- Test: `agent_service_v2/tests/test_personal_code_problem_tools.py`

**Interfaces:**
- `validate_personal_code_problem_draft(...) -> SanitizedValidationReport`
- `publish_validated_personal_code_problem(validation_id, review_id) -> CreatedCodeProblem`

- [ ] **Step 1: 写验证后不立即入库的失败测试**

```python
async def test_validation_returns_opaque_id_without_persisting_problem(...):
    report = await validate_personal_code_problem_draft(...)
    assert report.status == "passed"
    assert report.validation_id
    assert await count_code_problems(db) == 0
```

- [ ] **Step 2: 运行确认 RED**

Run: `cd backend && python3 -m pytest tests/test_code_problem_service.py tests/test_internal_ai_chat.py -v`

- [ ] **Step 3: 拆分验证与发布事务**

验证报告只公开编译状态、用例计数和通过计数；不返回参考解、隐藏输入或隐藏输出。发布必须校验 validation 归属、有效期、审核结论和未消费状态。

- [ ] **Step 4: 更新 Agent Tool 为草案验证工具**

将现有工具职责改为提交草案并获得 `validation_id`，不再生成正式 CodeSandboxCard；只有发布成功事件产生正式 card。

- [ ] **Step 5: 隐私回归、测试和提交**

Run: `cd backend && python3 -m pytest tests/test_code_problem_service.py tests/test_internal_ai_chat.py tests/test_oj_sandbox.py -v`

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_personal_code_problem_tools.py tests/test_agent_logging_middleware.py -v`

Commit: `拆分代码题验证与正式发布`

### Task 7: 统一个性化资源内部 API

**Files:**
- Create: `backend/app/api/v1/internal_personalized_resources.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/v1/personalized_resources.py`
- Modify: `backend/app/services/agent_client.py`
- Modify: `backend/app/schemas/personalized.py`
- Test: `backend/tests/test_internal_personalized_resources.py`
- Test: `backend/tests/test_personalized_resources.py`

**Interfaces:**
- Internal endpoints: create draft, attach validation, attach review, publish。
- Student endpoint accepts natural-language `goal` plus optional `knowledge_point`, `resource_preferences`, `difficulty` hints。

- [ ] **Step 1: 写权限、归属和发布门槛失败测试**
- [ ] **Step 2: 运行测试确认 RED**
- [ ] **Step 3: 实现薄 Router 与 Service 调用**
- [ ] **Step 4: 将旧固定 `generate_type` 路径保留为迁移适配器，不再扩展其类型**
- [ ] **Step 5: 运行测试和提交**

Run: `cd backend && python3 -m pytest tests/test_internal_personalized_resources.py tests/test_personalized_resources.py -v`

Commit: `统一个性化资源生成协议`

## Phase C：官方 AgentScope Agent Team

### Task 8: 建立 AgentScope App 托管入口

**Files:**
- Create: `agent_service_v2/src/agent_service_v2/team_app.py`
- Create: `agent_service_v2/src/agent_service_v2/team/storage.py`
- Create: `agent_service_v2/src/agent_service_v2/team/workspaces.py`
- Modify: `agent_service_v2/src/agent_service_v2/main.py`
- Test: `agent_service_v2/tests/test_team_app.py`

**Interfaces:**
- Uses verified `create_app(storage, message_bus, workspace_manager, custom_subagent_templates=...)`。
- Produces an internal AgentScope App mounted behind Agent Service v2; no raw endpoint is exposed directly to Frontend.

- [ ] **Step 1: 写本地 2.0.3 签名与 App 启动失败测试**

```python
def test_team_app_registers_custom_templates():
    app = build_team_app(test_dependencies)
    assert registered_template_types(app) == {"resource_generator", "resource_reviewer"}
```

- [ ] **Step 2: 运行确认 RED**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_team_app.py -v`

- [ ] **Step 3: 实现 Storage、MessageBus、WorkspaceManager 装配**

优先使用 AgentScope 2.0.3 已提供的本地测试实现；生产所需 Redis 或持久化依赖若项目未声明，必须先说明并获得用户批准，不能直接增加依赖或修改 `.env`。

- [ ] **Step 4: 挂载 App 并保留现有 `/agent/v2/workbench/chat`**

新 Team 入口先作为并行内部路径，旧 Workbench 在集成验证前保持可运行。

- [ ] **Step 5: 测试和提交**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_team_app.py tests/test_workbench_factory.py -v`

Commit: `接入AgentScope官方团队服务`

### Task 9: 注册生成与审核 Worker 模板及白名单

**Files:**
- Create: `agent_service_v2/src/agent_service_v2/agents/team_templates.py`
- Create: `agent_service_v2/src/agent_service_v2/agents/team_permissions.py`
- Create: `agent_service_v2/src/agent_service_v2/tools/resource_drafts.py`
- Create: `agent_service_v2/src/agent_service_v2/tools/resource_reviews.py`
- Test: `agent_service_v2/tests/test_team_templates.py`
- Test: `agent_service_v2/tests/test_team_permissions.py`

**Interfaces:**
- Template types: `resource_generator`, `resource_reviewer`。
- Reviewer decisions: `approved`, `approved_with_advice`, `rejected`。

- [ ] **Step 1: 写权限隔离与 Toolkit/白名单一致性失败测试**

```python
def test_reviewer_cannot_run_oj_or_publish():
    permission = build_reviewer_permission_context()
    assert "run_code_in_oj" not in permission.allow_rules
    assert "publish_personalized_resource" not in permission.allow_rules
```

- [ ] **Step 2: 运行确认 RED**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_team_templates.py tests/test_team_permissions.py -v`

- [ ] **Step 3: 实现两个 `SubAgentTemplate`**

明确设置 `extend_leader_permission_rules=False` 和 `extend_leader_working_directories=False`；`override_leader_mode` 先由测试验证行为再选择。Worker 只能通过 `TeamSay` 回报。

- [ ] **Step 4: 实现 typed draft/review tools**

所有工具返回结构化 observation；Reviewer 只读取脱敏 validation；硬失败与 warnings 分开。

- [ ] **Step 5: 测试和提交**

Commit: `隔离资源团队角色权限`

### Task 10: Leader 协调、事件适配和一次返修

**Files:**
- Create: `agent_service_v2/src/agent_service_v2/agents/resource_team_leader.py`
- Modify: `agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py`
- Modify: `agent_service_v2/src/agent_service_v2/runtime/edu_events.py`
- Create: `agent_service_v2/src/agent_service_v2/api/personalized_resources.py`
- Test: `agent_service_v2/tests/test_resource_agent_team.py`
- Test: `agent_service_v2/tests/test_protocol_adapter.py`

**Interfaces:**
- Request: natural-language goal plus trusted user/course/session context and optional hints。
- EDU events include role-aware `agent_started`, `agent_message`, `critic_completed`。

- [ ] **Step 1: 写真实 Team 生命周期集成失败测试**

测试必须观察 Leader session、generator worker session、reviewer worker session、`TeamSay` 和 `TeamDelete`；不能只 mock `run_leader_team_resource_generation`。

- [ ] **Step 2: 运行确认 RED**
- [ ] **Step 3: 实现 Leader prompt、Team 协调和最多一次返修规则**
- [ ] **Step 4: 将 AgentScope events 转为 EDU events，禁止原生对象泄露**
- [ ] **Step 5: 运行测试和提交**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_resource_agent_team.py tests/test_protocol_adapter.py tests/test_team_permissions.py -v`

Commit: `实现个性化资源Agent Team`

## Phase D：Frontend 统一入口和资源中心

### Task 11: 扩展个性化资源列表契约与卡片

**Files:**
- Modify: `frontend/src/api/services/personalizedResources.js`
- Create: `frontend/src/hooks/usePersonalizedResources.js`
- Modify: `frontend/src/pages/PersonalizedResources.jsx`
- Create: `frontend/src/components/personalized/PersonalizedResourceCard.jsx`
- Test: `frontend/src/hooks/usePersonalizedResources.test.js`
- Test: `frontend/src/pages/PersonalizedResources.test.jsx`

**Interfaces:**
- Displays five types, sources, generation status, review decision and warnings。

- [ ] **Step 1: 写五类资源、来源和审核状态失败测试**
- [ ] **Step 2: 运行确认 RED**
- [ ] **Step 3: 将数据和轮询移入 SWR hook，页面只组装组件**
- [ ] **Step 4: 实现统一卡片和旧值兼容 presenter**
- [ ] **Step 5: 测试、lint、build 和提交**

Run: `cd frontend && npm test -- --run src/hooks/usePersonalizedResources.test.js src/pages/PersonalizedResources.test.jsx && npm run lint && npm run build`

Commit: `统一个性化资源中心展示`

### Task 12: 智能生成页面与 AI Chat 保存

**Files:**
- Create: `frontend/src/pages/PersonalizedResourceGenerate.jsx`
- Create: `frontend/src/hooks/usePersonalizedResourceGeneration.js`
- Create: `frontend/src/components/personalized/AgentTeamProgress.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/pages/PersonalizedResources.jsx`
- Modify: `frontend/src/components/chat/ChatMessage.jsx`
- Modify: `frontend/src/hooks/useAIChat.js`
- Test: `frontend/src/pages/PersonalizedResourceGenerate.test.jsx`
- Test: `frontend/src/components/personalized/AgentTeamProgress.test.jsx`

**Interfaces:**
- Student submits `goal` plus optional hints。
- Renders only EDU events; saved AI Chat artifact appears in resource center through Backend refresh。

- [ ] **Step 1: 写自然语言提交、Team 进度和保存后刷新失败测试**
- [ ] **Step 2: 运行确认 RED**
- [ ] **Step 3: 实现独立生成页面和 role-aware 进度组件**
- [ ] **Step 4: 将 AI Chat 保存动作接到统一发布 API**
- [ ] **Step 5: 测试、lint、build 和提交**

Commit: `打通智能生成与AI对话资源保存`

### Task 13: `/learning-effects` 用户确认式生成入口

**Files:**
- Modify: `frontend/src/components/effects/EffectsSummaryCard.jsx`
- Modify: `frontend/src/pages/LearningEffects.jsx`
- Modify: `frontend/src/hooks/useLearningEffects.js`
- Test: `frontend/src/pages/LearningEffects.test.jsx`

**Interfaces:**
- Uses latest structured insight to prefill a natural-language goal; never auto-generates in background。

- [ ] **Step 1: 写必须用户点击确认才导航的失败测试**
- [ ] **Step 2: 运行确认 RED**
- [ ] **Step 3: 添加建议按钮与安全预填文本**
- [ ] **Step 4: 确认不会在页面加载时调用生成 API**
- [ ] **Step 5: 测试、lint、build 和提交**

Commit: `增加学情建议生成入口`

## Phase E：全量审核、回归与赛题报告

### Task 14: 代码质量与框架真实性审核

**Files:**
- Modify as required by findings: only files introduced or changed by Tasks 1-13
- Create: `docs/90-review/2026-07-12-resource-agent-team-code-audit.md`

- [ ] **Step 1: 运行 AgentScope framework audit**

确认实际入口使用 `create_app`、独立 session、Team tools、SubAgentTemplate、权限和事件流；搜索并记录残留伪 Team。

- [ ] **Step 2: 检查文件/函数长度、Router/Page 业务逻辑和注释风格**

超过 300 行文件或 50 行函数必须拆分或在审计中说明不可拆理由。

- [ ] **Step 3: 检查隐私、权限、日志和协议泄露**

搜索 `reference_solution`、`hidden_inputs`、AgentScope event 序列化和 Agent 直接 DB 调用。

- [ ] **Step 4: 修复所有 Critical/High/Medium 缺陷并补 RED/GREEN 回归测试**
- [ ] **Step 5: 提交审核报告和修复**

Commit: `审核资源多智能体实现质量`

### Task 15: 全量验证

**Files:**
- Modify: `WorkLine.md`

- [ ] **Step 1: Agent Service 全量测试**

Run: `cd agent_service_v2 && ./.venv/bin/pytest`

Expected: 全部 PASS，无未处理 warning/error。

- [ ] **Step 2: Backend 相关与全量测试**

Run: `cd backend && python3 -m pytest tests/test_evaluation_facts.py tests/test_evaluation_service_refactored.py tests/test_admin_catalog_resource_generation.py tests/test_personalized_resource_generation_service.py tests/test_internal_personalized_resources.py tests/test_code_problem_service.py tests/test_oj_sandbox.py -v`

随后 Run: `cd backend && python3 -m pytest`

Expected: 全部 PASS。

- [ ] **Step 3: Frontend 测试、lint 和 build**

Run: `cd frontend && npm test -- --run`

Run: `cd frontend && npm run lint && npm run build`

Expected: 全部 PASS。

- [ ] **Step 4: 静态和差异检查**

Run: `git diff --check`

Run: `rg -n "/agent/v1|KG_RESOURCE_TARGET_LIMIT|class CriticAgent|run_leader_team_resource_generation" frontend/src backend/app agent_service_v2/src`

对每个残留给出删除或保留证据。

- [ ] **Step 5: 更新 WorkLine 并提交验证记录**

Commit: `记录资源多智能体验证结果`

### Task 16: 审计赛题疑点与 TODO 并生成根目录报告

**Files:**
- Read only: `赛题疑点`
- Read only: `TODO.md`
- Create: `资源库与多智能体赛题完成度审计.md`

**Interfaces:**
- Report assesses only items present in the two named source files, but uses current code、测试、页面和文档作为完成证据。

- [ ] **Step 1: 将两个来源逐条拆成可验证要求**

不得把灵感或疑问直接标记为已完成；每条必须有代码路径、API、测试或 UI 行为证据。

- [ ] **Step 2: 对每条标记证据状态**

状态仅允许：`已完成`、`部分完成`、`未完成`、`无法验证`、`不再适用`。

- [ ] **Step 3: 对未完成项给出建议完成路径**

说明影响模块、依赖前置、建议顺序和验收证据，不编造实现状态。

- [ ] **Step 4: 写入根目录 Markdown 报告并自检**

报告至少包含：范围、证据方法、逐项矩阵、当前完整链路、比赛要求覆盖、剩余差距、建议路线和风险。

- [ ] **Step 5: 提交最终报告**

Commit: `审计赛题疑点与待办完成度`

## Plan Self-Review

- Spec coverage: 公共资源、五类个性化资源、学情快照、官方 Agent Team、白名单、确定性验证、宽松审核、持久化、前端入口、全量审核和最终报告均有对应任务。
- Placeholder scan: 计划不包含 TBD、TODO、FIXME 或“稍后实现”式占位；真实数据库迁移和新基础设施依赖明确保留用户授权门槛。
- Type consistency: `validation_id`、`review_decision`、五类资源、Team template 名称和 EDU events 在各阶段保持一致。
- Scope control: 视频、自动薄弱点生成和管理员人工发布系统明确排除，不作为完成条件。
