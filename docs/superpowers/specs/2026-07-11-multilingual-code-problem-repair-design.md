# AIChat 多语言代码题修复设计

日期：2026-07-11

## 目标

修复 AIChat 私有代码题创建被误报为“后端不可用”的问题，并使私有代码题与
既有 Judge0 执行、CodeSandboxCard 工件和接口文档一致地支持六种教学语言：
`c`、`cpp`、`python`、`java`、`go`、`javascript`。

完成功能修复后，将改动保留在独立的 `codex/multilang-code-problems` 工作树和
分支中，并审查 Backend 与 Agent Service v2 的代码质量和 AgentScope 2.x 框架使用。

## 事实与问题

1. Backend 的 Judge0 映射、CodeSandboxCard 工件校验和现有 API 文档均列出六种
   语言，但 `CodeProblemDraft.language` 只接受 `c`、`cpp`、`python`。
2. Agent 创建题目工具将任何 HTTP 4xx/5xx 压缩为 `backend_http_error`，再返回普通
   工具结果。AgentScope 的工具调用状态因此为 success，前端显示“完成”，模型则把
   校验拒绝误述为“后端不可用”。
3. 已执行 `backend/migrations/2026-07-10-add-personal-code-problems.sql` 修复
   `user_personalized_resources.code_problem_id` 缺列；本设计不再变更数据库结构。
4. 本地 Judge0 `/languages` 已包含六种目标语言。Judge0 的 `language_id` 随部署版本
   变化，不是产品对外契约。

## 备选方案

### A. 只接受模型输出的小写规范值

修改 schema 为六语言 Literal，但不处理 `C++`、`Python3`、`Node.js` 等常见别名。

- 优点：改动最少。
- 缺点：模型自然语言输出仍会产生 422；没有解决当前故障类别。
- 结论：不采用。

### B. 静态教学语言注册表（采用）

Backend 维护六种规范名称、别名和 Judge0 ID 的唯一注册表；schema 和 Judge0 服务
都通过该注册表归一化。Agent 仅将输入交给 Backend，Backend 是最终权威。

- 优点：复用已有六语言能力，部署稳定，错误可解释，避免跨服务 Python import。
- 缺点：新增语言需要显式更新注册表和测试。
- 结论：采用。

### C. 运行时暴露 Judge0 全部语言

每次读取 `/languages` 并把全部语言开放给 Agent 和前端。

- 优点：表面上覆盖更多语言。
- 缺点：部署版本漂移、Java 文件/类名要求、模板和教学质量均不可控；会把 Judge0
  实现细节泄露为产品契约。
- 结论：不采用。

## 设计

### Backend 语言边界

新增 `backend/app/services/code_language.py`，只负责语言事实：

- 规范值：`c`、`cpp`、`python`、`java`、`go`、`javascript`；
- 常见别名归一化，例如 `C++ -> cpp`、`Python 3 -> python`、`Node.js -> javascript`；
- 为本地 Judge0 固定的语言 ID；
- 对未知值抛出一个领域级、无敏感数据的语言不支持错误。

`CodeProblemDraft` 的 Pydantic before validator 调用归一化函数，随后由 Literal
保证持久化值一定是规范值。`execute_code_in_oj()` 和 batch 路径也复用同一个函数，
不再维护另一份裸字典。

### Agent 到 Backend 的失败语义

`BackendLearningClientError` 保留 HTTP status，并使用无敏感的分类：

- `backend_validation_error`：HTTP 422；
- `backend_rejected`：其他 4xx；
- `backend_server_error`：5xx；
- `backend_timeout`、`backend_unavailable`：传输失败。

私有代码题工具把前三类返回为 `status: rejected` 或 `status: degraded`，同时给模型
明确原因。只有 timeout/unavailable 才允许模型声称服务暂不可用。

AgentScope `ToolResultEndEvent` 仍按真实运行时生命周期映射为 `tool_completed`；
这是框架正常语义。产品适配器额外保留业务 status/reason，前端根据其判定卡片为
失败或完成，不伪造 AgentScope 工具异常。

### 前端展示

`tool_completed` 只有 `state != error` 且业务状态不是 `rejected`、`degraded` 或
`unavailable` 时才显示完成。展示使用 adapter 给出的安全摘要，不显示参考解、
隐藏用例或 Backend 原始错误体。

CodeSandbox 文件名展示补齐 `Main.java`、`main.go`、`main.js`；运行和提交请求继续
使用规范语言值，不让浏览器直连 Judge0。

### AgentScope 边界

不新增手写 Agent loop。现有 `Agent`、`Toolkit`、`ToolGroup`、`FunctionTool`、
permission context、`reply_stream()` 和 EDU 协议 adapter 继续承担各自职责：

```text
AgentScope FunctionTool
  -> Backend internal HTTP
  -> structured tool observation
  -> AgentScope ToolResultEndEvent
  -> EDUProtocolAdapter
  -> stable frontend tool status
```

Backend 不导入 Agent Service，Agent Service 不访问 MySQL 或 Judge0。

## 测试与验收

1. Backend 单元测试验证六语言、别名归一化及未知语言拒绝；
2. 私有代码题内部 API 验证 `C++` 和 `Python3` 被规范化后可通过 schema；
3. Agent 工具测试验证 HTTP 422 被分类为 `rejected`，不误称服务不可用；
4. 协议和前端测试验证 rejected/degraded 工具卡显示失败；
5. 运行相关 Backend pytest、Agent pytest、Frontend Vitest、lint 和 build；
6. 在独立分支进行 Backend 与 Agent Service v2 静态/运行路径审查，记录问题、正面
   证据、未证实项及修复结果；AgentScope 审查必须验证真实入口使用 `reply_stream()`。

## 非目标

- 不开放 Judge0 的全部语言；
- 不改变数据库表、公开 API 路径、Agent v1 或前端直连边界；
- 不持久化模型输入中的参考解或隐藏用例到日志、SSE 或 artifact。
