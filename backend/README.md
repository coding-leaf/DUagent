# Backend Docs Guide

`backend/` 负责主业务后端：用户、鉴权、课程、SQL 持久化、任务状态、前端 API、Agent Service HTTP 调用适配和 Webhook 落库。

## 阅读顺序

1. `README.md`
   - 模块文档入口、阅读顺序、目录导航
2. `docs/goals.md`
   - 本模块要做什么、不做什么、边界是什么
3. `docs/temporary-implementation.md`
   - 当前实现到哪、哪些是临时方案、哪些能力还未收口
4. `WORKFLOW.md`
   - 当前阶段状态、最近验证、下一步
5. `../docs/10-client-api/*` 与 `../docs/20-agent-api/*`
   - 正式接口契约真相源

## 文档地图

- `AGENTS.md`
  - 协作规则、修改约束、契约纪律
- `WORKFLOW.md`
  - 联调状态板，不承担完整架构说明
- `docs/goals.md`
  - 模块职责与明确不做事项
- `docs/glossary.md`
  - Backend 术语表
- `docs/decisions.md`
  - 关键实现决策与原因
- `docs/temporary-implementation.md`
  - 当前临时实现与已知限制

## 代码目录地图

- `app/api/v1`
  - FastAPI 路由、鉴权依赖、协议包装、SSE 代理、异步任务协议适配
- `app/services`
  - 业务编排与 Agent Service HTTP 访问
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
- 历史联调/实施细节优先收口到模块 `docs/`，避免继续堆进 `WORKFLOW.md`。
