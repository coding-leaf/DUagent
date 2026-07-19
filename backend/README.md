# EDUagent Backend

FastAPI 后端，负责鉴权、用户、课程、任务、MySQL 持久化、对外 API，以及对 Agent Service 的 HTTP 调用与 Webhook 落库。

## 代码目录

- `app/api/v1/`：路由、鉴权和响应包装。
- `app/services/`：业务编排、Agent HTTP 调用和数据处理。
- `app/models/`：SQLAlchemy ORM 模型。
- `app/schemas/`：请求、响应和内部 webhook 模型。
- `app/core/`、`app/db/`：配置、安全和数据库连接。

## 本地验证

```bash
../.venv/bin/python -m pytest tests -q
```

公开接口以 `../docs/10-client-api/Client-API.openapi.json` 为准；内部 Agent 接口以 `../docs/20-agent-api/Agent-Service.openapi.json` 为准。
