# Submodule AGENTS v3 Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align `frontend/AGENTS.md`, `backend/AGENTS.md`, and `agent_service/AGENTS.md` with root `Agents.md` v3 while preserving module-specific guidance.

**Architecture:** Root `Agents.md` remains the global process authority. Submodule `AGENTS.md` files become local supplements that keep module boundaries, commands, tests, and special constraints, while current progress records move to root `WorkLine.md`; old `WORKFLOW.md` files are documented as historical read-only records.

**Tech Stack:** Markdown documentation, git, ripgrep validation.

---

## File Structure

- Modify `frontend/AGENTS.md`: Keep frontend-specific UI, SWR/MVVM, data authenticity, and frontend verification rules; remove or rewrite stale global process rules.
- Modify `backend/AGENTS.md`: Keep backend contract, service boundary, FastAPI layering, Agent client, and pytest/py_compile rules; remove or rewrite stale global process rules.
- Modify `agent_service/AGENTS.md`: Keep Agent Service boundary, AgentScope verification, agents/tools/prompts layering, multi-agent guidance, and uv commands; remove or rewrite stale global process rules.
- Modify `WorkLine.md`: Append one record for the documentation alignment task after implementation and verification.

---

### Task 1: Establish Shared v3 Wording in Each Submodule

**Files:**
- Modify: `frontend/AGENTS.md`
- Modify: `backend/AGENTS.md`
- Modify: `agent_service/AGENTS.md`

- [ ] **Step 1: Add the same local-supplement scope note near the top of each file**

Use this exact wording in each submodule file after the existing scope heading and before module-specific scope bullets:

```markdown
> 根目录 `Agents.md` 是全局协作约束；本文件只补充当前子模块的局部规则。
> 若流程规则冲突，以根目录 `Agents.md` 为准；若模块边界细节冲突，以本文件为准。
```

- [ ] **Step 2: Replace current-record references with v3 record wording**

In all three files, replace statements that make `WORKFLOW.md` the active progress source with this meaning:

```markdown
根目录 `WorkLine.md` 是当前唯一工作存档。旧版 `WORKFLOW.md` 仅用于追溯历史上下文，不再追加新记录，也不作为当前状态源。
```

Keep any module-specific context recovery notes, but make them read from `WorkLine.md` first and `WORKFLOW.md` only as historical backup.

- [ ] **Step 3: Remove submodule branch hardcoding**

In `frontend/AGENTS.md`, replace:

```markdown
- 当前分支：`refactor/v2-architecture`，不切换分支
```

with:

```markdown
- 当前分支规则以根目录 `Agents.md` 为准。
```

If backend or agent_service contain branch-specific defaults, replace them with the same root-reference wording.

- [ ] **Step 4: Validate shared wording**

Run:

```bash
rg -n "WorkLine|WORKFLOW|refactor/v2|refactor/v3|根目录 `Agents.md`" frontend/AGENTS.md backend/AGENTS.md agent_service/AGENTS.md
```

Expected:
- Each file mentions `WorkLine.md`.
- Any `WORKFLOW.md` mention describes historical read-only lookup only.
- No `refactor/v2-architecture` remains.
- No submodule hardcodes `refactor/v3-architecture`; branch rule is delegated to root `Agents.md`.

- [ ] **Step 5: Commit Task 1**

```bash
git add frontend/AGENTS.md backend/AGENTS.md agent_service/AGENTS.md
git commit -m "docs: 对齐子模块 v3 全局规则引用"
```

---

### Task 2: Preserve and Trim Frontend-Specific Guidance

**Files:**
- Modify: `frontend/AGENTS.md`

- [ ] **Step 1: Keep frontend-specific sections**

Ensure `frontend/AGENTS.md` still contains these concepts after edits:

```text
以 UI 行为为真相
优先复用，避免重造
React / SWR / MVVM
数据真实性
npm run lint
npm run build
```

- [ ] **Step 2: Remove duplicated global process sections**

Delete or reduce frontend-local text that duplicates root `Agents.md` for:

```text
任务规模分级
Git 当前分支
完成一个功能点后固定写 WORKFLOW.md
完成后汇报格式
禁止 git push / reset / clean 的全局规则
```

If a deleted section contains a frontend-only warning, keep that warning in the nearest relevant frontend section.

- [ ] **Step 3: Rewrite frontend progress and interface drift wording**

Use this exact meaning for frontend progress and drift:

```markdown
完成前端功能或接口调用变更后，在根目录 `WorkLine.md` 追加记录。若需要追溯 v2 阶段历史，可只读查询旧版 `WORKFLOW.md`。
接口漂移记录位置统一为 `WorkLine.md`。
```

- [ ] **Step 4: Validate frontend-specific information is preserved**

Run:

```bash
rg -n "UI 行为|SWR|MVVM|数据真实性|mock|npm run lint|npm run build|WORKFLOW|WorkLine|refactor/v2" frontend/AGENTS.md
```

Expected:
- Frontend-specific terms are present.
- `WORKFLOW.md` appears only as historical read-only context.
- `WorkLine.md` is the current record target.
- `refactor/v2` does not appear.

- [ ] **Step 5: Commit Task 2**

```bash
git add frontend/AGENTS.md
git commit -m "docs: 精简前端局部协作规则"
```

---

### Task 3: Preserve and Trim Backend-Specific Guidance

**Files:**
- Modify: `backend/AGENTS.md`

- [ ] **Step 1: Keep backend-specific sections**

Ensure `backend/AGENTS.md` still contains these concepts after edits:

```text
Backend 只通过 HTTP 调用 Agent Service
app/services/agent_client.py
Backend 不直接访问 Qdrant
Agent Service 不直接写 Backend SQL
Contract Discipline
Router
Service
pytest
py_compile
```

- [ ] **Step 2: Remove duplicated global process sections**

Delete or reduce backend-local text that duplicates root `Agents.md` for:

```text
每次修改前必须输出四项通用说明
每次完成后 commit 的全局规则
WORKFLOW.md 作为当前主状态文件
跨窗口恢复以 WORKFLOW.md 为主要上下文
```

Keep backend-specific contract approval requirements when they are stricter than root rules.

- [ ] **Step 3: Rewrite backend progress and contract drift wording**

Use this exact meaning for backend records:

```markdown
Backend 开发完成后，在根目录 `WorkLine.md` 记录接口状态、测试命令和结果、契约是否漂移。旧版 `WORKFLOW.md` 仅用于追溯历史联调记录。
```

Keep the existing backend rule that contract changes must be identified before implementation.

- [ ] **Step 4: Validate backend-specific information is preserved**

Run:

```bash
rg -n "agent_client|Qdrant|Agent Service 不直接写|Contract Discipline|Router|Service|pytest|py_compile|WORKFLOW|WorkLine|refactor/v2" backend/AGENTS.md
```

Expected:
- Backend boundary and contract terms are present.
- `WORKFLOW.md` appears only as historical read-only context.
- `WorkLine.md` is the current record target.
- `refactor/v2` does not appear.

- [ ] **Step 5: Commit Task 3**

```bash
git add backend/AGENTS.md
git commit -m "docs: 精简后端局部协作规则"
```

---

### Task 4: Preserve and Trim Agent Service-Specific Guidance

**Files:**
- Modify: `agent_service/AGENTS.md`

- [ ] **Step 1: Keep Agent Service-specific sections**

Ensure `agent_service/AGENTS.md` still contains these concepts after edits:

```text
Agent Service 不直接写 Backend 数据库
AgentScope
agents
tools
prompts
memory
api
多智能体
uv sync --group dev
./.venv/bin/pytest
```

- [ ] **Step 2: Merge duplicate AgentScope Boundary headings**

If two `## AgentScope Boundary` headings remain, merge them into one section. Preserve both kinds of content:

```text
优先参考 AgentScope 官方文档和项目当前已有代码
官方文档索引优先使用 https://docs.agentscope.io/llms.txt
无法确认行为时，查文档、用本地安装包 introspection 验证，或实现规则版/适配层并在 WorkLine.md 标注后续替换点
```

- [ ] **Step 3: Remove duplicated global process sections**

Delete or reduce agent_service-local text that duplicates root `Agents.md` for:

```text
每次文件修改后需要 commit 的全局规则
完成开发任务后的最终回复格式
WORKFLOW.md 作为当前主状态文件
跨窗口恢复以 WORKFLOW.md 为主要上下文
```

Keep agent_service-specific context commands, but point active status reads at root `WorkLine.md`.

- [ ] **Step 4: Rewrite Agent Service progress wording**

Use this exact meaning:

```markdown
Agent Service 开发完成后，在根目录 `WorkLine.md` 记录实现状态、测试命令和结果、契约是否漂移。旧版 `agent_service/WORKFLOW.md` 或根目录 `WORKFLOW.md` 仅用于追溯历史，不再追加新记录。
```

- [ ] **Step 5: Validate Agent Service-specific information is preserved**

Run:

```bash
rg -n "AgentScope|agents|tools|prompts|memory|多智能体|uv sync|\\.venv/bin/pytest|WORKFLOW|WorkLine|refactor/v2" agent_service/AGENTS.md
```

Expected:
- Agent Service boundary and AgentScope guidance are present.
- Only one `## AgentScope Boundary` heading remains.
- `WORKFLOW.md` appears only as historical read-only context.
- `WorkLine.md` is the current record target.
- `refactor/v2` does not appear.

- [ ] **Step 6: Commit Task 4**

```bash
git add agent_service/AGENTS.md
git commit -m "docs: 精简 Agent Service 局部协作规则"
```

---

### Task 5: Final Cross-Document Validation and WorkLine Record

**Files:**
- Modify: `WorkLine.md`

- [ ] **Step 1: Run cross-document validation**

Run:

```bash
rg -n "WORKFLOW|WorkLine|refactor/v2|refactor/v3" frontend/AGENTS.md backend/AGENTS.md agent_service/AGENTS.md Agents.md
```

Expected:
- Root `Agents.md` says `WorkLine.md` is current and no longer uses `WORKFLOW.md` for new records.
- Submodule `WORKFLOW.md` mentions are historical read-only only.
- No `refactor/v2` remains in submodule docs.
- Submodule docs do not hardcode `refactor/v3`; they reference root branch rules.

- [ ] **Step 2: Confirm module-specific terms are still present**

Run:

```bash
rg -n "UI 行为|SWR|agent_client|Qdrant|AgentScope|uv sync|npm run build|pytest" frontend/AGENTS.md backend/AGENTS.md agent_service/AGENTS.md
```

Expected:
- Frontend, Backend, and Agent Service specific terms are all present.

- [ ] **Step 3: Append WorkLine record**

Append this entry to the end of `WorkLine.md`:

```markdown

### 2026-06-25 — 对齐子模块 AGENTS.md 到 v3 协作规则

**涉及文件：**
- `frontend/AGENTS.md`
- `backend/AGENTS.md`
- `agent_service/AGENTS.md`
- `WorkLine.md`

**核心改动：**
三个子模块文档调整为根目录 `Agents.md` 的局部补充：保留模块独有边界、测试命令和架构注意事项，删除或改写重复的全局流程规则。统一记录规则：根目录 `WorkLine.md` 是当前唯一工作存档，旧版 `WORKFLOW.md` 仅用于历史追溯，不再追加新记录。

**验证结果：**
- 前端 lint / build：未运行（仅文档变更）
- 后端 py_compile / pytest：未运行（仅文档变更）
- Agent pytest：未运行（仅文档变更）
- 文档检查：通过 `rg` 关键词检查

**接口漂移：** 无
```

- [ ] **Step 4: Review final diff**

Run:

```bash
git diff -- frontend/AGENTS.md backend/AGENTS.md agent_service/AGENTS.md WorkLine.md
```

Expected:
- Only documentation changes are present.
- No business code files are modified.
- The diff preserves module-specific guidance listed in Tasks 2-4.

- [ ] **Step 5: Commit Task 5**

```bash
git add frontend/AGENTS.md backend/AGENTS.md agent_service/AGENTS.md WorkLine.md
git commit -m "docs: 完成子模块 AGENTS v3 对齐"
```

---

## Self-Review

- Spec coverage: The plan covers all target files, current `WorkLine.md` rule, historical-only `WORKFLOW.md`, preservation of module-specific guidance, validation commands, and final WorkLine record.
- Placeholder scan: No placeholders or deferred implementation steps remain.
- Scope check: The plan is documentation-only and does not modify business code, API contracts, tests, dependencies, or historical `WORKFLOW.md` contents.
