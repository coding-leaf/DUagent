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

## 路径导航与文档分工

| 文件 / 目录 | 用途 |
|------------|------|
| `AGENTS.md` | 根目录全局协作约束。文件名必须保持全大写，子模块也统一使用 `AGENTS.md`。 |
| `frontend/AGENTS.md` | 前端局部规则，只补充 UI、SWR/MVVM、前端验证等细节。 |
| `backend/AGENTS.md` | 后端局部规则，只补充 FastAPI 分层、数据库、契约和测试细节。 |
| `agent_service/AGENTS.md` | Agent Service 局部规则，只补充 AgentScope、RAG、多智能体和模型调用边界。 |
| `TODO.md` | USER 灵感碎片和待办池，允许保留不完整想法，不作为事实结论。 |
| `赛题疑点` | A3 赛题原文摘录、疑问和需求理解草稿。用于对齐比赛要求，不作为实现状态源。 |
| `docs/90-review/` | 放正式审计、验收、差距分析文档。例如 A3 赛题需求差距审计。 |
| `docs/superpowers/specs/` | 放用户确认后的设计文档，不放随手 TODO。 |
| `docs/superpowers/plans/` | 放已经确认设计后的实施计划。 |
| `WorkLine.md` | 当前唯一工作存档，记录已完成修改、验证命令、接口漂移和下一步。 |
| `WORKFLOW.md` | 旧版历史记录，只读追溯，不再追加新记录。 |

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

**中等 / 大改提交前，必须在回复中附上结构化自检结果：**

- [ ] 新增/修改文件未出现单文件超长（参考上限 300 行）或单函数超长（参考上限 50 行）；若超出已说明拆分理由
- [ ] 没有引入 `package.json` / `requirements.txt` 中未声明的新依赖
- [ ] 没有在 Router / Page 层写业务逻辑、SQL 查询或直接 LLM 调用
- [ ] 注释只写 why，没有解释 what

小修（1-2 文件）免自检。

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

## 架构模式规范

> 原则优先，反例说明典型错误。AI 在生成代码时必须主动遵守，不需要用户每次提醒。

### 前端（React / SWR / MVVM）

**原则：**
- `pages/` 是容器，只负责组装子组件，不写业务逻辑、不直接调 API
- 所有数据获取统一通过 `hooks/` 下的 SWR hook，不在组件内手写 `useEffect` + `fetch`
- `components/` 下的组件只接收 props 渲染，不持有异步状态

**典型反例：**
```js
// ❌ Page 里直接 fetch
const [data, setData] = useState()
useEffect(() => { fetch('/api/xxx').then(r => r.json()).then(setData) }, [])

// ✅ 应该
const { data, isLoading } = useXxxData(courseId)  // hooks/ 下的 SWR hook
```

```js
// ❌ 组件内自己管异步状态
function ResourceCard() {
  const [detail, setDetail] = useState()
  useEffect(() => { fetchDetail(id).then(setDetail) }, [id])
}

// ✅ 应该由父级 hook 提供数据，组件只渲染
function ResourceCard({ detail }) { ... }
```

---

### 后端（FastAPI 分层）

**原则：**
- `api/v1/` Router 只做：鉴权依赖注入、参数校验、调用 Service、包装响应 `{code, message, data}`
- 业务逻辑、DB 查询、Agent 调用必须下沉到 `services/`
- Router 函数体参考上限 30 行；超出说明原因

**典型反例：**
```python
# ❌ 路由里直接写 SQL
@router.get("/courses")
async def list_courses(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Course).where(Course.is_deleted == 0))
    return result.scalars().all()

# ✅ 应该
@router.get("/courses")
async def list_courses(current_user=Depends(get_current_user), db=Depends(get_db)):
    data = await course_service.list_courses(db, current_user.id)
    return success(data)
```

---

### Agent Service（编排分层）

**原则：**
- `agents/` 负责编排多步流程，不直接调 LLM
- `tools/` 封装单一原子能力（RAG 检索、结构化输出等），不包含流程判断
- `prompts/` 只存提示词模板，不含调用逻辑

**典型反例：**
```python
# ❌ 在 api/ 路由里直接调 LLM
@router.post("/generate")
async def generate(req: Request):
    result = await llm.chat(prompt)  # 路由层不该出现 LLM 调用
    return result

# ✅ 应该走 agents/ 编排
@router.post("/generate")
async def generate(req: Request):
    result = await resource_agent.run(req.task_id, req.context)
    return result
```

---

## 代码生成规范

> 以下为 AI 生成代码时的默认风格约束，适用于所有子项目。

### 文件与函数体积

原则：单文件保持聚焦，函数保持短小。文件超过 300 行、函数超过 50 行时，优先考虑拆分，而不是继续堆叠。

反例：
```
❌ 把所有逻辑写进一个 500 行的 Page 或路由文件
✅ 提取 hook / service / 子组件，主文件退化为组装容器
```

---

### 注释风格

原则：**只写 why，不写 what。** 代码本身说明在做什么，注释解释为什么这样做（隐含约束、历史原因、非直觉决策）。

反例：
```python
# ❌ 解释 what（代码已经说清了，注释是噪音）
# 查询未删除的课程列表
courses = await course_service.list_active(db)

# ✅ 解释 why（读代码看不出来的原因才值得写）
# skip catalog-less courses — frontend KG panel crashes on null catalog_id
courses = await course_service.list_with_catalog(db)
```

---

### 依赖引入

原则：不引入 `package.json` / `requirements.txt` 中未声明的库。需要引入新依赖时，必须先说明：
1. 用途是什么
2. 为什么现有工具不够用
3. 对 bundle 大小或依赖树的影响

反例：
```
❌ 直接 import 一个新库，不解释为什么不用已有的
❌ pip install 新包，不更新 requirements.txt 说明
✅ "需要 dayjs 的 duration 插件处理时长显示，项目已安装 dayjs，仅需 import 插件，无需新增依赖"
```

---

### 工具优先复用

原则：项目已有的工具、封装、hook，直接用，不另造一套。

| 场景 | 使用 | 禁止 |
|------|------|------|
| 前端数据获取 | `hooks/` 下对应 SWR hook | 手写 `useEffect` + `useState` fetch |
| 前端日期格式化 | `src/utils/date.js` | 新写格式化函数 |
| 前端网络请求 | `src/api/client.js`（已有拦截器） | 直接 `fetch()` 或引入 axios |
| 后端 Agent 调用 | `services/agent_client.py` | 路由层直接 `httpx.post` |
| 后端错误响应 | 全局异常处理器 | 路由内自定义 `try/except` 返回错误格式 |

---

## 禁止操作

- 修改 `.env` 文件（含各子项目）
- 修改密钥、凭据、MySQL volume 数据
- 删除或覆盖用户上传文件
- 提交 `node_modules`、`.venv`、`__pycache__`、构建产物
- 编造 AgentScope / OpenAPI 接口，未经确认不得使用不存在的 API
