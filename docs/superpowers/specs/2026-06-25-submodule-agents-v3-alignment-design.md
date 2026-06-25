# 设计文档：子模块 AGENTS.md v3 对齐

**日期：** 2026-06-25  
**状态：** 待执行  
**目标文件：**
- `frontend/AGENTS.md`
- `backend/AGENTS.md`
- `agent_service/AGENTS.md`
- `WorkLine.md`

---

## 背景

根目录 `Agents.md` 已升级为 v3 全局协作约束，并明确 `WorkLine.md` 是当前唯一工作存档。三个子模块 `AGENTS.md` 仍保留 v2 阶段表达，包括 `WORKFLOW.md` 作为主状态源、`refactor/v2-architecture` 分支引用，以及部分与根目录重复的全局流程规则。

这些内容会造成两个问题：

1. 新任务开始时，根目录与子模块文档对“记录写哪里、当前分支是什么、完成后怎么汇报”的说法不一致。
2. 子模块文档包含大量有价值的模块经验，如果直接极简化，会丢失 Backend/Frontend/Agent Service 的局部边界和测试规则。

本次设计目标是采用“局部补充型”子模块文档：根目录负责全局流程，子模块只保留本模块独有规则。

---

## 目标

1. 三个子模块 `AGENTS.md` 与根目录 v3 规则一致。
2. 保留子模块独有信息，不做大规模重写和信息删除。
3. 统一当前工作记录规则：
   - `WorkLine.md` 是当前唯一工作存档。
   - `WORKFLOW.md` 是旧版历史记录，只用于追溯上下文，不再追加新记录，不作为当前状态源。
4. 删除或改写与根目录重复、冲突、需要多处维护的全局流程规则。

---

## 非目标

- 不修改业务代码。
- 不修改 API 契约、运行逻辑或测试代码。
- 不清理历史 `WORKFLOW.md` 内容。
- 不删除子模块中仍有实际约束价值的边界、测试命令和架构说明。

---

## 方案选择

采用方案 1：**v3 对齐 + 保留局部规则**。

### 选用原因

- 根目录 `Agents.md` 已经覆盖任务分级、修改前确认、Git、完成汇报、WorkLine 等全局规则。
- 子模块文档仍包含不可替代的局部知识，例如 Backend 与 Agent Service 边界、AgentScope 查证规则、Frontend UI 真实性原则。
- 相比只做字符串替换，本方案能减少后续维护冲突。
- 相比极简化，本方案不会丢失模块上下文。

---

## 文档分工

### 根目录 `Agents.md`

继续作为全局规则来源，负责：

- 当前阶段与工作方式
- 任务规模分级
- 修改前确认
- Git 与 commit 规则
- 完成汇报格式
- 通用架构与代码生成规范
- 当前工作存档位置：`WorkLine.md`

### 子模块 `AGENTS.md`

调整为局部补充文档，负责：

- 模块职责边界
- 模块内部目录职责
- 模块特有架构约束
- 模块特有测试命令
- 模块特有禁止事项
- 与根目录规则不冲突的上下文说明

每个子模块文档开头应明确：

> 根目录 `Agents.md` 是全局协作约束；本文件只补充当前子模块的局部规则。若流程规则冲突，以根目录 `Agents.md` 为准；若模块边界细节冲突，以本文件为准。

---

## 记录规则

三个子模块文档中涉及进度、状态、上下文恢复的描述统一改为：

- 当前开发记录、测试结果、接口漂移和下一步建议写入根目录 `WorkLine.md`。
- 旧版 `WORKFLOW.md` 仅作为历史记录查阅，不再追加新条目。
- 如果旧 `WORKFLOW.md` 与当前代码或 `WorkLine.md` 冲突，以当前代码和 `WorkLine.md` 为准。

保留“可查旧记录追溯历史”的能力，但避免它继续承担当前状态源职责。

---

## 各子模块处理策略

### Frontend

保留：

- UI 行为为功能完成度真相。
- React / SWR / MVVM 约束。
- 不使用 mock 数据、假数据、硬编码业务字段。
- 前端测试和构建命令。
- 页面、组件、hook 的职责边界。

改写：

- `WORKFLOW.md` 相关内容改为 `WorkLine.md` 当前记录 + `WORKFLOW.md` 历史查询。
- `refactor/v2-architecture` 改为引用根目录当前分支规则。
- 删除与根目录重复的 Git、完成汇报、任务分级规则。

### Backend

保留：

- Backend / Agent Service / SQL / Qdrant 边界。
- API 契约纪律。
- Router / Service / Schema / Model / DB 分层职责。
- 统一通过 `app/services/agent_client.py` 调用 Agent Service。
- pytest、py_compile 和相关测试要求。

改写：

- `WORKFLOW.md` 作为主状态源的描述改为 `WorkLine.md`。
- 子模块 Git 分支与 commit 规则改为引用根目录。
- 保留 Backend 特有的契约漂移处理，但记录位置统一为 `WorkLine.md`。

### Agent Service

保留：

- Agent Service 不直接写 Backend SQL。
- Agent Service 不改变 Backend 调用契约。
- `agents/`、`tools/`、`prompts/`、`memory/`、`api/` 分层职责。
- AgentScope 官方文档与本地 introspection 查证规则。
- 多 Agent 适用边界。
- `uv` 和本地测试命令。

改写：

- `WORKFLOW.md` 相关描述改为 `WorkLine.md` 当前记录 + 旧记录只读查询。
- 去除重复的全局 Git 和完成汇报规则。
- 合并重复出现的 AgentScope Boundary 标题，保留完整内容。

---

## 影响范围

本次只影响协作文档，不影响运行代码。

预期影响：

- 后续任务的记录位置统一。
- 子模块文档更短、更清晰，但仍保留关键局部经验。
- 减少根目录与子模块文档的规则漂移。

---

## 验证方式

文档修改完成后检查：

1. `rg -n "WORKFLOW|WorkLine|refactor/v2|refactor/v3" frontend/AGENTS.md backend/AGENTS.md agent_service/AGENTS.md Agents.md`
2. 确认子模块中不再要求向 `WORKFLOW.md` 追加新记录。
3. 确认子模块中不再硬编码 v2 分支。
4. 确认三个子模块仍保留各自独有边界和测试命令。
5. 在 `WorkLine.md` 追加本次文档对齐记录。

---

## 自检项

- 不修改业务代码。
- 不引入新依赖。
- 不删除历史 `WORKFLOW.md`。
- 不把子模块文档改成只有链接的极简索引。
- 保留模块独有约束，删除或改写重复的全局流程规则。
