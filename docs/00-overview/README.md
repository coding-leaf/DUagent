# EDUagent 项目总览

## 当前架构

```text
Frontend (React)
    |
    | HTTP / SSE
    v
Backend (FastAPI, MySQL authority)
    |
    | internal HTTP / webhook
    v
Agent Service v2 (AgentScope 2.x)
    |
    +-- LLM provider
    +-- Qdrant
    +-- isolated workspaces
```

- Frontend 不直连 Agent Service。
- Backend 负责鉴权、课程权限、MySQL、任务状态和业务落库。
- Agent Service v2 负责 Agent/Team、工具、RAG、Memory、Workspace 和模型调用。
- Agent Service 不访问 MySQL；Backend 不直接访问 Qdrant。

## 目录

```text
frontend/                    React、SWR、页面与组件
backend/                     FastAPI、Service、MySQL 模型与测试
agent_service_v2/            AgentScope 2.x Agent Service
docs/10-client-api/          Frontend ↔ Backend 契约
docs/20-agent-api/           Backend ↔ Agent Service v2 契约
```

## Agent Service v2 能力

| 路径 | 能力 |
|---|---|
| `/agent/v2/workbench/chat` | AI Chat、工具调用与产物流 |
| `/agent/v2/workbench/artifacts` | 受控产物读取 |
| `/agent/v2/knowledge/ingestions` | 课程资料入库 Qdrant |
| `/agent/v2/knowledge/knowledge-graphs/generations` | 知识图谱生成 |
| `/agent/v2/knowledge/quiz/generations` | 题目生成 |
| `/agent/v2/knowledge/resources/generations` | 公共学习资源生成 |
| `/agent/v2/evaluation/generations` | 学情评估 |
| `/agent/v2/evaluation/quiz/diagnose` | 作答诊断 |
| `/agent/v2/personalized-resources/*` | 个性化资源 Agent Team |

画像刷新由 Backend 规则服务完成；学习路径由 Backend 根据 active KG 和实时进度计算。

## 数据归属

| 数据 | 权威位置 |
|---|---|
| 用户、课程、任务、画像、评估、资源 | MySQL / Backend |
| 用户上传 PDF | `backend/storage/course_catalogs/` |
| 课程切片和向量 | 独立 Qdrant 服务 |
| Agent 运行产物与 offload | `agent_service_v2/workspaces/` |

PDF 不复制进 Agent Service 源码目录；Agent Service 通过 Backend 传入的可信资料路径执行入库。

## 本地运行

```bash
./start_all.sh setup
./start_all.sh start
```

默认端口：Frontend 5173（或 Vite 自动选择）、Backend 8001、Agent Service v2 8002、Qdrant 6333、MySQL 3306。

## 验证

```bash
cd frontend && npm run lint && npm run build
cd backend && ../.venv/bin/python -m pytest tests/<相关测试> -q
cd agent_service_v2 && ./.venv/bin/pytest
```

部署和运行方式见项目根目录 `README.md`；接口字段、路径和状态枚举以两份 OpenAPI 契约为准。
