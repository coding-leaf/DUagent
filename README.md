# DUagent 开发者交接与生产部署指南

DUagent 是面向高校课程教学的多智能体个性化导学平台。本仓库包含完整的三端源码（`frontend/`、`backend/`、`agent_service_v2/`）、生产部署脚本（`deploy_prod.sh`）以及 **Trellis 规范化 AI 工程工作流**（`.trellis/`）。

---

## 一、快速上手与架构全景（接手必读）

### 1.1 系统拓扑与职责边界

```text
Frontend (React 19 + Vite, 开发 :5173 / 生产同源托管)
    │  HTTP (/api/v1/*) + SSE 流式对话 (Bearer JWT)
    ▼
Backend (FastAPI + SQLAlchemy 2.0, :8001)  ──► MySQL (:3306, 唯一关系数据权威源)
    │  内部 REST (/agent/v2/*) + Webhook (/api/v1/webhooks/agent)
    │  Agent 回写 (/internal/*, X-Internal-Agent-Token)
    ▼
Agent Service v2 (AgentScope 2.x + uv, 127.0.0.1:8002)
    ├── Qdrant (:6333/6334, 课程教材向量库，按 catalog_id 索引)
    ├── Redis (:6379, AgentScope 运行时状态)
    ├── Judge0 (:2358, 代码沙箱评测)
    └── Workspaces (agent_service_v2/workspaces/, 会话受控文件产物)
```

- **核心隔离原则**：
  - `Frontend` 仅与 `Backend` 通信，**严禁**直连 `Agent Service`；
  - `Backend` 是业务编排与 MySQL 唯一入口，**严禁**直接调用任何 LLM SDK（所有大模型能力均经由 `app/services/agent_client.py` 委托给 `Agent Service v2`）；
  - `Agent Service v2` 负责 Prompt、ReAct 工具链、RAG 检索与课程规划，**不直接连接 MySQL**，需读写业务数据时统一通过 `BackendLearningClient` 调用 Backend 的 `/internal/*` 接口。

### 1.2 核心目录与关键文件速览

| 目录 / 文件 | 说明 |
| --- | --- |
| `backend/` | FastAPI 业务后端（`app/api/v1/` 公开路由、`app/api/internal_*.py` 内部回调、`app/services/` 业务逻辑、`app/models/` ORM 模型、`tests/` 单测） |
| `agent_service_v2/` | AgentScope 2.x 智能体服务（`agents/workbench_react_agent.py` 对话工作台、`agents/curriculum_planner.py` 学科自适应知识图谱规划、`generators/` 资源与题库生成流水线、`tools/` 工具集） |
| `frontend/` | React 19 + Vite + Tailwind v4 纯 JSX 前端（`src/api/` 统一 Axios 客户端与服务、`src/pages/` 页面、`src/components/` 组件、`src/hooks/` SWR 状态钩子） |
| `docs/` | 自动导出的最新接口契约：`10-client-api/Client-API.openapi.json`（前后端）与 `20-agent-api/Agent-Service.openapi.json`（后端与 Agent） |
| `.trellis/` | **Trellis 工程规范与任务记忆库**：`.trellis/spec/` 存放三端架构红线与代码规范，`.trellis/tasks/archive/` 存放历次重构的设计与验收记录 |
| `check_all.py` | **全仓唯一质量门禁脚本**：一键串联前端 ESLint、Vite Build、Backend Ruff + Pytest、Agent Ruff + Pytest 共 6 项检查 |

### 1.3 本地开发环境启动

首次拉取仓库后，在根目录准备 `.env`（可参考 `deploy/env.production.example`）并启动本地热重载开发环境：

```bash
./start_all.sh setup   # 检查基础环境并安装三端依赖 (.venv / uv / npm)
./start_all.sh start   # 启动 Docker 基础组件 + Backend(8001) + Agent(8002) + Vite(5173) 热重载
```

- `start_all.sh start` 会锁定前端端口为 `5173`（`strictPort: true`）并自动注入 `BACKEND_INTERNAL_AGENT_TOKEN`。
- 按 `Ctrl+C` 仅停止本机开发进程，不会删除数据库或 Docker 数据卷。

### 1.4 质量门禁与测试命令

在提交任何代码前，**必须**在仓库根目录执行统一门禁：

```bash
# 全仓 6 大门禁（Frontend Lint + Build, Backend Ruff + Pytest, Agent Ruff + Pytest）
python -X utf8 check_all.py

# 快速静态门禁（跳过耗时 Pytest，仅跑三端 Lint + 前端 Build，约 10 秒）
python -X utf8 check_all.py --fast

# 前端 Vitest 单元测试
cd frontend && npm run test:unit
```

---

## 二、Trellis 规范化开发工作流导览

本项目使用 **Trellis** 管理架构约束（Specs）、开发任务（Tasks）与会话演进日志（Workspace Journal）。建议在支持 `AGENTS.md` / Skills 的 AI 编程助手（如 Pi、Claude Code、Codex、Cursor、OpenCode）中按以下流程协作：

### 2.1 三端架构红线（写代码前必查 `.trellis/spec/`）

每个模块均设有不可逾越的 `architecture-guardrails.md` 与 `quality-guidelines.md`：

1. **Backend (`.trellis/spec/backend/backend/architecture-guardrails.md`)**：
   - 严禁在 `backend` 内直调大模型或拼装 Prompt；
   - SQLAlchemy 布尔过滤必须写 `Model.is_deleted == False`，严禁写 `not Model.is_deleted`（`ruff.toml` 已为此全局豁免 `E712`）；
   - 课程级接口必须前置调用 `await ensure_course_resource_access(db, current_user, course_id)`；
   - 触发 Agent 个性化资源生成时必须同时传递业务教学班 `course_id` 与教材向量索引键 `catalog_id`；
   - 文件下载接口仅接受 `Authorization: Bearer` Header，严禁使用 Query `?token=`。
2. **Agent Service v2 (`.trellis/spec/agent_service_v2/backend/architecture-guardrails.md`)**：
   - Prompt 必须保持**学科中立**（从 `course_title` 与大纲动态注入学科，严禁硬编码“C语言/Python”等词）；
   - 严禁在沙箱中动态生成脚本解析文档，统一使用 `tools/outline_extractor.py` 与 `tools/rag.py`；
   - `ResourceGenerationRequest.webhook_url` 强制校验协议与云元数据 SSRF 防护；`BackendLearningClient.post_json` 统一收敛传输层与非 JSON 异常。
3. **Frontend (`.trellis/spec/frontend/frontend/architecture-guardrails.md`)**：
   - 纯 JavaScript / JSX 项目，严禁擅自引入 TypeScript（`.ts/.tsx`）或重型第三方 UI 组件库；
   - 局域网 HTTP 部署兼容：生成客户端唯一 ID 必须使用 `src/utils/id.js` 的 `uid()`，严禁裸调 `crypto.randomUUID()`；
   - 错误提取统一使用 `src/utils/apiError.js` 的 `getErrorMessage`；图标统一通过 `src/components/Icon.jsx` 映射至 `lucide-react`。

### 2.2 标准任务生命周期

```bash
# 1. 查看当前工作流上下文与活跃任务
python ./.trellis/scripts/get_context.py

# 2. 创建新任务并编写规划文档 (prd.md / design.md / implement.md)
python ./.trellis/scripts/task.py create "<任务标题>" --slug <task-slug> -p <backend|frontend|agent_service_v2>

# 3. 校验上下文清单并激活任务进入实施阶段 (in_progress)
python ./.trellis/scripts/task.py validate .trellis/tasks/<task-dir>
python ./.trellis/scripts/task.py start .trellis/tasks/<task-dir>

# 4. 实施并通过 python -X utf8 check_all.py 后，提交代码、归档任务并记录日志
python ./.trellis/scripts/task.py archive <task-slug> --skip-branch-validation
python -X utf8 ./.trellis/scripts/add_session.py --title "<标题>" --commit "<hash>" --summary "<摘要>"
```

### 2.3 OpenAPI 契约同步刷新

当修改了 `backend` 或 `agent_service_v2` 的接口路由/Schema 时，请运行以下命令保持 `docs/` 下的契约文件同步：

```bash
./.venv/Scripts/python -c "import json, sys; sys.path.insert(0, 'backend'); from app.main import app; open('docs/10-client-api/Client-API.openapi.json', 'w', encoding='utf-8').write(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + '\n')"
uv run --project agent_service_v2 python -c "import json; from agent_service_v2.main import app; open('docs/20-agent-api/Agent-Service.openapi.json', 'w', encoding='utf-8').write(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + '\n')"
```

---

## 三、生产环境部署与运维指南

生产部署后，通过 Backend 的 `8001` 端口同时托管前端静态产物与公开 API；Agent Service 及数据库等基础设施仅监听本机回环地址。

### 3.1 分支与部署拓扑

- **分支约定**：`main` 为唯一可部署稳定分支；日常开发在 `dev` 或 `feature/*` 进行，通过全量门禁后合入 `main`。
- **运行端口**：

| 服务 | 运行方式 | 默认监听地址 |
| --- | --- | --- |
| Frontend + Backend | 宿主机 Python 进程（Backend 同源托管前端 `dist/`） | `0.0.0.0:8001` |
| Agent Service v2 | 宿主机 Python (`uv`) 进程 | `127.0.0.1:8002` |
| MySQL / Qdrant / Redis / Judge0 | Docker Compose | `127.0.0.1:3306` / `6333` / `6379` / `2358` |

### 3.2 服务器环境准备（Ubuntu 24.04+）

需要安装：`docker`、`docker compose` (v2)、`python3` (支持 `venv`)、`npm` (Node.js 22)、`uv`、`curl`。可使用仓库内置脚本自动检查或安装：

```bash
./bootstrap_ubuntu.sh check          # 只读检查缺失工具
sudo ./bootstrap_ubuntu.sh install   # 自动安装缺失工具（不破坏已有容器与数据卷）
```

### 3.3 首次部署与配置 `.env`

```bash
git clone --branch main --single-branch https://github.com/coding-leaf/DUagent.git DUagent-prod
cd DUagent-prod

# 1. 首次执行 check 会自动从模板生成权限为 600 的根 .env
./deploy_prod.sh check
nano .env
```

在 `.env` 中替换所有占位符（可使用 `openssl rand -hex 32` 生成随机密钥）：
- **安全密钥**：`DB_PASSWORD`、`JWT_SECRET_KEY`、`WEBHOOK_SECRET`、`INTERNAL_AGENT_TOKEN`、`JUDGE0_POSTGRES_PASSWORD`、`JUDGE0_REDIS_PASSWORD`（注：生产模式下 `WEBHOOK_SECRET` 为空将拒绝服务）。
- **模型配置**：`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 以及 `EMBEDDING_BASE_URL`、`EMBEDDING_API_KEY`、`EMBEDDING_MODEL`。

填写完成后执行正式部署与健康检查：

```bash
./deploy_prod.sh check     # 确认输出 Preflight passed
./deploy_prod.sh deploy    # 构建前端、安装依赖、初始化数据库并启动服务
./deploy_prod.sh status

# 验证服务与 Judge0 (cgroup v2 镜像)
curl -fsS http://127.0.0.1:8001/health
curl -fsS -X POST 'http://127.0.0.1:2358/submissions?base64_encoded=false&wait=true' \
  -H 'Content-Type: application/json' \
  -d '{"source_code":"print(\"judge0 cgroup v2 ok\")","language_id":71,"stdin":""}'
```

- **默认管理员账号**（仅在库中无管理员时幂等创建，首次登录后请立即修改密码）：
  - 账号：`admin@admin.com`
  - 密码：`Admin123456`

### 3.4 常用运维命令与排障

```bash
./deploy_prod.sh start | stop | restart | status   # 启停或查看应用进程状态（stop 不停止 Docker 容器）
./deploy_prod.sh logs [backend|agent]              # 查看 .run_logs/prod/ 下的运行日志
./deploy_prod.sh reset-judge0 --confirm            # 仅重置 Judge0 容器与卷（不影响业务 MySQL/Qdrant）

# 版本更新
git pull --ff-only origin main && ./deploy_prod.sh deploy
```

- **安全基线**：严禁提交 `.env` 或暴露内部端口（`3306`/`6333`/`6379`/`8002`/`2358`）至公网；云安全组仅需放行 TCP `8001`。
