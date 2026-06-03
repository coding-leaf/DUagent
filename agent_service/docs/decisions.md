# Agent Service Decisions

## 决策 1：Qdrant 检索由 Agent Service 自行完成

- 背景
  - tutoring、resources、assessment 等链路都依赖语义检索。
- 决策
  - Backend 只传结构化当前态，Qdrant 检索和注入上下文由 Agent Service 自行负责。
- 原因
  - 保持 SQL 真值与语义检索职责分离，减少跨服务耦合。

## 决策 2：deterministic 接口优先 structured output + 规则保护

- 背景
  - profile、evaluation、assessment/evaluate、learning-path 等接口需要稳定结构与较强可控性。
- 决策
  - 这些接口不强推多 Agent 化，优先使用 schema 约束和规则保护。
- 原因
  - 相比多 Agent，稳定性和契约一致性更重要。

## 决策 3：resources 保持异步工作流 + webhook

- 背景
  - 资源生成天然耗时长，且适合拆解规划、并发生成、critic、聚合。
- 决策
  - Agent Service 走异步资源工作流并通过 webhook 回调 Backend。
- 原因
  - 更适合长耗时和多阶段处理。

## 决策 4：本地优先允许 Qdrant local mode，但推荐逐步转向 server mode

- 背景
  - 当前配置支持 `QDRANT_PATH` 和 `QDRANT_URL` 两种模式。
- 决策
  - 保留 local mode 作为开发便利，但文档明确其文件锁限制。
- 原因
  - 便于单机开发，同时逐步为真实联调与多进程场景迁移到 server mode。
