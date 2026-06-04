# Backend Docs Guide

`backend/` 负责主业务后端：用户、鉴权、课程、SQL 持久化、任务状态、前端 API、Agent Service HTTP 调用适配和 Webhook 落库。

## 先看什么

1. `../docs/10-client-api/*` 与 `../docs/20-agent-api/*`
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
  - 协作规则、修改约束、契约纪律
- `README.md`
  - 文档导航入口，不重复承载大段现状说明
- `docs/goals.md`
  - 模块职责与边界
- `docs/decisions.md`
  - 稳定决策
- `docs/glossary.md`
  - 稳定术语
- `docs/temporary-implementation.md`
  - 临时方案与已知限制
- `WORKFLOW.md`
  - 状态板，不承担完整架构说明、术语表或决策说明

## 关于 `decisions` / `glossary` 的划分

这两个拆分是合理的，前提是职责保持单一：

- `decisions.md` 只记录跨多人协作仍需要反复解释的稳定决策
- `glossary.md` 只记录项目内高频且容易歧义的术语
- 它们都不应重复 `WORKFLOW.md` 的阶段状态
- 它们都不应复制 OpenAPI 字段定义

如果某条内容会随着联调阶段频繁变化，它应该写进 `WORKFLOW.md` 或 `temporary-implementation.md`，而不是 `decisions.md` / `glossary.md`。

## 代码目录地图

- `app/api/v1`
  - FastAPI 路由、鉴权依赖、协议包装、SSE 代理、异步任务协议适配
- `app/services`
  - Agent Service HTTP 访问与逐步收口的业务编排
- `app/models`
  - SQLAlchemy ORM
- `app/schemas`
  - 前端请求响应与 Webhook 实体
- `app/core`
  - 配置、安全、JWT
- `app/db`
  - 数据库连接与初始化

## 当前文档规则

- OpenAPI 与接口规范保留在根目录 `docs/`，不在模块目录复制一份。
- `WORKFLOW.md` 只记录状态，不再承担 glossary、决策和临时方案说明。
- 根目录的联调手册、结果记录等文件只作补充材料；当前开发判断仍以 `docs/` 非归档契约文档和本模块文档为准。
