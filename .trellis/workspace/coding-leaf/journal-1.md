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


## Session 5: 稳定性收尾与新人交接前修复（Blob下载修复、Webhook白名单与生产密钥护栏、题库精确清理与7项CI门禁）
<!-- trellis-session: v=2 fp=e11b04e215d96eaa -->

**Date**: 2026-10-27
**Task**: 稳定性收尾与新人交接前修复（Blob下载修复、Webhook白名单与生产密钥护栏、题库精确清理与7项CI门禁）
**Package**: backend
**Branch**: `main`

### Summary

修复两处MarkdownViewer.jsx因apiClient拦截器已解包response.data导致的Blob下载回归并补齐点击下载单测；Backend回调URL统一走受信任内部配置BACKEND_INTERNAL_BASE_URL，Agent Service实施Origin白名单+路径双层校验并拦截生产环境默认弱JWT_SECRET_KEY；将题库批量重生成的旧题软删除收窄至已完成节点的(chapter, knowledge_point)组合并覆盖多教学班共享Catalog；将frontend-tests(Vitest)纳入check_all.py默认7项门禁并建立GitHub Actions CI。

### Git Commits

| Hash | Message |
|------|---------|
| `7e24a94` | fix(frontend,backend,agent,ci): 修复文件下载Blob解包回归、加固Webhook白名单与生产密钥校验、收窄题库清理边界并纳管7项CI门禁 |

### Status

[OK] **Completed**


## Session 6: 教材安全切片与版本化幂等入库改造
<!-- trellis-session: v=2 fp=42efd7d4094548fe -->

**Date**: 2026-10-27
**Task**: 教材安全切片与版本化幂等入库改造
**Package**: agent_service_v2
**Branch**: `fix/robust-catalog-ingestion`

### Summary

修复教材PDF切片Token溢出400错误，实现敏感格式防误伤清洗、Token感知递归安全二次分块，以及Qdrant版本化幂等入库

### Git Commits

| Hash | Message |
|------|---------|
| `cd7d815` | feat(agent): 实施教材语法保护清洗、Token感知递归分块与Qdrant蓝绿版本化幂等入库 |

### Status

[OK] **Completed**


## Session 7: RAG入库数据安全加固与CI门禁修复
<!-- trellis-session: v=2 fp=ceb381158d839af7 -->

**Date**: 2026-10-27
**Task**: RAG入库数据安全加固与CI门禁修复
**Package**: backend
**Branch**: `fix/rag-safety-and-ci-fixes`

### Summary

加固教材级粒度清理隔离与激活两阶段校验事务状态机，排查并阻断未激活临时切片泄露，增加长前缀与组合文本Token预算双重保护及历史Collection回退兼容，补齐CI测试依赖

### Git Commits

| Hash | Message |
|------|---------|
| `5483143` | fix(rag,ci): 加固教材级粒度隔离与激活事务状态机、防检索未激活泄露并补齐CI测试依赖 |

### Status

[OK] **Completed**


## Session 8: DUagent交接前稳定性修复
<!-- trellis-session: v=2 fp=b38b903cbe302e87 -->

**Date**: 2026-10-27
**Task**: DUagent交接前稳定性修复
**Package**: backend
**Branch**: `fix/pre-handover-stability-fixes`

### Summary

贯穿教材业务ID隔离并修复同名教材切片互删缺陷，历史集合回退增加模型身份强校验，加固原生MySQL部署环境参数与密码安全传递，根除Backend异步测试事件循环冲突并为Agent真实Qdrant测试注入确定性离线Embedding

### Git Commits

| Hash | Message |
|------|---------|
| `3bf26bf` | fix(rag,deploy,ci): 实施教材业务ID物理隔离、历史Collection模型身份判定、原生MySQL部署安全加固与测试事件循环解耦 |

### Status

[OK] **Completed**

## Session 9: Agent事件适配器容错重构与数据库窗口函数降维兼容
<!-- trellis-session: v=2 fp=c49e701ebd214f98 -->

**Date**: 2026-10-27
**Task**: Agent事件适配器容错重构与数据库窗口函数降维兼容
**Package**: backend
**Branch**: `fix/agent-event-adapter-and-db-compat`

### Summary

从架构根源重构Agent协议适配器未知事件防御模型（良性事件与扩展事件安全吸收，仅框架致命错误阻断），彻底消除HintBlockEvent引发的流中断；重构会话列表与班级学情数据访问层，消除非必要的MySQL 8.0窗口函数强依赖，实现MySQL 5.7/8.0/SQLite无差别向下兼容与内存映射；加固前端会话边界与部署环境数据库版本探测。

### Git Commits

| Hash | Message |
|------|---------|
| `62ea579` | fix(agent,backend,frontend,deploy): 重构Agent协议适配器未知事件防御模型、消除MySQL 8.0窗口函数强依赖并加固环境检测 |

### Status

[OK] **Completed**

## Session 10: 修复聊天首字流式等待状态与学习面板代码题目渲染异常
<!-- trellis-session: v=2 fp=d2830f3f18ea4c19 -->

**Date**: 2026-10-27
**Task**: 修复聊天首字流式等待状态与学习面板代码题目渲染异常
**Package**: frontend
**Branch**: `fix/chat-loading-state-and-code-problem-ui`

### Summary

修复在聊天框发送消息后startStream内部调用cancelStream误将新占位消息的loading置为false的时序缺陷，确保首字返回前持续展示跳动加载动效并彻底杜绝操作栏提前露底；重构MarkdownViewer代码围栏渲染逻辑，支持无语言标识代码块作为标准块级容器渲染，彻底解决样例输入输出被拆碎为药丸标签的严重UI破损；在代码沙箱用例增加多行换行格式化排版并在工作区Tab中补齐个性化资源卡片元数据。

### Git Commits

| Hash | Message |
|------|---------|
| `d6045f9` | fix(frontend): 修复聊天首字流式等待状态丢失与学习面板代码题目渲染异常 |

### Status

[OK] **Completed**

## Session 11: 基于AgentScope原生编排重构多智能体生成并修复数据库死锁
<!-- trellis-session: v=2 fp=6a71e86095ea4f18 -->

**Date**: 2026-10-27
**Task**: 基于AgentScope原生编排重构多智能体生成并修复数据库死锁
**Package**: agent_service_v2
**Branch**: `fix/agentscope-native-orchestration-and-deadlock-fix`

### Summary

全面废弃手写单线程过程式生成管道，拥抱AgentScope 2.0官方原生的TeamPipeline、TeamMember与Toolkit架构；重构CurriculumLeaderAgent规划主管与LessonWorkerAgent、MindmapWorkerAgent、QuizWorkerAgent、ReadingWorkerAgent领域专家智能体，利用框架底层的asyncio.gather同轮并发调度消除串行排队延迟；在Backend资源发布入库层增加knowledge_point/title等有限长字段防御截断，彻底消除MySQL 1406 Data too long异常；新增POST /internal/personalized-resources/tasks/{task_id}/fail内部失败闭环端点，结合Agent端全局异常拦截网与前端180s超时熔断，彻底杜绝异步任务悬挂与界面无休止转圈假死。

### Git Commits

| Hash | Message |
|------|---------|
| `2752213` | feat(agent,backend,frontend): 基于AgentScope原生TeamPipeline重构多智能体并发生成并消除数据库死锁 |

### Status

[OK] **Completed**



