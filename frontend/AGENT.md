# AGENT.md

## Scope

- 开始前先读 `README.md`，获取当前阶段、目录导读、运行方式和阶段一范围。
- `AGENT.md` 只负责前端协作规则与修改约束，不承担页面字段清单、接口分析或进度记录职责。

- 负责 `frontend/` 内的浏览器端 React 应用。
- 负责学生端学习流程、教师端学情查看、管理员基础控制台、路由保护、前端状态、浏览器侧 Backend API 调用、SSE 流式渲染和 Mock 演示。
- 不负责 `backend/` 的 FastAPI 路由、SQL、鉴权实现、Agent HTTP 适配和 Webhook 落库。
- 不负责 `agent_service/` 内部的 LLM、AgentScope、RAG、提示词和智能体编排实现。
- Frontend 只通过 Backend `/api/v1` 访问业务能力；不直接调用 Agent Service `/agent/v1`，不直接访问数据库或 Qdrant。

- 目前处于前后端联调阶段。前端页面以现有 Client API 能承接的主链路为优先，不用硬编码假数据补齐未定契约能力。

## Source Of Truth

开发时优先级如下：

1. `README.md` — 前端当前阶段、目录入口、运行方式和阶段范围
2. `docs/Client-API.openapi.json` — 前端可调用 Backend Client API 契约
3. `docs/API_前端接口规范.md` — 字段语义、错误码和接口说明
4. 当前 `src/` 代码 — 已落地页面、服务封装和状态管理
5. `e2e/specs.spec.js` — 阶段一主链路验收参考
6. `docs/Agent-Service.openapi.json`、`docs/API_Agent内部接口规范.md` — 仅用于判断是否涉及 Agent API 间接契约，不作为前端直接调用依据

- 根目录或后端目录下同名文档若与 `frontend/docs/` 冲突，先说明冲突并等待用户确认。
- `api_mismatch_analysis.md`、`frontend_completeness_analysis.md`、`integration_plan.md`、`phase_1_frontend_integration_plan.md`、`前端页面字段与布局结构数据报告.md` 等分析文档只作为排查参考，不高于正式 API 契约。
- `开发进度.md` 可作为前端进度恢复上下文；临时任务和下一步建议不要写入 `AGENT.md`。

## Contract Discipline

- 不允许隐式扩展 API 契约。
- 不允许新增、删除、重命名任何正式 Client API 字段、路径参数、query 参数、response 字段、状态枚举，除非用户明确确认。
- 前端不得因为页面缺字段而自行发明响应字段、拼接隐含语义或把 Mock 字段当正式字段。
- 如果 Backend 返回空数组、空对象、`null` 或字段缺失，优先展示 Empty / Unknown / Loading / Error 状态；不要回退到假数据伪装成功。
- 只要字段会被 `src/api/services/` 暴露给页面使用，就视为前端可见契约；不得以“只是适配层内部字段”为理由隐式新增。
- 任何同步/异步行为变化也视为契约变化，必须先确认。包括但不限于：
  - 原本页面轮询任务状态，改为提交后直接等待生成完成
  - 原本普通 JSON 请求，改为 SSE 或长轮询
  - 原本快速返回，改为依赖 Agent / 外部服务调用时长
  - 原本同步返回结果，改为返回 `task_id` 后轮询
- 修改 API 调用前，必须先核对：
  - `docs/Client-API.openapi.json`
  - `docs/API_前端接口规范.md`
  - 如涉及 Agent 间接能力，再核对 `docs/Agent-Service.openapi.json` 和 `docs/API_Agent内部接口规范.md`

修改说明中必须显式写出：

- 本次是否改变 Client API 契约：`是` / `否`
- 本次是否改变 Agent API 契约：`是` / `否`

若实现发现现有契约不足，必须先停止修改，并向用户明确说明：

1. 当前契约限制
2. 为什么无法按现有契约正确实现
3. 建议的契约变更
4. 受影响的文档和代码文件

未获确认前，不允许先改代码再补文档。

## Architecture Boundaries

### Frontend 分层职责

- `src/api/client.js`：Axios 实例，读取 `VITE_API_BASE_URL`，统一注入 `access_token`，统一返回 Backend 包装后的响应数据。
- `src/api/services/`：按业务模块封装 Backend Client API。页面不得绕过 service 层散落拼接接口，SSE 等特殊场景除外。
- `src/api/mock/`：`VITE_USE_MOCK=true` 时启用的本地演示和断网调试数据。Mock 必须尽量贴近正式 Client API，不得成为契约来源。
- `src/context/`：跨页面状态，例如 `AuthContext`、`CourseContext`。不要把页面私有状态提升到 Context。
- `src/components/`：通用 UI 和通用交互组件，例如导航、路由保护、反馈状态、报告弹窗和图表。
- `src/pages/`：页面级组件，负责组合 service、context 和 components。避免把可复用的 API 适配、鉴权恢复或复杂状态机直接堆在页面中。
- `e2e/`：Playwright 主链路验收。E2E 依赖 Backend、Agent Service、测试数据库和种子数据就绪。

### Frontend 负责

- 登录、注册、验证码、Token 存取和 `/users/me` 鉴权恢复的浏览器侧流程
- 学生 / 教师 / 管理员角色路由保护
- 课程列表、课程切换和 `course_id` 上下文传递
- 学生 Dashboard、学习路径、Quiz、AI Chat、学习效果等页面渲染
- 教师端学生列表和基础学情报告展示
- 管理员基础用户和日志页面展示
- SSE 文本流解析、取消和错误反馈
- Loading、Empty、Error、Unauthorized 等用户可见状态

### Backend 负责

- Client API 路由、鉴权和统一返回 `{code, message, data}`
- SQL 查询和写入
- Agent Service HTTP 调用、异步任务状态、Webhook 结果落库
- SSE 代理转发

### Agent Service 负责

- LLM 调用、AgentScope 编排、RAG 检索、资源生成、测验评估和智能辅导内容生成

### 禁止

- Frontend 直接调用 Agent Service `/agent/v1`
- Frontend 直接访问 SQL、Qdrant 或本地后端内部文件
- 页面绕过 `src/api/services/` 大量散落 API path
- 用 Mock 数据掩盖真实 API 缺字段、报错或空状态
- 修改 `docs/` 下正式接口文档，除非用户明确要求
- 把进度、临时计划、测试记录长期写进 `AGENT.md`

## Code Change Rules

- 修改代码前需要分析并说明问题。
- 修改代码前必须先输出：
  1. 问题分析
  2. 计划修改的文件
  3. 修改方案
  4. 可能影响的功能
- 用户确认后，才允许修改文件。
- 保持 React + Vite + JavaScript + JSX 的现有技术栈和命名风格。
- 以页面、service 或明确子能力为修改边界；一次不超过 5 个文件。
- 不要过度工程化。只有在减少真实重复、隔离契约适配或简化复杂页面状态时才新增抽象。
- 新增跨页面组件、Context 或 service 函数时添加简短注释，说明作用、主要输入和输出。
- 简单私有辅助函数不强制添加长注释，优先用清晰命名表达意图。
- 不引入新依赖，除非用户确认必要性、安装方式和影响范围。
- 不大规模重写 UI 风格。现有页面以 `src/index.css` 的设计变量、组件样式和当前布局为准。
- 修改登录、鉴权、课程上下文、SSE、Quiz 提交、资源生成任务轮询等主链路时，必须同步评估相关页面影响。

## Incremental Development

- 默认一次只推进一个页面、一个接口适配或一个明确子能力。
- 优先修正 `src/api/services/` 的契约适配，再调整页面渲染。
- 如果页面需要的数据不在正式 Client API 中，先展示可解释的空状态或提出契约变更，不要在页面内硬编码推导。
- Mock 更新必须与真实 service 行为一起审查，确保 `VITE_USE_MOCK=true` 只用于演示，不改变真实联调判断。
- 修改可见交互后，至少覆盖桌面浏览器的基本手工检查；涉及响应式布局时同时检查移动宽度。

## Testing

- 使用 npm 脚本作为前端验证入口：
  ```bash
  npm run lint
  npm run build
  npm run test:e2e
  ```
- 修改 JS / JSX / CSS 后，至少运行 `npm run lint` 和 `npm run build`。
- 修改主链路页面、路由、鉴权、课程上下文、SSE、Quiz 或教师端流程后，尽量运行 `npm run test:e2e`。
- E2E 依赖测试数据库、种子数据、Backend 和 Agent Service。环境未就绪时，必须说明未运行原因，不能静默跳过。
- 修改 API service 后重点验证：
  - 请求路径、path 参数、query 参数与 OpenAPI 一致
  - request body 字段与接口规范一致
  - response 字段访问前处理 `null` / 空数组 / 缺字段
  - 错误状态有用户可见反馈
  - `VITE_USE_MOCK=false` 时不会走 Mock-only path
- 修改 SSE 后重点验证：
  - token 传递
  - `data:` 行 JSON 解析
  - `chunk` / `diagram` / `knowledge_points` / `done` 事件处理
  - AbortController 取消逻辑
  - 网络错误不会导致页面崩溃

## Context Handoff

每次开始 Frontend 联调前，先执行：

```bash
pwd
git status --short
npm run lint
```

如需真实联调，再确认：

```bash
VITE_USE_MOCK=false VITE_API_BASE_URL=http://localhost:8001/api/v1 npm run dev
```

跨窗口继续时，以 `AGENT.md`、`README.md`、`开发进度.md`、`git status --short`、最近测试结果为主要上下文。

## Git

- 避免在 `main` / `master` / `dev` 直接开发。
- 默认在用户当前分支工作；如需新分支，先说明分支名和原因。
- 修改前识别已有未提交内容，不回滚、不覆盖无关改动。
- 使用 `git stash` 前必须告知用户。
- 每次修改后 git commit（不 push）。
- 提交只纳入本轮文件，不能顺手提交用户已有无关改动。

## Completion Summary

每次完成任务后回复包含：

- 当前完成
- 修改文件
- 测试结果
- Client API 契约是否漂移
- Agent API 契约是否漂移
- 下一步建议
