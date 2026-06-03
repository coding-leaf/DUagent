# Agent Service Docs

`agent_service/docs/` 不维护正式接口契约；正式契约请看根目录 `docs/20-agent-api/*`。模块阅读入口优先看上层 `agent_service/README.md`，本文件只说明本目录内各文件定位。

## 稳定文档

- `goals.md`
  - 模块目标、边界、明确不做事项
- `glossary.md`
  - 模块术语表
- `decisions.md`
  - 关键实现决策与原因
- `temporary-implementation.md`
  - 当前临时实现与已知限制
- `Agent-Service_本地启动与运维.md`
  - 启动、readiness、smoke、知识入库和常见问题操作说明

## 补充阅读

- `Agent-Service_代码导读与自学手册.md`
  - 代码阅读辅导材料；适合新人上手，不替代正式导航和状态板
- `Agent-AI编排审计.md`
  - AI 编排专题审计；适合针对某条链路深挖时使用
- `Agent架构演进与多智能体进程.md`
  - 架构演进讨论；用于理解历史取舍，不作为当前实现计划
- `Apifox_Agent_Service_全接口测试指南.md`
  - 接口测试操作手册；联调执行时按需阅读
- `Apifox_resources_generate_调试说明.md`
  - 资源生成调试手册；按需阅读

## 参考与历史材料

- `skills/agentscope-framework/`
  - AgentScope 开发导航与参考资料
- `superpowers/`
  - 历史实施设计/计划材料；保留追溯价值，但默认视为 archive-like 内容
