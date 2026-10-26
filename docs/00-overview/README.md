# DUagent 架构总览

## 1. 服务拓扑与职责边界

```text
Frontend (React 19 + Vite, :5173 / 生产由 Backend 同源托管)
    |
    | HTTP (/api/v1/*) + SSE (Authorization: Bearer JWT)
    v
Backend (FastAPI + SQLAlchemy 2.0, :8001, MySQL 权威源)
    |
    | 内部 HTTP (/agent/v2/*) / Webhook (/api/v1/webhooks/agent)
    | 内部回调 (/internal/*, X-Internal-Agent-Token)
    v
Agent Service v2 (AgentScope 2.x, 127.0.0.1:8002)
    |
    +-- LLM / Embedding Provider
    +-- Qdrant (:6333, 课程切片向量库，按 catalog_id 索引)
    +-- Redis (:6379, AgentScope 运行时)
    +-- Isolated Workspaces (agent_service_v2/workspaces/)
```

- **Frontend** 不直连 Agent Service；所有请求经由 `frontend/src/api/client.js` 发往 Backend。
- **Backend** 负责鉴权、课程访问控制（`ensure_course_resource_access`）、MySQL 事务、异步任务状态和业务落库；**严禁在 Backend 内直调大模型**。
- **Agent Service v2** 负责 ReAct 导学工作台（`WorkbenchReActAgent`）、学科自适应课程图谱规划（`CourseCurriculumPlanner`）、RAG 检索与资源/题库生成；**不直接访问 MySQL**。

## 2. 目录结构

```text
frontend/                    React 19 + Vite + Tailwind v4 + SWR + Lucide 图标
backend/                     FastAPI 业务后端、SQLAlchemy 2.0 异步模型与集成测试
agent_service_v2/            AgentScope 2.x 智能体服务（uv 管理）
docs/10-client-api/          Frontend ↔ Backend OpenAPI 契约
docs/20-agent-api/           Backend ↔ Agent Service v2 OpenAPI 契约
.trellis/spec/               三端架构红线 (architecture-guardrails.md) 与质量规范
check_all.py                 全仓统一静态检查与单元测试门禁
```

## 3. Agent Service v2 核心端点

| 路径 | 能力 |
|---|---|
| `POST /agent/v2/workbench/chat` | AI Chat SSE 流式交互、工具调用与产物流 |
| `GET /agent/v2/workbench/artifacts` | 会话受控文件产物读取 |
| `POST /agent/v2/knowledge/ingestions` | 课程教材切片向量化入库 Qdrant（按 `catalog_id` 索引） |
| `POST /agent/v2/knowledge/knowledge-graphs/generations` | 学科自适应知识图谱 DAG 生成（含三色 DFS 防环） |
| `POST /agent/v2/knowledge/quiz/generations` | 知识点题库生成（基础题库 / 个性化加练） |
| `POST /agent/v2/knowledge/resources/generations` | 公共学习资源异步生成（完成后通过 Webhook 回写 Backend） |
| `POST /agent/v2/personalized-resources/generations` | 个性化学习资源生成（使用 `catalog_id` 检索 RAG，使用 `course_id` 落库发布） |
| `POST /agent/v2/evaluation/generations` | 阶段学情评估生成 |
| `POST /agent/v2/evaluation/quiz/diagnose` | 练习作答错因诊断 |

## 4. 数据归属权威源

| 数据类型 | 权威位置 |
|---|---|
| 用户、班课 (`Course`)、课程目录 (`CourseCatalog`)、任务、画像、题库、资源 | MySQL (`backend`) |
| 上传的课程原始教材 (PDF/DOCX/MD) | `backend/storage/course_catalogs/` |
| 教材文本切片与 Embedding 向量 | Qdrant (`course_knowledge_v1_1024`，`metadata.course_id = catalog_id`) |
| 对话工作台生成的文件产物 | `agent_service_v2/workspaces/` |

## 5. 本地开发与全仓门禁

```bash
# 启动本地热重载环境（Frontend :5173, Backend :8001, Agent :8002）
./start_all.sh setup
./start_all.sh start

# 运行全仓 6 大质量门禁（ESLint + Vite Build + 双端 Ruff + 双端 Pytest）
python -X utf8 check_all.py

# 运行前端单元测试
cd frontend && npm run test:unit
```

完整的开发者交接导览、Trellis 工作流规范与生产部署步骤请参见根目录 [README.md](../../README.md)。
