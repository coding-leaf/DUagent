# Agent Service Docs Guide

`agent_service/` 负责智能体服务：LLM 调用、AgentScope 编排、Qdrant 检索、结构化结果生成、SSE 输出、资源生成工作流。

## 先看什么

1. `../docs/20-agent-api/*`
   - 正式接口契约真相源
2. `README.md`
   - 模块文档入口，只负责说明去哪看什么
3. `docs/goals.md`
   - 模块目标、边界、明确不做事项
4. `docs/decisions.md`
   - 稳定实现决策，回答“为什么这样做”
5. `docs/glossary.md`
   - 稳定术语定义，回答“这里的词是什么意思”
6. `docs/temporary-implementation.md`
   - 当前临时方案、已知限制、替换条件
7. `WORKFLOW.md`
   - 当前阶段状态、最近验证、下一步

## 文档分层

- `AGENTS.md`
  - 协作规则、边界、修改约束
- `README.md`
  - 模块导航入口，不承载长篇代码导读和历史背景
- `docs/goals.md`
  - 模块职责与边界
- `docs/decisions.md`
  - 稳定决策
- `docs/glossary.md`
  - 稳定术语
- `docs/temporary-implementation.md`
  - 临时方案与已知限制
- `docs/Agent-Service_本地启动与运维.md`
  - 启动、readiness、smoke、知识入库操作手册
- `WORKFLOW.md`
  - 状态板，不承担完整架构说明

## 关于 `decisions` / `glossary` 的划分

这两个拆分是合理的，但只适合放“稳定知识”：

- `decisions.md` 记录跨阶段仍成立的设计取舍
- `glossary.md` 记录高频且容易歧义的术语
- 阶段性实现状态不要写进这两个文件
- OpenAPI 字段和协议定义不要复制进这两个文件

如果内容主要回答“现在做到哪了”或“这只是暂时方案”，它应进入 `WORKFLOW.md` 或 `docs/temporary-implementation.md`。

## 补充文档的定位

以下文档保留，但默认不作为第一阅读入口：

- `docs/supplemental/Agent-Service_代码导读与自学手册.md`
  - 面向新同学的补充阅读材料，不是当前实现真相源
- `docs/supplemental/Agent-AI编排审计.md`
  - 专题审计材料，不替代 goals / decisions / workflow
- `docs/supplemental/Apifox_*`
  - 操作与调试手册，只在联调执行时按需查看
- `docs/supplemental/Agent架构演进与多智能体进程.md`
  - 架构演进讨论材料，不是当前实现计划
- `docs/superpowers/`
  - 历史实施设计/计划材料，视为 archive-like 内容

## 代码目录地图

- `api`
  - FastAPI 路由、协议包装、SSE/异步响应适配
- `schemas`
  - Pydantic 请求响应实体
- `agents`
  - Agent/Workflow 编排逻辑
- `memory`
  - Qdrant 读写、检索、记忆适配
- `tools`
  - smoke/readiness/ingestion 与外部工具封装
- `core`
  - 配置、provider、基础设施
- `prompts`
  - Prompt 模板

## 当前文档规则

- 正式接口契约只看根目录 `docs/20-agent-api/*`。
- `docs/superpowers/*` 属于历史实施材料，不再作为当前实现真相源。
- `WORKFLOW.md` 只记录状态，不承担 glossary、决策和临时实现说明。
