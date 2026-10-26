# Journal - coding-leaf (Part 1)

> AI development session journal
> Started: 2026-10-18

---



## Session 1: 拔除后端大模型越位调用，重构通用课程规划智能体与大纲解析工具
<!-- trellis-session: v=2 fp=5e6f6b2845badb80 -->

**Date**: 2026-10-18
**Task**: 拔除后端大模型越位调用，重构通用课程规划智能体与大纲解析工具
**Package**: backend
**Branch**: `main`

### Summary

物理删除 backend/app/services/kg_generation.py 中违规直接调用大模型的 generate_kg_from_llm，大纲图谱生成统一向 Agent Service 委托；在 agent_service_v2 中彻底拔除死写 C 语言的硬编码，重构为通用的 CourseCurriculumPlanner 并执行 DAG 拓扑环路校验；基于 AgentScope 原生 FunctionTool 实现确定性的文档大纲解析工具 outline_extractor.py；全量单测通过，无回归缺陷。

### Git Commits

| Hash | Message |
|------|---------|
| `ad21c19` | refactor(agent,backend): 拔除后端大模型越位调用，重构通用课程知识大纲规划器与原生解析工具 |

### Status

[OK] **Completed**


## Session 2: 统一前后端代码扫描体系并沉淀架构红线逃生通道
<!-- trellis-session: v=2 fp=23d37248190a35bd -->

**Date**: 2026-10-18
**Task**: 统一前后端代码扫描体系并沉淀架构红线逃生通道
**Package**: backend
**Branch**: `main`

### Summary

引入现代 Rust 工具 Ruff 统一后端与智能体端静态扫描，配置 ruff.toml 忽略 SQLAlchemy E712；修复 auth.py 与 evaluation.py 未定义变量及 Windows 文件句柄锁隐患；交付全仓 check_all.py 串联 6 大门禁全部绿灯通过；在 .trellis/spec/ 下固化负向红线与显式逃生通道 # arch-allow: 规范。

### Git Commits

| Hash | Message |
|------|---------|
| `53787ed` | chore(tooling,spec): 统一前后端代码扫描流水线与沉淀架构红线逃生通道 |

### Status

[OK] **Completed**


## Session 3: 收口剩余P0安全越权、RAG错位与前端交互缺陷并完成前四阶段审计
<!-- trellis-session: v=2 fp=7365afa7ad0f8c5b -->

**Date**: 2026-10-26
**Task**: 收口剩余P0安全越权、RAG错位与前端交互缺陷并完成前四阶段审计
**Package**: backend
**Branch**: `main`

### Summary

完成前四阶段任务只读合规审查（11项全PASS）；修复quiz/learning-path课程越权IDOR、题库批量生成partial状态防误删、个性化资源生成RAG catalog_id与班课course_id错位、教师端退出登录失效与局域网HTTP环境uid()安全回退；沉淀三端架构红线与7节可执行契约；全仓6大门禁与前端155项单测100%绿灯。

### Git Commits

| Hash | Message |
|------|---------|
| `5d71a9d` | fix(backend,agent,frontend,spec): 修复课程越权IDOR、部分失败题库误删、RAG catalog_id错位与前端退出/UUID缺陷并沉淀规范 |

### Status

[OK] **Completed**


## Session 4: 交接前全仓死代码清理、跨层安全收尾、OpenAPI契约刷新与README重构
<!-- trellis-session: v=2 fp=8b491242f8cbb801 -->

**Date**: 2026-10-26
**Task**: 交接前全仓死代码清理、跨层安全收尾、OpenAPI契约刷新与README重构
**Package**: backend
**Branch**: `main`

### Summary

清理过时审计报告、测试残留库与前端0引用死组件/脚本/重复catalogService（净减3700+行历史包袱）；补齐Icon.jsx 23个缺失映射并合并错误解析函数；消除下载URL的Query Token泄露、Webhook生产防空密钥与SSRF校验、BackendLearningClient异常收敛；自动同步双端OpenAPI JSON并重构README交接与部署指南。

### Git Commits

| Hash | Message |
|------|---------|
| `95eb44f` | chore(handover,security,docs): 清理过时报告与前端死代码、收尾跨层安全隐患并重构README与OpenAPI文档 |

### Status

[OK] **Completed**
