# AGENTS.md — 全局协作约束（v3）

> 本文档为项目根目录全局约束，对 `frontend/`、`backend/`、`agent_service/` 全部生效。
> 各子目录有同名文件时，**子目录 AGENTS.md 补充局部细节，但不得与本文件冲突**。

---

## 当前阶段

**v3 — 架构强化与功能迭代并行**

- v2 完成了：功能打通、主链路联调、核心重构（胖路由拆分、SWR/MVVM、分层架构）
- v3 目标：在稳定架构基础上继续新功能开发，同时持续提升代码质量和可维护性
- 工作存档统一写入 `WorkLine.md`，不再使用 WORKFLOW.md 堆日记

---

## 子项目边界速查

| 任务类型 | 看哪里 |
|---------|--------|
| 前端页面 / 组件 / hook | `frontend/AGENTS.md` |
| 后端 API / 数据库 / 鉴权 | `backend/AGENTS.md` |
| Agent 编排 / LLM / RAG | `agent_service/AGENTS.md` |
| **跨模块交互 / 根目录决策** | 本文件 |

---

## 权威来源（按优先级）

查证"该怎么做"时，按以下顺序：

1. **当前运行代码**（`frontend/src/`、`backend/app/`、`agent_service/`）— 代码是最终事实
2. **`docs/` 下的 API 契约**（`docs/10-client-api/`、`docs/20-agent-api/`）— 接口边界基准
3. **`WorkLine.md`**（本项目工作存档，近期决策和验证结论在这里）
4. **`PROJECT.md`**（架构说明与里程碑）

文档与代码冲突时，**以代码为准，在 WorkLine.md 记录差异**。

---

## 跨模块边界规则（硬约束）

```
前端  ──HTTP──▶  Backend API  ──HTTP──▶  Agent Service
                     │                        │
                   MySQL                   Qdrant
```

- **前端不直连 Agent Service**，所有 AI 能力通过 Backend 代理
- **Agent Service 不写 MySQL**，持久化数据必须通过 Backend Webhook 落库
- **Backend 不导入 `agent_service` Python 模块**，只通过 HTTP 调用
- **Backend 不直接访问 Qdrant**，向量检索由 Agent Service 负责
- Agent Service 使用 Backend 传入的 `task_id`，不自行生成

违反以上任意一条，必须停下来说明原因，等待用户确认。

---

## 任务规模分级

| 规模 | 判断标准 | 操作方式 |
|------|---------|---------|
| **小修** | 1-2 个文件，局部逻辑/字段 | 直接修改，commit，更新 WorkLine |
| **中等** | 3-5 个文件，跨层或跨前后端 | 先说明范围和影响，确认后修改 |
| **大改** | 涉及数据结构 / Agent 编排 / 核心 service / 多页面联动 | 先在对话中输出设计方案，用户确认后再动手 |

> 跨模块提取、环境清理、接口变更——无论文件数量多少，一律按「大改」处理。

---

## 修改前必须输出

**任何代码修改前**，先回复：

1. 问题分析（为什么要改）
2. 计划修改的文件清单
3. 修改方案概述
4. 可能影响的功能

用户确认后，才允许编辑文件。

---

## 接口契约纪律

- 不允许隐式扩展 API 字段、路径、状态枚举
- 修改接口时必须同步改前后端两侧调用点，不能只改一侧
- 每次接口变动在 WorkLine.md 记录：改了什么字段、为什么

---

## 验证命令（每次修改后）

```bash
# 前端
cd frontend && npm run lint && npm run build

# 后端语法检查
python3 -m py_compile backend/app/<修改的文件.py>

# 后端测试
cd backend && python3 -m pytest tests/<相关测试> -v

# Agent Service 测试
cd agent_service && ./.venv/bin/pytest
```

构建或测试失败必须修复后再 commit。

---

## Git 规范

- 当前分支：`refactor/v3-architecture`
- 不在 `main` / `dev` 直接提交
- 不运行 `git push --force` / `git reset --hard` / `git clean -fd`
- 不运行 `git push`，除非用户明确要求
- 使用 `git stash` 前必须告知用户
- 每完成一批文件修改后 commit，commit message 用简洁中文

---

## 完成任务后必须汇报

```
当前完成：
修改文件：
测试结果：
接口是否漂移：
WorkLine 是否已更新：
下一步建议：
```

---

## 禁止操作

- 修改 `.env` 文件（含各子项目）
- 修改密钥、凭据、MySQL volume 数据
- 删除或覆盖用户上传文件
- 提交 `node_modules`、`.venv`、`__pycache__`、构建产物
- 编造 AgentScope / OpenAPI 接口，未经确认不得使用不存在的 API
