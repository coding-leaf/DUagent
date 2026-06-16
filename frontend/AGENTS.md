# AGENTS.md

## Scope

This file applies to `frontend/`. Subdirectory AGENTS.md takes precedence if present.

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
3. **`WORKFLOW.md`**：按日期的施工记录，回溯某次改了什么、跑了什么。
4. **`docs/feature-ledger.md`**：功能级看板，但已与实际实现存在较大偏差，**只作参考，不作约束**。用它了解历史意图，不用它判断现状。
5. **`../docs/10-client-api/` OpenAPI 和前端接口规范**：历史契约，**已过时**，仅在核对某个字段来源时参考，不作为实现约束。
6. `/home/yezisama/workspace/workflow/EDUagent/frontend/docs/requirements-coverage.md`为接口实现功能记录,可参考
**不要用文档推翻实际运行代码的行为。如果文档和代码冲突，以代码为准，顺带在 WORKFLOW.md 记一笔。**

---

## 开发原则

### 以 UI 行为为真相

前端页面能显示什么、用户能操作什么，这就是"功能是否完成"的判断标准。

- 后端有接口但前端没有入口 → 不算完成
- Agent 能力存在但数据没有流到页面 → 不算完成
- 字段在 OpenAPI 里定义了但前端显示是空或错的 → 没意义

### 计划驱动的重构原则 (Plan-Driven Refactoring)

**已废除绝对的“最小修改原则”**。由于进入重构阶段，Agent 在发现代码坏味道、反模式或耦合过深时，**必须主动提出重构**。
但在进行跨模块提取、前后端分离或环境清理前，**必须先在 `docs/superpowers/specs/` 中输出架构设计和重构计划 (Plan/Spec)**。
经由沟通确认后，采用 TDD（测试驱动开发）方式，分阶段、步进式地进行重构，绝不能盲目进行全局正则替换或不经测试的瞎改。

### 架构重构指南 (Refactoring Directives)

在进行新的 Spec 规划和代码修改时，必须主动对照以下核心痛点并予以解决：
1. **理清后端与 Agent 边界**：明确核心业务 CRUD（后端）与大模型计算/逻辑编排（Agent）的职能界限，拒绝面条代码。
2. **按业务模块重组目录**：前端需提取复用 Context/Hooks/Components，后端和 Agent 需采用合理的模块分层（Router/Service/Repository 等），拒绝大杂烩文件。
3. **全局环境变量管理**：清理项目中到处乱飞的重复环境变量，收口到统一的配置读取模块。
4. **虚拟环境与依赖收敛**：规范化 Python 和 Node 依赖，清理无用配置和冗余的虚拟环境残留。
5. **引入现代最佳实践**：主动建议并落实 DRY、SOLID 原则，添加全局错误处理、统一日志、DTO 数据清洗等，不断提升代码可读性与健壮性。

### 数据真实性

- 不允许 mock 数据、假数据、前端硬编码假字段
- 数据库只用 MySQL
- 不允许修改 `.env`、密钥文件、volume 数据

### 接口漂移处理

OpenAPI 已过时，不以它为强约束。但改动接口时：

- 要同时改前后端对应的调用点（不能只改一侧）
- 在 WORKFLOW.md 记录漂移点（改了什么字段、为什么）
- 不需要审批，但需要记录

---

## 改动规模分级

| 规模 | 判断标准 | 操作方式 |
|------|---------|---------|
| 小修 | 1-2 个文件，局部字段/逻辑 | 直接修改，commit，记录 |
| 中等 | 3-5 个文件，跨前后端联调 | 说明范围和影响，确认后修改 |
| 大改 | 涉及数据结构/Agent/核心 service/多页面 | 先写 spec（`docs/superpowers/specs/`），走设计流程 |

---

## 测试与检查

每次修改后运行：

```bash
# 前端
npm run lint
npm run build

# 后端语法
python3 -m py_compile <修改的 .py 文件>

# 后端测试（如果涉及已有测试）
cd backend && python3 -m pytest tests/<相关测试文件> -v
```

构建失败必须修复后再 commit。如果测试失败需说明：命令、失败位置、是否修复。

---

## Git

- 当前分支：`feat/backend-agent-integration`，不切换分支
- 不运行 `git reset --hard`、`git clean -fd`、`git push --force`
- 不运行 `git push`，除非用户明确要求
- 每完成一批文件修改后 commit
- commit message 用简洁中文，描述做了什么

---

## 进度记录

完成一个功能点后，在 `WORKFLOW.md` 末尾追加：日期、改了什么文件、核心改动、测试结果、是否有接口漂移。

`docs/feature-ledger.md` 不要频繁更新，它已经偏移，更新它的收益低于维护成本。
` /home/yezisama/workspace/workflow/EDUagent/frontend/docs/requirements-coverage.md`内部需要更新功能/接口实现记录
---

## 禁止修改

密钥文件 / 凭据文件 / MySQL volume 数据 / 用户上传文件 / 构建产物 / `node_modules` / 缓存目录
*(注：环境变量 `.env` 相关的重构需经过 Spec 计划明确后方可操作整理)*
