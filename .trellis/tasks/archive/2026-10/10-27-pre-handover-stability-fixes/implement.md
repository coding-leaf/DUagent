# DUagent 交接前稳定性修复 (Implementation Plan)

## Ordered Execution Checklist

- [x] **Step 1: 贯穿真实 material_id 传递与 Qdrant 强隔离 (P0-01)**
  - 修改 `backend/app/services/catalog_ingestion_service.py`：传递 `material_id: material.id`；
  - 修改 `agent_service_v2/src/agent_service_v2/api/knowledge.py`：数据模型增加 `material_id`，并传递给底层入库函数；
  - 修改 `agent_service_v2/src/agent_service_v2/tools/rag.py`：`ingest_course_material` 接收 `material_id`，写入 Payload 并用于回滚与清理过滤器；
  - 编写回归测试：同一 Catalog、相同文件名、不同 Material ID 的独立入库与更新测试。

- [x] **Step 2: 严格历史 Collection 模型身份兼容校验 (P1-01)**
  - 修改 `agent_service_v2/src/agent_service_v2/tools/rag.py` 中的 `_get_historical_fallback_collection`；
  - 增加模型兼容判定：维度一致且模型兼容才允许回退，未知或不同模型拒绝回退；
  - 增加单元测试：维度相同但模型不同时的拒绝回退断言。

- [x] **Step 3: 宿主机原生 MySQL 部署健壮性与安全加固 (P1-02)**
  - 修改 `deploy/ensure_default_admin.sh` 与 `deploy_prod.sh`；
  - 支持 `DB_PORT`、`DB_HOST`、`DB_USER`；
  - 区分 Docker 与原生 MySQL 建表路径，原生环境不依赖不存在的 Docker 容器；
  - 密码通过环境变量读取，禁止字符串插值拼入 Python 代码；
  - 验证带特殊字符密码与自定义端口场景。

- [x] **Step 4: 根除 Backend 测试事件循环冲突 (P1-03)**
  - 审查并消除 `backend/tests/` 顶层的裸 `asyncio.run(init_db())` / `asyncio.run(_init_schema())`；
  - 改造为标准 pytest / pytest-asyncio fixture；
  - 运行 `backend/.venv/Scripts/python.exe -m pytest backend/tests/` 验证测试收集与执行无 `Future attached to a different loop` 报错。

- [x] **Step 5: Agent 真实 Qdrant 集成测试离线确定性改造 (P1-03)**
  - 在 `agent_service_v2/tests/test_rag_pipeline.py` 中引入确定性本地 Embedding 实现；
  - 保证在无外部 SiliconFlow API Key 的环境中真实读写 Qdrant 依然 100% 稳定运行。

- [x] **Step 6: 全仓 7 项 CI 门禁验证**
  - 运行 `python -X utf8 check_all.py`；
  - 确保全部 7 项测试通过。

## Rollback Points
- 若修复出现非预期回归，使用 git checkout 恢复受影响的单独模块。
