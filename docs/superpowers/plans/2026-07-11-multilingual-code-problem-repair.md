# 多语言代码题修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 AIChat 私有代码题可靠支持 c、cpp、python、java、go、javascript，并把参数拒绝、服务退化和成功在产品界面中明确区分。

**Architecture:** Backend 内部语言注册表是规范名称、别名和 Judge0 ID 的唯一事实源；schema 和 Judge0 服务均复用它。Agent Service 保持 HTTP 工具边界并返回结构化业务结果，协议适配器和前端只消费安全的 status/reason，不改变 AgentScope 的真实生命周期状态。

**Tech Stack:** FastAPI、Pydantic v2、SQLAlchemy async、httpx/Judge0、AgentScope 2.0.3、React、Vitest、pytest。

## Global Constraints

- Frontend 只通过 Backend HTTP；Agent Service v2 不写 MySQL、不直连 Judge0，Backend 不导入 Agent 模块。
- 不引入依赖、不改 `.env`、不改数据库结构；已有迁移已应用到本地开发库。
- 私有代码题的参考解、隐藏输入和预期输出不得进入 Agent 日志、SSE、artifact 或客户端。
- 规范语言值固定为 `c`、`cpp`、`python`、`java`、`go`、`javascript`；未知值不能被表述为服务不可用。
- Router/Page 保持薄层；单个函数只做语言归一化、HTTP 错误分类、协议映射或视图映射中的一类职责。
- 完成功能修复后，审查 Backend 与 Agent Service v2 的实际运行入口、内聚、体积、边界和 AgentScope 原生使用。

---

### Task 1: Backend 规范语言注册表与代码题 schema

**Files:**
- Create: `backend/app/services/code_language.py`
- Modify: `backend/app/schemas/code_problem.py`
- Modify: `backend/app/services/oj_execution_service.py`
- Create: `backend/tests/test_code_language.py`
- Modify: `backend/tests/test_code_problem_service.py`

**Interfaces:**
- Produces `normalize_code_language(value: str) -> str` and `judge0_language_id(language: str) -> int`.
- Produces canonical `SUPPORTED_CODE_LANGUAGES` and aliases for all six teaching languages.
- `CodeProblemDraft.language` persists only canonical values.

- [ ] **Step 1: Write failing language-registry tests**

```python
import pytest

from app.services.code_language import (
    UnsupportedCodeLanguageError,
    judge0_language_id,
    normalize_code_language,
)

@pytest.mark.parametrize(
    ("raw", "expected"),
    [("C", "c"), ("C++", "cpp"), ("Python3", "python"),
     ("Java", "java"), ("Golang", "go"), ("Node.js", "javascript")],
)
def test_normalize_code_language_accepts_common_aliases(raw, expected):
    assert normalize_code_language(raw) == expected

def test_normalize_code_language_rejects_unknown_value():
    with pytest.raises(UnsupportedCodeLanguageError):
        normalize_code_language("rust")

def test_judge0_language_id_uses_canonical_language():
    assert judge0_language_id("C++") == 54
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `cd backend && ../.venv/bin/pytest tests/test_code_language.py -q`

Expected: collection fails because `app.services.code_language` does not exist.

- [ ] **Step 3: Implement the focused registry**

```python
class UnsupportedCodeLanguageError(ValueError):
    pass

SUPPORTED_CODE_LANGUAGES = ("c", "cpp", "python", "java", "go", "javascript")

_LANGUAGE_ALIASES = {
    "c": "c", "c++": "cpp", "cpp": "cpp",
    "python": "python", "python3": "python",
    "java": "java", "go": "go", "golang": "go",
    "javascript": "javascript", "js": "javascript", "node.js": "javascript",
}

_JUDGE0_LANGUAGE_IDS = {"c": 50, "cpp": 54, "python": 71, "java": 62, "go": 60, "javascript": 63}

def normalize_code_language(value: str) -> str:
    normalized = _LANGUAGE_ALIASES.get(value.strip().lower())
    if normalized is None:
        raise UnsupportedCodeLanguageError(value)
    return normalized

def judge0_language_id(value: str) -> int:
    return _JUDGE0_LANGUAGE_IDS[normalize_code_language(value)]
```

Use a `field_validator("language", mode="before")` in `CodeProblemDraft` to call `normalize_code_language`. Replace both direct `LANGUAGE_MAP` lookups in `oj_execution_service.py` with `judge0_language_id`, translating `UnsupportedCodeLanguageError` to existing `OJExecutionError("unsupported_language", ...)`.

- [ ] **Step 4: Run backend unit and service regressions**

Run: `cd backend && ../.venv/bin/pytest tests/test_code_language.py tests/test_code_problem_service.py tests/test_oj_sandbox.py -q`

Expected: PASS.

- [ ] **Step 5: Commit Backend language batch**

```bash
git add backend/app/services/code_language.py backend/app/schemas/code_problem.py backend/app/services/oj_execution_service.py backend/tests/test_code_language.py backend/tests/test_code_problem_service.py
git commit -m "fix: 统一代码题语言契约"
```

### Task 2: Agent HTTP 分类与产品工具状态

**Files:**
- Modify: `agent_service_v2/src/agent_service_v2/tools/backend_learning_client.py`
- Modify: `agent_service_v2/src/agent_service_v2/tools/personal_code_problem.py`
- Modify: `agent_service_v2/src/agent_service_v2/agents/prompts.py`
- Modify: `agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py`
- Modify: `agent_service_v2/tests/test_backend_learning_client.py`
- Modify: `agent_service_v2/tests/test_personal_code_problem_tools.py`
- Modify: `agent_service_v2/tests/test_protocol_adapter.py`

**Interfaces:**
- `BackendLearningClientError.reason` categorizes network, validation, rejection and server failures without raw Backend body.
- `create_validated_personal_code_problem` returns `created`, `rejected`, `degraded` or `unavailable` with a safe reason.
- Adapter forwards business `status` and `reason` in its stable `tool_completed` payload.

- [ ] **Step 1: Write failing HTTP classification and tool-result tests**

```python
async def handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(422, json={"detail": {"code": 40001}}, request=request)

with pytest.raises(BackendLearningClientError, match="backend_validation_error"):
    asyncio.run(client.post_json("/internal/ai-chat/code-problems", {}))

assert data == {"status": "rejected", "reason": "backend_validation_error"}
assert event.payload["status"] == "rejected"
assert event.payload["reason"] == "backend_validation_error"
```

- [ ] **Step 2: Run targeted tests and confirm RED**

Run: `cd agent_service_v2 && ./.venv/bin/pytest -s tests/test_backend_learning_client.py tests/test_personal_code_problem_tools.py tests/test_protocol_adapter.py -q`

Expected: assertion failures because all HTTP errors are currently `backend_http_error` and the tool always returns `degraded`.

- [ ] **Step 3: Implement one-way error classification**

```python
def _reason_for_status(status_code: int) -> str:
    if status_code == 422:
        return "backend_validation_error"
    if 400 <= status_code < 500:
        return "backend_rejected"
    return "backend_server_error"
```

Keep raw response bodies out of exceptions and logs. In the personal code-problem tool, map validation/rejection errors to `status: "rejected"`; map 5xx to `degraded`; preserve timeout/unavailable values. Update the prompt to state that only `backend_timeout` and `backend_unavailable` may be described as an unavailable service.

- [ ] **Step 4: Verify Agent tool and protocol regressions**

Run: `cd agent_service_v2 && ./.venv/bin/pytest -s tests/test_backend_learning_client.py tests/test_personal_code_problem_tools.py tests/test_protocol_adapter.py tests/test_workbench_factory.py -q`

Expected: PASS.

- [ ] **Step 5: Commit Agent batch**

```bash
git add agent_service_v2/src/agent_service_v2/tools/backend_learning_client.py agent_service_v2/src/agent_service_v2/tools/personal_code_problem.py agent_service_v2/src/agent_service_v2/agents/prompts.py agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py agent_service_v2/tests/test_backend_learning_client.py agent_service_v2/tests/test_personal_code_problem_tools.py agent_service_v2/tests/test_protocol_adapter.py
git commit -m "fix: 区分代码题工具失败语义"
```

### Task 3: 前端工具卡语义与多语言文件名

**Files:**
- Modify: `frontend/src/utils/chatStreamEvents.js`
- Modify: `frontend/src/utils/__tests__/chatStreamEvents.test.js`
- Modify: `frontend/src/components/workspace/plugins/codeSandbox/codeSandboxViewModel.js`
- Modify: `frontend/src/components/workspace/plugins/codeSandbox/codeSandboxViewModel.test.js`

**Interfaces:**
- A tool call with `status` rejected/degraded/unavailable renders `error`; successful statuses remain `completed`.
- Source labels use `main.c`, `main.cpp`, `main.py`, `Main.java`, `main.go`, `main.js`.

- [ ] **Step 1: Write failing frontend tests**

```javascript
expect(reduceAssistantMessageForEvent(message, {
  type: 'tool_completed',
  payload: { tool_call_id: 'tool-1', state: 'success', status: 'rejected', reason: 'backend_validation_error' },
}).toolCalls[0]).toMatchObject({ status: 'error', outputSummary: 'backend_validation_error' });

expect(getSourceFilename('java')).toBe('Main.java');
expect(getSourceFilename('javascript')).toBe('main.js');
```

- [ ] **Step 2: Run targeted tests and confirm RED**

Run: `cd frontend && npm run test -- --run src/utils/__tests__/chatStreamEvents.test.js src/components/workspace/plugins/codeSandbox/codeSandboxViewModel.test.js`

Expected: failures because only AgentScope `state` decides error and file names use a generic extension.

- [ ] **Step 3: Implement UI-only status mapping**

```javascript
const failedToolStatuses = new Set(['rejected', 'degraded', 'unavailable']);
const isFailed = event.payload?.state === 'error' || failedToolStatuses.has(event.payload?.status);
```

Use `event.payload?.output_summary || event.payload?.reason` for the display summary. Extend `getSourceFilename()` with explicit Java, Go and JavaScript branches; do not change execution request paths or card state management.

- [ ] **Step 4: Run frontend targeted regressions**

Run: `cd frontend && npm run test -- --run src/utils/__tests__/chatStreamEvents.test.js src/components/workspace/plugins/codeSandbox/codeSandboxViewModel.test.js`

Expected: PASS.

- [ ] **Step 5: Commit frontend batch**

```bash
git add frontend/src/utils/chatStreamEvents.js frontend/src/utils/__tests__/chatStreamEvents.test.js frontend/src/components/workspace/plugins/codeSandbox/codeSandboxViewModel.js frontend/src/components/workspace/plugins/codeSandbox/codeSandboxViewModel.test.js
git commit -m "fix: 显示代码题工具的真实失败状态"
```

### Task 4: 契约记录、完整验证与运行时回归

**Files:**
- Modify: `docs/20-agent-api/API_Agent内部接口规范.md`
- Modify: `docs/10-client-api/API_前端接口规范.md`
- Modify: `WorkLine.md`

**Interfaces:**
- Documents canonical language values, accepted aliases, and `rejected` versus unavailable semantics without changing public paths.

- [ ] **Step 1: Add contract regression notes**

Document six canonical stored values and that aliases are input normalization only. Document that `backend_validation_error` is a request rejection, while only timeout/unavailable represents service reachability.

- [ ] **Step 2: Run the full applicable verification suite**

Run:

```bash
cd backend && ../.venv/bin/pytest tests/test_code_language.py tests/test_code_problem_service.py tests/test_oj_sandbox.py -q
cd ../agent_service_v2 && ./.venv/bin/pytest -s tests/test_backend_learning_client.py tests/test_personal_code_problem_tools.py tests/test_protocol_adapter.py tests/test_workbench_factory.py -q
cd ../frontend && npm run test -- --run src/utils/__tests__/chatStreamEvents.test.js src/components/workspace/plugins/codeSandbox/codeSandboxViewModel.test.js
npm run lint
npm run build
```

Expected: all commands exit 0.

- [ ] **Step 3: Perform authenticated runtime smoke**

Use the running Backend's existing internal auth configuration only through a local diagnostic harness. Verify C++, Python3, Java, Go and JavaScript normalization at schema/service level; do not create a duplicate student problem or expose a reference solution.

- [ ] **Step 4: Commit documentation and verification record**

```bash
git add docs/10-client-api docs/20-agent-api WorkLine.md
git commit -m "docs: 记录多语言代码题契约"
```

### Task 5: Backend 与 AgentScope v2 质量审查

**Files:**
- Create: `docs/90-review/2026-07-11-multilang-code-problem-backend-agent-audit.md`
- Modify only if evidence identifies a critical or high-severity issue in the repaired path.

**Interfaces:**
- Produces an evidence-backed quality report covering cohesion, coupling, file/function size, duplicated responsibilities, test coverage, and AgentScope runtime ownership.

- [ ] **Step 1: Gather actual runtime and structural evidence**

Run AgentScope 2.0.3 introspection, search for `Agent(`, `reply_stream`, `Toolkit`, `ToolGroup`, `FunctionTool`, middleware, workspaces and custom tool loops. Measure modified Backend and Agent files with `wc -l`; inspect routers, services, tool builders, session entrypoint and tests.

- [ ] **Step 2: Classify quality findings**

Apply severity to concrete file/line evidence. Do not flag `reply_stream`, trusted JSON parsing, workspace artifact I/O or EDU-specific RAG merely because they are custom. Flag only genuine boundary, ownership, cohesion, file-size or framework misuse.

- [ ] **Step 3: Repair critical/high findings only**

For each critical/high issue, first add a focused failing test, then make the smallest cohesive change. Do not bundle unrelated refactors or introduce dependencies.

- [ ] **Step 4: Run audit verification and write report**

Run targeted tests for every repaired finding. Report the AgentScope verdict as Framework-native, Partially framework-native or Pseudo-framework, with positive evidence and missing evidence. Include a concise completion checklist for the user objective.

- [ ] **Step 5: Commit audit report and fixes**

```bash
git add docs/90-review backend agent_service_v2
git commit -m "docs: 审查代码题后端与智能体质量"
```
