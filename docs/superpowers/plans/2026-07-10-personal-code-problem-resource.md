# AIChat 私有代码题资源实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让学生通过 AIChat 生成、经 Judge0 验证并持久化的私有代码题，使用服务端公开/隐藏固定用例完成安全判题。

**Architecture:** Backend 新增私有代码题、测试用例和验证报告的领域模型；它是题目归属、验证与判题的唯一事实源。Agent Service v2 以一个受限 typed tool 发起“验证并创建私有题”事务，之后写入只引用 `problem_id` 的工作区 artifact；Frontend 按题目详情 API 渲染卡片并提交判题。

**Tech Stack:** FastAPI、SQLAlchemy async、MySQL、httpx/Judge0、AgentScope 2.0.3、React、SWR、Vitest、pytest。

## Global Constraints

- Frontend 只经 Backend HTTP 调用；Agent Service v2 不写 MySQL，且不直连 Judge0。
- Backend Router 只做鉴权、参数校验与响应包装；领域逻辑在 `services/`。
- 不增加第三方依赖，不修改 `.env`、密钥、用户上传内容或数据库 volume。
- 学生私有题必须由 `owner_user_id` 隔离；隐藏用例与参考解不得进入 Client API、SSE 摘要、AI 答疑 prompt 或日志。
- 使用 AgentScope 2.0.3 已验证的 `FunctionTool`、`ToolGroup`、`Toolkit` 与 `reply_stream()`；不公开 AgentScope 对象。
- 维持既有 `/api/v1/sandbox/execute` 和 `/internal/ai-chat/oj/evaluate` 的自由 stdin 调试语义。
- 新增 Client API 与 Backend internal API 必须同步更新 OpenAPI、接口规范和 `WorkLine.md`。
- 本计划只实现学生私有题闭环，不迁移 Agent v1 的管理员通用资源生成。

---

## 文件结构

- `backend/app/models/code_problem.py`：私有/未来通用代码题与服务端测试用例 ORM。
- `backend/app/db/session.py`：在 `Base.metadata.create_all()` 前导入新 ORM 模型。
- `backend/app/schemas/code_problem.py`：Client 与 Agent internal API 的 request/response Pydantic schema。
- `backend/app/services/code_problem_service.py`：验证参考解、原子保存、公开详情投影和固定用例判题。
- `backend/app/api/v1/code_problems.py`：学生详情与提交 Router。
- `backend/app/api/v1/internal_code_problems.py`：Agent service-token 创建 Router。
- `agent_service_v2/src/agent_service_v2/tools/personal_code_problems.py`：有副作用的 AgentScope typed tool。
- `frontend/src/hooks/useCodeProblem.js`：题目详情 SWR hook 与提交 mutation。
- `frontend/src/components/workspace/plugins/codeSandbox/`：新版卡片、结果台与 AI 答疑摘要。
- `frontend/src/pages/CodeProblemPractice.jsx`：个性化资源页打开私有题的受保护容器。

## Task 1: 私有代码题持久化模型与迁移契约

**Files:**
- Create: `backend/app/models/code_problem.py`
- Modify: `backend/app/db/session.py`
- Modify: `backend/app/models/others.py`
- Modify: `backend/schema.sql`
- Create: `backend/tests/test_code_problem_models.py`

**Interfaces:**
- Produces `CodeProblem` 和 `CodeProblemTestCase` ORM；`UserPersonalizedResource.code_problem_id` 为 nullable FK。
- `CodeProblem.owner_user_id` 非空表示学生私有；本期保存的 `status` 固定为 `validated`。

- [ ] **Step 1: 写失败的 ORM/DDL 测试**

```python
def test_private_code_problem_schema_exposes_owner_and_case_linkage():
    assert CodeProblem.__tablename__ == "code_problems"
    assert "owner_user_id" in CodeProblem.__table__.c
    assert "code_problem_id" in UserPersonalizedResource.__table__.c
    assert CodeProblemTestCase.__table__.c.problem_id.foreign_keys
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_code_problem_models.py -q`

Expected: FAIL，因为 `app.models.code_problem` 不存在。

- [ ] **Step 3: 定义最小 ORM 与 SQL DDL**

```python
class CodeProblem(Base):
    __tablename__ = "code_problems"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    course_id: Mapped[str] = mapped_column(String(32), ForeignKey("courses.id"), nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    starter_templates: Mapped[dict] = mapped_column(JSON, nullable=False)
    reference_solutions: Mapped[dict] = mapped_column(JSON, nullable=False)
    validation_report: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="validated")

class CodeProblemTestCase(Base):
    __tablename__ = "code_problem_test_cases"
    problem_id: Mapped[str] = mapped_column(String(32), ForeignKey("code_problems.id"), nullable=False)
    stdin: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

Add equivalent `CREATE TABLE` definitions and `user_personalized_resources.code_problem_id` foreign key to `backend/schema.sql`; retain existing `resource_id` and `question_id` columns.
Add `import app.models.code_problem  # noqa: E402` after the existing model imports in
`backend/app/db/session.py`, so `init_db()` registers the tables in test and local startup.

- [ ] **Step 4: 运行模型测试和导入检查**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_code_problem_models.py -q && ../.venv/bin/python -m py_compile app/models/code_problem.py app/models/others.py`

Expected: PASS。

- [ ] **Step 5: 提交模型批次**

```bash
git add backend/app/models/code_problem.py backend/app/db/session.py backend/app/models/others.py backend/schema.sql backend/tests/test_code_problem_models.py
git commit -m "feat: 增加私有代码题数据模型"
```

## Task 2: Backend 验证、原子保存与私有访问服务

**Files:**
- Create: `backend/app/schemas/code_problem.py`
- Create: `backend/app/services/code_problem_service.py`
- Create: `backend/tests/test_code_problem_service.py`

**Interfaces:**
- Consumes `CodeProblemDraft`, `CodeProblem`, `CodeProblemTestCase` 和 `execute_code_in_oj(code, language, stdin)`。
- Produces `create_validated_personal_problem(db, *, owner_user_id, course_id, conversation_id, run_id, draft)`、`get_private_problem_detail(...)`、`submit_private_problem(...)`。

- [ ] **Step 1: 写服务层失败测试**

```python
@pytest.mark.asyncio
async def test_create_validated_problem_uses_reference_stdout_and_creates_personal_link(db, mock_oj):
    mock_oj.side_effect = [ok(stdout="3\\n"), ok(stdout="42\\n")]
    created = await create_validated_personal_problem(
        db, owner_user_id="student-1", course_id="course-1", conversation_id="conv-1", run_id="run-1",
        draft=CodeProblemDraft(title="求和", statement="...", language="python", starter_code="", reference_solution="...", test_inputs=[...]),
    )
    assert created.problem.owner_user_id == "student-1"
    assert created.public_case_count == 1
    assert created.hidden_case_count == 1
    assert created.problem.validation_report["status"] == "validated"

@pytest.mark.asyncio
async def test_hidden_case_failure_does_not_return_input_or_expected_output(db, saved_problem, mock_oj):
    result = await submit_private_problem(db, owner_user_id="student-1", problem_id=saved_problem.id, language="python", code="...")
    assert result.failed_case == {"visibility": "hidden", "message": "隐藏用例未通过"}
```

- [ ] **Step 2: 运行服务测试确认失败**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_code_problem_service.py -q`

Expected: FAIL，因为 schema 与 service 尚未定义。

- [ ] **Step 3: 实现 Draft schema、验证和保存事务**

```python
class CodeProblemDraft(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    statement: str = Field(min_length=1, max_length=10000)
    language: Literal["c", "cpp", "python"]
    starter_code: str = Field(max_length=20000)
    reference_solution: str = Field(min_length=1, max_length=30000)
    test_inputs: list[CodeProblemTestInput] = Field(min_length=2, max_length=8)

async def create_validated_personal_problem(...):
    _validate_draft_shape(draft)
    executed_cases = await _execute_reference_cases(draft)
    return await _persist_problem_transaction(..., executed_cases)
```

Implement `_normalize_output()` with CRLF normalization, trailing whitespace removal per line, and trailing blank-line removal. Validate at least one public and one hidden input; reject duplicate inputs and any reference compile/runtime/timeout failure. Store stdout returned by Judge0 as `expected_output`; never accept an expected output from the Agent draft.

- [ ] **Step 4: 实现 detail/submit 安全投影**

```python
async def get_private_problem_detail(db, *, owner_user_id: str, problem_id: str) -> CodeProblemDetail: ...
async def submit_private_problem(db, *, owner_user_id: str, problem_id: str, language: str, code: str) -> CodeSubmissionResult: ...
```

Require `problem.owner_user_id == owner_user_id` in both paths. On a public failure return the exact public input, expected and actual output; on a hidden failure return only the fixed anonymous object used in the failing test.

- [ ] **Step 5: 运行服务回归**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_code_problem_service.py tests/test_oj_sandbox.py -q`

Expected: PASS。

- [ ] **Step 6: 提交服务批次**

```bash
git add backend/app/schemas/code_problem.py backend/app/services/code_problem_service.py backend/tests/test_code_problem_service.py
git commit -m "feat: 验证并保存学生私有代码题"
```

## Task 3: Client 与 internal API 路由、权限和契约文档

**Files:**
- Create: `backend/app/api/v1/code_problems.py`
- Create: `backend/app/api/v1/internal_code_problems.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_oj_sandbox.py`
- Modify: `docs/10-client-api/Client-API.openapi.json`
- Modify: `docs/10-client-api/API_前端接口规范.md`
- Modify: `docs/20-agent-api/API_Agent内部接口规范.md`

**Interfaces:**
- Produces `GET /api/v1/sandbox/problems/{problem_id}` and `POST /api/v1/sandbox/problems/{problem_id}/submit`.
- Produces `POST /internal/ai-chat/code-problems/create-validated` protected by `X-Internal-Agent-Token`.

- [ ] **Step 1: 写路由失败测试**

```python
@pytest.mark.asyncio
async def test_student_submit_rejects_other_users_and_hides_private_cases(client, saved_problem):
    response = await client.post(f"/api/v1/sandbox/problems/{saved_problem.id}/submit", json={"language": "python", "code": "..."})
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_internal_create_requires_token(client, valid_draft_payload):
    response = await client.post("/internal/ai-chat/code-problems/create-validated", json=valid_draft_payload)
    assert response.status_code == 403
```

- [ ] **Step 2: 运行路由测试确认失败**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_oj_sandbox.py -q`

Expected: FAIL，新增路径尚未注册。

- [ ] **Step 3: 实现薄 Router 与 response schemas**

```python
@router.post("/sandbox/problems/{problem_id}/submit")
async def submit_problem(problem_id: str, req: CodeSubmissionRequest, current_user=Depends(get_current_user), db=Depends(get_db)):
    return success(await submit_private_problem(db, owner_user_id=current_user.id, problem_id=problem_id, **req.model_dump()))

@router.post("/code-problems/create-validated")
async def create_validated(req: InternalCreateCodeProblemRequest, _auth=Depends(verify_internal_agent_token), db=Depends(get_db)):
    return success(await create_validated_personal_problem(db, **req.model_dump()))
```

Mount both routers in `app/main.py`. Document all request/response fields, error status semantics and the explicit ban on hidden-case projection. Do not alter `/sandbox/execute` or `/internal/ai-chat/oj/evaluate`.

- [ ] **Step 4: 运行 API 与 OpenAPI 回归**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_oj_sandbox.py tests/test_internal_ai_chat.py -q && ../.venv/bin/python -m py_compile app/api/v1/code_problems.py app/api/v1/internal_code_problems.py`

Expected: PASS。

- [ ] **Step 5: 提交 API 批次**

```bash
git add backend/app/api/v1/code_problems.py backend/app/api/v1/internal_code_problems.py backend/app/main.py backend/tests/test_oj_sandbox.py docs/10-client-api docs/20-agent-api
git commit -m "feat: 提供私有代码题详情与判题接口"
```

## Task 4: Agent v2 创建私有题工具与可观察事件

**Files:**
- Create: `agent_service_v2/src/agent_service_v2/tools/personal_code_problems.py`
- Modify: `agent_service_v2/src/agent_service_v2/tools/workbench_toolkit.py`
- Modify: `agent_service_v2/src/agent_service_v2/agents/workbench_factory.py`
- Modify: `agent_service_v2/src/agent_service_v2/agents/permissions.py`
- Modify: `agent_service_v2/src/agent_service_v2/agents/prompts.py`
- Modify: `agent_service_v2/tests/test_workbench_toolkit.py`
- Modify: `agent_service_v2/tests/test_workbench_factory.py`
- Create: `agent_service_v2/tests/test_personal_code_problem_tools.py`

**Interfaces:**
- Consumes Backend internal API and closure-bound `user_id`, `course_id`, `conversation_id`, `run_id`.
- Produces AgentScope `FunctionTool` named `create_validated_personal_code_problem` and structured `tool_completed` facts.

- [ ] **Step 1: 写 Agent tool 失败测试**

```python
def test_create_personal_problem_tool_never_accepts_model_supplied_owner_or_course():
    tool = build_personal_code_problem_tools(client=FakeClient(), user_id="u1", course_id="c1", conversation_id="conv1", run_id="run1")[0]
    asyncio.run(tool.call(title="题", statement="...", language="python", starter_code="", reference_solution="...", test_inputs=[...], owner_user_id="other"))
    assert client.calls[0][1]["user_id"] == "u1"
    assert "owner_user_id" not in client.calls[0][1]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd agent_service_v2 && ./.venv/bin/python -m pytest tests/test_personal_code_problem_tools.py -q`

Expected: FAIL，因为 builder 尚不存在。

- [ ] **Step 3: 实现 typed tool 与 Toolkit 注册**

```python
def build_personal_code_problem_tools(*, client, user_id, course_id, conversation_id, run_id) -> list[FunctionTool]:
    async def create_validated_personal_code_problem(title: str, statement: str, language: str, starter_code: str, reference_solution: str, test_inputs: list[dict], **_ignored):
        return await client.post_json("/internal/ai-chat/code-problems/create-validated", {
            "user_id": user_id, "course_id": course_id, "conversation_id": conversation_id,
            "run_id": run_id, "title": title, "statement": statement, "language": language,
            "starter_code": starter_code, "reference_solution": reference_solution, "test_inputs": test_inputs,
        })
```

Register a `personal_code_problems` `ToolGroup`. Permit the tool only for the active student chat context; it is a user-requested persistence action, not a general unrestricted write tool. Update the prompt: call it only for a request to create a coding exercise; write `CodeSandboxCard` only after it returns `problem_id`; never include a reference solution or tests in the artifact.

- [ ] **Step 4: 运行 Agent 回归**

Run: `cd agent_service_v2 && ./.venv/bin/python -m pytest tests/test_personal_code_problem_tools.py tests/test_workbench_toolkit.py tests/test_workbench_factory.py tests/test_protocol_adapter.py -q`

Expected: PASS。

- [ ] **Step 5: 提交 Agent 批次**

```bash
git add agent_service_v2/src/agent_service_v2 agent_service_v2/tests/test_personal_code_problem_tools.py agent_service_v2/tests/test_workbench_toolkit.py agent_service_v2/tests/test_workbench_factory.py
git commit -m "feat: AIChat 验证并保存私有代码题工具"
```

## Task 5: 新版 CodeSandboxCard、详情读取和安全提交 UI

**Files:**
- Create: `frontend/src/api/services/codeProblems.js`
- Create: `frontend/src/hooks/useCodeProblem.js`
- Modify: `frontend/src/components/workspace/plugins/codeSandbox/CodeSandboxCard.jsx`
- Modify: `frontend/src/components/workspace/plugins/codeSandbox/useCodeSandboxExecution.js`
- Modify: `frontend/src/components/workspace/plugins/codeSandbox/CodeSandboxConsole.jsx`
- Modify: `frontend/src/components/workspace/plugins/codeSandbox/codeSandboxViewModel.js`
- Modify: `frontend/src/components/workspace/plugins/CodeSandboxCard.test.jsx`
- Create: `frontend/src/hooks/useCodeProblem.test.js`

**Interfaces:**
- `getCodeProblem(problemId)` returns public title, statement, templates and public cases only.
- `submitCodeProblem(problemId, { language, code })` returns `CodeSubmissionResult` without hidden data.
- New card props are `{ problem_id, language }`; legacy `{ question_text, code, language, default_stdin }` remains a free-run compatibility path.

- [ ] **Step 1: 写前端失败测试**

```jsx
test('private code problem card submits only problem id, language and code', async () => {
  render(<CodeSandboxCard problem_id="p1" language="python" />);
  await screen.findByText('两个整数求和');
  fireEvent.click(screen.getByRole('button', { name: '提交判题' }));
  expect(submitCodeProblem).toHaveBeenCalledWith('p1', { language: 'python', code: expect.any(String) });
  expect(screen.queryByLabelText(/stdin/i)).toBeNull();
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm run test:unit -- src/components/workspace/plugins/CodeSandboxCard.test.jsx src/hooks/useCodeProblem.test.js`

Expected: FAIL，因为 card 仍需要 `default_stdin` 并调用 `/sandbox/execute`。

- [ ] **Step 3: 实现 API service、SWR hook 与 card 分支**

```javascript
export const getCodeProblem = (problemId) => apiClient.get(`/sandbox/problems/${problemId}`);
export const submitCodeProblem = (problemId, body) => apiClient.post(`/sandbox/problems/${problemId}/submit`, body);

export const useCodeProblem = (problemId) => useSWR(
  problemId ? ['code-problem', problemId] : null,
  ([, id]) => getCodeProblem(id).then((response) => response.data),
);
```

Render public sample input/output from the detail response. Remove editable stdin only for `problem_id` cards; button text is `提交判题`. Render `passed_cases/total_cases`; reveal exact values only when `failed_case.visibility === 'public'`. Keep the existing legacy run branch intact. `buildAskAIPrompt` must accept only `statement`, student code and the safe result summary.

- [ ] **Step 4: 运行前端回归**

Run: `cd frontend && npm run test:unit -- src/components/workspace/plugins/CodeSandboxCard.test.jsx src/components/workspace/plugins/codeSandbox/codeSandboxViewModel.test.js src/hooks/useCodeProblem.test.js && npm run lint && npm run build`

Expected: PASS，build 仅可保留既有 chunk-size warning。

- [ ] **Step 5: 提交前端卡片批次**

```bash
git add frontend/src/api/services/codeProblems.js frontend/src/hooks/useCodeProblem.js frontend/src/components/workspace/plugins/codeSandbox frontend/src/components/workspace/plugins/CodeSandboxCard.test.jsx frontend/src/hooks/useCodeProblem.test.js
git commit -m "feat: 私有代码题固定用例判题卡"
```

## Task 6: 个性化资源入口与删除闭环

**Files:**
- Modify: `backend/app/api/v1/personalized_resources.py`
- Create: `backend/tests/test_personalized_resources.py`
- Create: `frontend/src/components/personalized/CodeProblemResourceCard.jsx`
- Modify: `frontend/src/pages/PersonalizedResources.jsx`
- Modify: `frontend/src/App.jsx`
- Create: `frontend/src/pages/CodeProblemPractice.jsx`
- Create: `frontend/src/pages/CodeProblemPractice.test.jsx`

**Interfaces:**
- Personalized list item adds optional `code_problem` summary `{ id, title, language, difficulty, status }`.
- `/code-problems/:problemId` renders the same private `CodeSandboxCard` under protected student routing.

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.asyncio
async def test_personalized_resource_list_projects_owned_code_problem(client, private_problem):
    response = await client.get('/api/v1/personalized-resources', params={'course_id': private_problem.course_id})
    assert response.json()['data']['items'][0]['code_problem']['id'] == private_problem.id
```

```jsx
test('personal code resource opens its protected practice page', () => {
  render(<CodeProblemResourceCard item={{ code_problem: { id: 'p1', title: '求和' } }} />);
  expect(screen.getByRole('link', { name: '开始编程练习' })).toHaveAttribute('href', '/code-problems/p1');
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_personalized_resources.py -q && cd ../frontend && npm run test:unit -- src/pages/CodeProblemPractice.test.jsx`

Expected: FAIL，因为列表没有 `code_problem` 投影且路由不存在。

- [ ] **Step 3: 实现安全投影、卡片和路由**

Extend the existing batch preload in `list_personalized_resources()` with `code_problem_ids`, query only non-deleted records owned by `current_user.id`, and return only summary fields. Extend deletion to soft-delete the owned problem after the personalized link is deleted. Add `CodeProblemResourceCard` as a props-only view and a protected `CodeProblemPractice` page that reads `problemId` from route params and renders `<CodeSandboxCard problem_id={problemId} language="python" />`.

- [ ] **Step 4: 运行入口回归**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_personalized_resources.py tests/test_code_problem_service.py -q && cd ../frontend && npm run test:unit -- src/pages/CodeProblemPractice.test.jsx src/components/workspace/plugins/CodeSandboxCard.test.jsx && npm run lint && npm run build`

Expected: PASS。

- [ ] **Step 5: 提交资源入口批次**

```bash
git add backend/app/api/v1/personalized_resources.py backend/tests/test_personalized_resources.py frontend/src/components/personalized/CodeProblemResourceCard.jsx frontend/src/pages/PersonalizedResources.jsx frontend/src/pages/CodeProblemPractice.jsx frontend/src/pages/CodeProblemPractice.test.jsx frontend/src/App.jsx
git commit -m "feat: 个性化资源展示私有代码题"
```

## Task 7: 端到端回归、契约复核与工作存档

**Files:**
- Modify: `WorkLine.md`
- Modify: `docs/10-client-api/Client-API.openapi.json`
- Modify: `docs/10-client-api/API_前端接口规范.md`
- Modify: `docs/20-agent-api/API_Agent内部接口规范.md`

**Interfaces:**
- Confirms all new Client/internal API paths and no new public Agent v2 route.

- [ ] **Step 1: 核对接口字段与隐藏数据边界**

Run: `rg -n "reference_solution|expected_output|stdin" backend/app/api/v1 frontend/src agent_service_v2/src`

Expected: student detail/submit response builders、SSE summaries和 AI prompt 中不出现 reference solution；隐藏 `expected_output` 只在 Backend service persistence/comparison paths 出现。

- [ ] **Step 2: 运行完整相关验证**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_code_problem_models.py tests/test_code_problem_service.py tests/test_oj_sandbox.py tests/test_personalized_resources.py tests/test_internal_ai_chat.py -q`

Expected: PASS。

Run: `cd agent_service_v2 && ./.venv/bin/python -m pytest tests/test_personal_code_problem_tools.py tests/test_oj_execution_tools.py tests/test_workbench_toolkit.py tests/test_workbench_factory.py tests/test_protocol_adapter.py tests/test_workbench_session.py -q`

Expected: PASS。

Run: `cd frontend && npm run test:unit -- src/components/workspace/plugins/CodeSandboxCard.test.jsx src/components/workspace/plugins/codeSandbox/codeSandboxViewModel.test.js src/hooks/useCodeProblem.test.js src/pages/CodeProblemPractice.test.jsx && npm run lint && npm run build`

Expected: PASS，build 仅保留既有 chunk-size warning。

- [ ] **Step 3: 追加 WorkLine 并最终提交**

Append one record that names the new private ownership boundary, tests, client/internal contract additions and the explicit statement that Agent v1 common resource generation remains unchanged.

```bash
git add WorkLine.md docs/10-client-api docs/20-agent-api
git commit -m "docs: 记录私有代码题判题接口"
```

## Plan Self-Review

- Spec coverage: Tasks 1–3 cover data ownership, validation, persistence, client/internal contracts and security; Task 4 covers AgentScope v2 tools/SSE; Tasks 5–6 cover card and personalized-resource UX; Task 7 covers verification and recordkeeping.
- Placeholder scan: the plan uses no deferred implementation markers; every task has named files, concrete interfaces, tests and commands.
- Type consistency: `problem_id` is the only browser-side identity; `CodeProblemDraft` is Agent-to-Backend-only; `CodeSubmissionResult` is projected by the student submit API; `code_problem_id` is the personalized-resource linkage.
