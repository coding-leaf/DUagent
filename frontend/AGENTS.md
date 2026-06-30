# AGENTS.md

## Scope

> **【作用域声明】**
> 本约束文档为前端局部规范；凡涉及 `frontend/` 的前端范围工作，无论当前工作目录在哪里，都必须遵守本文档的前端局部规则。根目录 `AGENTS.md` 仍是全局协作约束和流程权威。

> 根目录 `AGENTS.md` 是全局协作约束；本文件只补充当前子模块的局部规则。
> 若流程规则冲突，以根目录 `AGENTS.md` 为准；若模块边界细节冲突，以本文件为准。

This file applies only to frontend-specific work scoped from `frontend/` and supplements the root `AGENTS.md`.

---

## 项目现状（2026-06）

这是一个 AI 教育助手全栈项目，技术栈：React 前端 + FastAPI 后端 + Python Agent Service + MySQL。

**真实运行状态：**

- 前端页面：Login / Register / Dashboard / LearningPath / Quiz / StudentProfile / AIChat / ResourceDetail / TeacherConsole / AdminConsole
- 后端 API 模块：auth / courses / learning-path / quiz / profile / evaluation / learning-activities / resources / profile / teaching / tutoring / catalogs（admin）
- Agent Service：tutoring / evaluation / learning_path / profile / assessment / resources
- 数据库活跃表：learning_activities（259）/ quiz_questions（117）/ resources（88）/ quiz_sessions（31）/ evaluations（23）

**项目开发阶段：**

当前正式进入**架构治理与重构阶段**。
前期的“功能打通阶段”已达成目标，现在的核心任务是：清理过度堆砌的代码，理清微服务/Agent/后端的边界，使用现代化且合理的系统架构、模块化文件划分，并清理到处乱飞的环境变量与虚拟环境。最终目的是**让开发人员能读懂代码，让文件架构清晰明了**。

---

## 权威来源（按优先级）

判断"该怎么做"时，按以下顺序查证：

1. **当前运行代码**：前端 `src/`、后端 `backend/app/`、Agent `agent_service/`。代码是最终事实。
2. **`docs/superpowers/specs/`**：本 session 产出的设计文档，近期决策在这里。
3. **`WorkLine.md`**：根目录 `WorkLine.md` 是当前唯一工作存档。旧版 `WORKFLOW.md` 仅用于只读追溯历史上下文，不再追加新记录，也不作为当前状态源。
4. **`docs/feature-ledger.md`**：功能级看板，但已与实际实现存在较大偏差，**只作参考，不作约束**。用它了解历史意图，不用它判断现状。
5. **`../docs/10-client-api/` OpenAPI 和前端接口规范**：历史契约，**已过时**，仅在核对某个字段来源时参考，不作为实现约束。
6. **`docs/requirements-coverage.md`**：接口实现功能记录，可参考。

**不要用文档推翻实际运行代码的行为。如果文档和代码冲突，以代码为准，顺带在根目录 `WorkLine.md` 记一笔。**

> 注意：权威来源第1条（当前运行代码）判断的是实现逻辑和格式，而"以 UI 行为为真相"判断的是功能完成度。二者适用场景不同，不冲突。

---

## 开发原则

### 以 UI 行为为真相

前端页面能显示什么、用户能操作什么，这就是"功能是否完成"的判断标准。

- 后端有接口但前端没有入口 → 不算完成
- Agent 能力存在但数据没有流到页面 → 不算完成
- 字段在 OpenAPI 里定义了但前端显示是空或错的 → 没意义

### 优先复用，避免重造 (Reuse-First Principle)

在实现任何非业务专属逻辑前，**必须先评估是否已有成熟方案**：

- **状态管理与数据获取**：轮询、缓存、乐观更新、请求去重——优先考虑 SWR / React Query，而非手写 `useEffect`
- **工具函数**：日期、深拷贝、防抖节流——优先用 `dayjs` / `lodash-es`，而非手写
- **UI 交互模式**：拖拽、虚拟滚动、复杂表单——先查 Headless UI / Radix 是否覆盖

**评估标准**：引入一个库的收益（正确性、可维护性）是否超过其成本（bundle 体积、学习曲线、依赖风险）。

> 反例：手写 `setInterval` 轮询时忘记 cleanup 导致内存泄漏；手写深拷贝遗漏 `Date`/`Map` 类型。
> 正例：用 React Query 的 `refetchInterval: (data) => data?.done ? false : 2000` 替代 30 行脆弱的 `pollTask`。

### React / SWR / MVVM

前端状态和接口调用按 React 组件、SWR 数据层、MVVM 视图模型拆分职责：页面组件只表达交互和渲染，接口缓存与重试交给 SWR，可复用的页面状态与字段映射沉到 hook 或 view model。

### 计划驱动的重构原则 (Plan-Driven Refactoring)

**已废除绝对的“最小修改原则”**。由于进入重构阶段，Agent 在发现代码坏味道、反模式或耦合过深时，**必须主动提出重构**。
但在进行跨模块提取、前后端分离或环境清理前，**必须先在 `docs/superpowers/specs/` 中输出架构设计和重构计划 (Plan/Spec)**。
经由沟通确认后，采用 TDD（测试驱动开发）方式，分阶段、步进式地进行重构，绝不能盲目进行全局正则替换或不经测试的瞎改。

### 架构重构指南 (Refactoring Directives)

在进行新的 Spec 规划和代码修改时，AI 应将以下 5 项视为“大体重构方向”，自主发现在项目中违反这些方向的代码文件，针对性地输出单点设计文档后再执行重构：

1. **整理目录**：审视前端、后端、Agent 的目录结构，消除臃肿的大文件（胖路由/胖组件），推行如 `Router -> Service -> DB` 等清晰的分层架构。
2. **提取公共组件**：识别前端中散落的重复 UI 组件、重复的 Context/状态管理、冗余的 Axios API 请求逻辑，将其提取到统一的全局位置。
3. **加测试**：任何核心逻辑的抽取和重构，必须补全或调整对应的单元测试（如后端 Pytest，前端 Playwright/Jest），保证重构后的稳定性。
4. **清环境变量**：审查并清理前端、后端、Agent 中重复定义或过时的 `.env` 变量、配置飞线，以及冗余的虚拟环境与过期的依赖锁文件。
5. **规范后端和 Agent 边界**：当前 Agent Service 不直接连接数据库，边界是清晰的。本方向的任务是**将现有边界契约文档化**（输出 Backend ↔ Agent 通信方式说明），并作为防范性约束：禁止未来在 Agent 侧引入直接数据库操作，所有持久化数据流必须经过后端标准接口。

> **AI 行动指南**：`docs/superpowers/specs/2026-06-17-phase2-architecture-refactoring-master-plan.md` 提供了整体指导方针。AI 应以此方向为指引，**自行找出需要重构的目标文件**，写出具体的单步修复 Spec，**经用户确认后再执行**，而非直接动手。
>
> **架构选型判断（必做）**：在产出任何 Spec 之前，AI 必须主动判断当前痛点是否适合引入特定的系统架构或设计模式——例如：是否需要增加过滤器/中间件链来统一处理横切逻辑、是否应引入仓储层来隔离数据访问、是否适合用策略模式替换硬编码的条件分支、是否需要在分层架构中补齐缺失的 Service 层等。可参考的完整架构与模式清单见 master plan 附录，Spec 中须注明"选用 / 不选用"及原因。

> 
### 数据真实性

- 不允许 mock 数据、假数据、前端硬编码假字段
- 数据库只用 MySQL
- 不允许修改密钥文件、volume 数据
- `.env` 相关的重构需经过 Spec 计划明确后方可操作整理，其余情况不允许修改

### 接口漂移处理

OpenAPI 已过时，不以它为强约束。但改动接口时：

- 要同时改前后端对应的调用点（不能只改一侧）
- 接口漂移记录位置统一为 `WorkLine.md`。
- 接口变更的确认与审批流程以根目录 `AGENTS.md` 为准；前端侧必须记录漂移点。

---

## 测试与检查

前端修改后运行：

```bash
npm run lint
npm run build
```

构建失败必须修复后再 commit。如果测试失败需说明：命令、失败位置、是否修复。

---

## 进度记录

完成前端功能或接口调用变更后，在根目录 `WorkLine.md` 追加记录。若需要追溯 v2 阶段历史，可只读查询旧版 `WORKFLOW.md`。
接口漂移记录位置统一为 `WorkLine.md`。

`docs/feature-ledger.md` 不要频繁更新，它已经偏移，更新它的收益低于维护成本。
`docs/requirements-coverage.md` 需要更新功能/接口实现记录。

---

## 禁止修改

密钥文件 / 凭据文件 / MySQL volume 数据 / 用户上传文件 / 构建产物 / `node_modules` / 缓存目录
