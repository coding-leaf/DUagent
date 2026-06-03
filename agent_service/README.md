# Agent Service Docs Guide

`agent_service/` 负责智能体服务：LLM 调用、AgentScope 编排、Qdrant 检索、结构化结果生成、SSE 输出、资源生成工作流。

## 阅读顺序

1. `README.md`
   - 模块文档入口、阅读顺序、目录导航
2. `docs/goals.md`
   - 模块目标、明确不做事项、边界
3. `docs/temporary-implementation.md`
   - 当前能力实现到哪、哪些方案是临时的
4. `WORKFLOW.md`
   - 当前阶段状态、最近验证、下一步
5. `../docs/20-agent-api/*`
   - 正式接口契约真相源

## 文档地图

- `AGENTS.md`
  - 协作规则、边界、修改约束
- `WORKFLOW.md`
  - 状态板，不再承担完整架构说明
- `docs/goals.md`
  - 模块职责与明确不做事项
- `docs/glossary.md`
  - Agent Service 术语表
- `docs/decisions.md`
  - 关键实现决策与原因
- `docs/temporary-implementation.md`
  - 当前临时实现与已知限制
- `docs/Agent-Service_本地启动与运维.md`
  - 本地启动、readiness、smoke、知识入库操作手册
- `docs/superpowers/`
  - 历史实施设计/计划材料，不作为当前真相源

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
