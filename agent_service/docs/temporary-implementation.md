# Agent Service Temporary Implementation

## 当前已实现

- tutoring/chat 已具备 StrategyAgent、ReAct、critic、规则 fallback 主链。
- assessment/generate-questions 已具备 RAG toolkit、质量门禁与 fallback。
- resources/generate 已具备 planner、fanout、critic、aggregator、多阶段 fallback。
- profile/evaluation/assessment-evaluate/learning-path/memory-compress 保持 structured output + 规则保护主链。

## 临时方案

### `docs/superpowers/*` 仍保留但只作历史实施材料

- 当前行为
  - 这些文档继续存在，方便追溯当时实施思路。
- 为什么是临时状态
  - 它们不再是当前实现真相源，但还没有统一迁入正式 archive 目录。

### Qdrant local mode 仍被默认支持

- 当前行为
  - 未配置 `QDRANT_URL` 时回落到 `QDRANT_PATH=./qdrant_data`。
- 为什么是临时方案
  - local mode 会带来单目录文件锁问题，不适合作为长期联调主形态。

### health/readiness/smoke 与真实业务验收仍是两层体系

- 当前行为
  - smoke 解决“最小链路能跑”，不等于质量验收。
- 为什么是临时说明
  - 当前还需要人读 `WORKFLOW.md` 和联调文档理解哪些结果才算真正通过。

## 已知限制

- 部分模块级说明仍残留在 `WORKFLOW.md` 历史记录里，尚未完全去历史化。
- `docs/30-dev-guide/Agent-Service_开发导读.md` 仍承担一部分开发导览作用，但不应再被当作当前实现真相。

## 替换条件

- 完成历史实施材料归档后，可把 `docs/superpowers/*` 从常规文档视图中进一步弱化。
- 当联调完全以 `QDRANT_URL` 为主时，可把 local mode 降为兼容路径而不是默认心智模型。
