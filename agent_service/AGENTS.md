# AGENTS.md

## Scope

- 只负责 `agent_service` 内部的智能体服务。
- 不负责主业务后端、前端、SQL 数据库业务系统。
- Agent Service 不直接写 Backend 数据库，只接收 Backend 传入的结构化数据并返回结构化结果。

## Source Of Truth

开发时优先级如下：

1. `../docs/20-agent-api/Agent-Service.openapi.json`
2. `../docs/20-agent-api/API_Agent内部接口规范.md`
3. `../docs/30-dev-guide/Agent-Service_开发导读.md`
4. 当前 `agent_service/` 代码
5. `WORKFLOW.md`

如果文档与历史实现冲突，优先以当前非归档文档为准。

`WORKFLOW.md` 是开发进度和跨窗口恢复上下文的主状态文件，不是接口契约来源。

## Architecture Boundaries

当前分层职责固定为：

- `api`：只处理 FastAPI 路由、参数接收、返回包装、SSE 输出、异步任务协议适配。
- `schemas`：只放 Pydantic 实体，严格对齐 OpenAPI。
- `agents`：放真正的 Agent/Workflow 编排逻辑；规则版实现也先放在这里，方便后续替换为 LLM/AgentScope。
- `memory`：放 Qdrant 读写、检索、事实提取适配。
- `tools`：放图解、代码执行、外部工具封装。
- `prompts`：放系统提示词和模板。
- `core`：放配置和基础设施初始化。

避免把业务逻辑写进 `api` 层。API 层应调用 `agents` 层完成业务处理。

## Code Change Rules

- 修改代码前需要分析并说明问题。
- 修改代码前必须先输出：
  1. 问题分析
  2. 计划修改的文件
  3. 修改方案
  4. 可能影响的功能
- 用户确认后，才允许修改文件。
- 保持命名风格和当前项目结构。
- 只能小范围重构，以 minimal diff 为准则。
- 不要一次性修改过多文件。
- 不要过度工程化；除非能简化代码或减少真实重复，否则不要引入复杂抽象。
- `WORKFLOW.md` 可随已确认的开发任务同步更新，但不能以更新进度为理由扩大业务代码修改范围。
- 新增对外承接函数、Agent 编排函数、协议转换函数时，需要添加简短注释，说明作用、主要输入和输出。
- 简单私有辅助函数不强制添加长注释，优先用清晰命名表达意图。
- 注释应与 `API_Agent内部接口规范.md` 的语义保持一致，不要编造协议字段。
## Incremental Development

- 默认一次只推进一个接口或一个明确子能力。
- 推荐流程：
  1. 写或补测试
  2. 运行测试确认失败
  3. 最小实现
  4. 运行相关测试
  5. 更新 `WORKFLOW.md`
- 除非用户明确要求，不要一次性实现多个接口的业务逻辑。
- 渐进式开发，优先规则版可用实现，再逐步接入 AgentScope、LLM、Qdrant、工具调用。

## Documentation Boundary

- `../docs` 下的文档是开发基础和契约来源。
- 默认不修改 `../docs` 下任何文件。
- 如果代码与 `../docs` 冲突，默认修改代码或测试以贴合文档。
- 只有用户明确要求时，才允许修改 `../docs`。

## AgentScope Boundary

- 涉及 AgentScope API、用法、配置时，优先参考 AgentScope 官方文档和项目当前已有代码。
- 不凭空编造 AgentScope 接口。
- 若无法确认 AgentScope 行为，先实现规则版或接口承接层，并在 `WORKFLOW.md` 标注后续替换点。

## Progress Tracking

每次完成一个小阶段后，必须更新 `WORKFLOW.md`，至少同步：

- 对应接口的实现状态
- 当前上下文
- 下一步建议
- 已运行的测试命令和结果

接口状态以 `WORKFLOW.md` 的项目进度表为准。临时进度、当前任务、下一步队列写入 `WORKFLOW.md`，不要写入 `AGENTS.md`。

## Context Handoff

每次开始 `agent_service` 开发前，先执行非修改型检查：

```bash
pwd
git status --short
sed -n '1,260p' WORKFLOW.md
```

如果当前目录在仓库根目录，则读取：

```bash
sed -n '1,260p' agent_service/WORKFLOW.md
```

跨窗口继续开发时，以 `WORKFLOW.md`、`git status --short`、最近测试结果为主要上下文。

## Git

- 避免在 `master` / `main` / `dev` 等主分支直接开发。
- 默认在 `feat/agent` 或用户当前指定的 agent 功能分支开发。
- 修改前如工作区已有未提交内容，必须先识别哪些是用户改动，不能回滚或覆盖无关改动。
- 如需使用 `git stash`，必须先告知用户。

## Testing

- 修改 Python 代码后，优先运行相关测试。
- 修改 `api/` 或 `schemas/` 后，必须运行 OpenAPI 对齐测试：

```bash
./.venv/bin/pytest tests/test_openapi_alignment.py
```

- 修改接口业务逻辑后，运行对应 agent 测试和契约测试。
- 如无现有测试，至少运行基本导入检查或启动检查。  
- 推荐使用 `pytest`。
- 可选使用 `pytest-cov` 查看测试覆盖率。
- 不为了测试而大规模重构项目。

## Commands

`agent_service` 使用 `uv` 管理，根目录不是 `uv` 项目根。

当前常用命令在 `agent_service/` 目录下执行：

```bash
./.venv/bin/pytest
./.venv/bin/python -m agent_service.main
```

如需使用 `uv`：

```bash
uv sync --group dev
uv run pytest
uv run python -m agent_service.main
```

不要在仓库根目录直接运行 `uv sync`。

## Completion Summary

每次完成开发任务后，最终回复需要包含：

- 当前完成
- 修改文件
- 测试结果
- OpenAPI/契约是否漂移
- 下一步建议
