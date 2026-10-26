# RAG入库数据安全加固与CI门禁修复 (Implementation Plan)

## Ordered Execution Checklist

- [x] **Step 1: 修复 CI 环境 pytest 依赖与测试配置**
  - 在 `backend/requirements.txt` 中添加 `pytest==9.1.1` 与 `pytest-asyncio==1.4.0`；
  - 验证 GitHub Actions 脚本与本地 `check_all.py` 执行 `backend-tests` 依赖无缺失。

- [x] **Step 2: 实施 Token 预算双重检查与章节前缀保护**
  - 修改 `agent_service_v2/src/agent_service_v2/tools/rag.py` 中 `TokenAwareRecursiveChunker`；
  - 动态计算并裁剪过长前缀，且在拼合 `full_text` 后强制执行 `estimate_token_count(full_text) <= safe_threshold` 校验与二次切分；
  - 单元测试验证极端长前缀下的切片 Token 数严格在预算内。

- [x] **Step 3: 实施教材级粒度清理与激活强前置事务状态机**
  - 修改 `agent_service_v2/src/agent_service_v2/tools/rag.py` 中的 `ingest_course_material`；
  - 淘汰旧切片过滤器增加 `material_id` 匹配；
  - 激活前 `client.count()` 校验失败阻断激活并回滚；
  - 激活后校验已激活点位总数；激活或验证失败立即回滚新切片并抛出异常，严禁清理旧版本。

- [x] **Step 4: 实施检索防泄露与历史 Collection 兼容读取**
  - 修改 `build_catalog_kg_context()` 与 `retrieve_course_context()`；
  - 过滤条件强化，任何包含 `is_active=False` 的临时切片均不参与图谱生成或问答检索；
  - 支持历史 Collection（如 `course_knowledge_v1_1024`）在相同向量维度下的只读回退查询。

- [x] **Step 5: 编写真实的 Qdrant 容器集成测试**
  - 在 `agent_service_v2/tests/test_rag_pipeline.py` 中新增真实集成测试（拒绝 Mock 替代）：
    1. 同一课程多教材连续入库与教材级隔离测试；
    2. 写入或数量校验失败时新数据回滚测试；
    3. 激活失败回滚且旧版本教材数据完好保留测试；
    4. 检索严格隔离未激活临时切片测试；
    5. 历史 Collection 兼容读取测试。

- [x] **Step 6: 执行全仓 7 项 CI 门禁验证**
  - 运行 `python -X utf8 check_all.py`；
  - 确保 7 项检查全部通过（前端 lint/build/unit, 后端 lint/tests, Agent lint/tests）。

## Rollback Points
- 若改动引入破坏性变更，可通过 git checkout 恢复 `agent_service_v2/src/agent_service_v2/tools/rag.py`。
