# Agent Service 本地启动与运维

本文件只记录 `agent_service` 独立启动、验证和本地联调操作。

接口契约仍以仓库根目录下列文件为准：

- `../docs/20-agent-api/Agent-Service.openapi.json`
- `../docs/20-agent-api/API_Agent内部接口规范.md`
- `../docs/30-dev-guide/Agent-Service_开发导读.md`

## 目录与环境

所有命令默认在 `agent_service/` 目录执行：

```bash
cd /home/yezisama/workspace/workflow/EDUagent/agent_service
```

项目使用当前目录下的虚拟环境：

```bash
./.venv/bin/python
./.venv/bin/pytest
./.venv/bin/uvicorn
```

## 配置

复制配置示例：

```bash
cp .env.example .env
```

无 LLM / Embedding 配置时，接口会走规则版 fallback。

真实联调时至少建议配置：

```env
LLM_PROVIDER=agentscope_openai
LLM_BASE_URL=https://your-llm-endpoint/v1
LLM_API_KEY=sk-your-api-key
LLM_MODEL=deepseek-chat

EMBEDDING_PROVIDER=agentscope_openai
EMBEDDING_BASE_URL=https://your-embedding-endpoint/v1
EMBEDDING_API_KEY=sk-your-api-key
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1024

QDRANT_PATH=./qdrant_data
QDRANT_USER_MEMORY_COLLECTION=user_memory_v1_1024
QDRANT_COURSE_KNOWLEDGE_COLLECTION=course_knowledge_v1_1024
```

## 启动服务

推荐启动命令：

```bash
./.venv/bin/uvicorn agent_service.main:app --host 127.0.0.1 --port 8002
```

Backend 本地联调时可使用：

```env
AGENT_SERVICE_URL=http://127.0.0.1:8002
```

如需允许局域网访问：

```bash
./.venv/bin/uvicorn agent_service.main:app --host 0.0.0.0 --port 8002
```

不推荐作为标准启动方式：

```bash
./.venv/bin/python -m agent_service.main
```

原因：该入口主要用于开发，当前会走 `main.py` 内的 uvicorn 默认参数；本地联调请显式使用 `uvicorn agent_service.main:app`。

## 健康检查

服务启动后检查：

```bash
curl http://127.0.0.1:8002/agent/v1/health
```

期望返回：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "status": "healthy",
    "qdrant_connected": true,
    "model_loaded": false,
    "model_name": "",
    "uptime_seconds": 1
  }
}
```

`status` 也可能是 `degraded`，通常表示 Qdrant local path 或 collection 初始化不可用。LLM 未配置时 `model_loaded=false` 是正常状态。

## Readiness 检查

默认 readiness 只检查配置和 provider 构建，不发真实模型请求：

```bash
./.venv/bin/python -m agent_service.tools.readiness_check
```

需要真实探针时使用：

```bash
./.venv/bin/python -m agent_service.tools.readiness_check --live
```

`--live` 会真实调用 LLM / Embedding / Reranker provider，只有在 `.env` 已配置并允许外部请求时使用。

## Smoke 验证

本地最小可用验证：

```bash
./.venv/bin/python -m agent_service.tools.smoke_all
```

当前 smoke 覆盖全部 9 个接口的最小路径：

- `GET /agent/v1/health`
- `POST /agent/v1/tutoring/chat`
- `POST /agent/v1/profile/generate`
- `POST /agent/v1/evaluation/generate`
- `POST /agent/v1/assessment/evaluate`
- `POST /agent/v1/assessment/generate-questions`
- `POST /agent/v1/learning-path/generate`
- `POST /agent/v1/resources/generate`
- `POST /agent/v1/memory/compress`

该命令用于本地验收，不依赖真实 webhook、外部 Qdrant server 或真实模型请求。

## 测试

全量测试：

```bash
./.venv/bin/pytest -q
```

OpenAPI 对齐测试：

```bash
./.venv/bin/pytest tests/test_openapi_alignment.py -q
```

常用 focused tests：

```bash
./.venv/bin/pytest tests/test_tutoring_api.py tests/test_tutoring_agent.py -q
./.venv/bin/pytest tests/test_resources_agent.py -q
./.venv/bin/pytest tests/test_memory_agent.py -q
```

## 课程知识入库

课程资料默认放在：

```bash
knowledge_base/
```

支持 PDF / Markdown / TXT。执行摄入：

```bash
./.venv/bin/python -m agent_service.tools.ingest_knowledge \
  --course-id <course_id> \
  --path knowledge_base/<file-or-directory>
```

重复执行会跳过已摄入的源文件。摄入后，题目生成、资源生成、tutoring 工具检索可使用 course knowledge RAG context。

## 日志观察点

联调时重点看以下 INFO / WARNING：

- `LLM enrichment succeeded: <endpoint>`
- `LLM generation succeeded: <endpoint>`
- `RAG retrieved <n> chunks for course_id=<course_id>`
- `User memory RAG retrieved <n> facts for user_id=<user_id>`
- `Tutoring ReAct succeeded`
- `Tutoring structured output succeeded`
- `WARNING` fallback / provider / Qdrant / webhook 失败日志

## 常见问题

### 端口被占用

换端口启动：

```bash
./.venv/bin/uvicorn agent_service.main:app --host 127.0.0.1 --port 8012
```

### Health degraded

先检查 Qdrant local path 是否可写：

```bash
ls -ld qdrant_data
```

如果目录不存在，启动时会尝试自动创建 collection。仍失败时运行：

```bash
./.venv/bin/python -m agent_service.tools.readiness_check
```

### LLM 未命中

确认 `.env` 中 LLM provider 非 `none` 且配置完整：

```bash
./.venv/bin/python -m agent_service.tools.readiness_check --live
```

如果 live 失败，接口仍会走规则版 fallback。

### RAG 返回 0 chunks

检查：

```bash
./.venv/bin/python -m agent_service.tools.readiness_check
```

并确认：

- 已配置 embedding provider；
- 已执行 `ingest_knowledge`；
- 请求中的 `course_id` 与摄入时一致。
