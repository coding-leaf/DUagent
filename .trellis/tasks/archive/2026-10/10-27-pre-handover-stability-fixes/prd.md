# DUagent 交接前稳定性修复 (PRD)

## Goal

在基线提交 `f8c0099` 之上，全面收敛交付前剩余的稳定性与数据安全缺陷，涵盖同名教材 material_id 物理隔离、历史 Qdrant Collection 语义兼容性保护、宿主机原生 MySQL 部署健壮性与安全加固、Backend 测试事件循环隔离以及 Agent 真实 Qdrant 测试离线确定性，保证交付质量与全仓 CI 7 项门禁 100% 稳定通过。

## Requirements

### P0-01：同名教材教材级粒度与真实业务 ID 隔离
1. **真实 Material ID 传递**：
   - Backend 在 `CatalogIngestionService` 触发入库时，将 `CourseCatalogMaterial.id`（如 `cmat_...`）与 `storage_uri` 一起传递给 Agent Service（`/agent/v2/knowledge/ingestions`）。
   - Agent Service API 数据模型 `MaterialIngestionItem` 增加 `material_id: str | None = None`，并传递给 `ingest_course_material()`。
2. **Qdrant Payload 存储与生命周期管理**：
   - `ingest_course_material()` 中切片 metadata 及 Qdrant Payload 统一采用真实的业务 `material_id`（缺省时降级为 `path.name` 保障向后兼容）。
   - 写入强校验、激活验证、回滚清理及淘汰旧版本切片均基于 `material_id`（同时保留 `filename` 记录物理文件名）。
3. **向后兼容与隔离安全**：
   - 同一 Catalog 下上传多份同名教材（不同 `material_id`）时，各自独立的入库、更新或失败回滚绝不能互相影响、误删对方的向量切片。
   - 保留对旧版未传入 `material_id` 的兼容处理，避免旧数据因缺少 ID 被意外清理。

### P1-01：历史 Qdrant Collection 回退条件严格模型身份校验
1. **语义空间兼容性校验**：
   - 历史集合自动回退机制严禁仅凭“向量维度相同”即静默回退。
   - 必须校验当前配置的 Embedding 模型与历史集合的模型标识兼容性（例如当前集合与历史集合具有兼容的模型标识，或配置显式回退白名单）；
   - 对模型来源无法确认或模型不匹配的 Legacy 集合，采取保守策略，拒绝回退查询，防止余弦空间畸变导致严重幻觉。

### P1-02：宿主机原生 MySQL 部署安全与配置遵循
1. **遵循环境配置**：
   - `deploy_prod.sh` 与 `deploy/ensure_default_admin.sh` 统一使用 `.env` 中的 `DB_HOST`、`DB_PORT`、`DB_USER`、`DB_PASSWORD`、`DB_NAME`，严禁在查询或探活中硬编码端口 `3306` 或固定 host `127.0.0.1`。
2. **区分 Docker 与原生 MySQL 初始化**：
   - 当复用宿主机原生 MySQL 时，建表逻辑严禁调用不存在的 `eduagent-mysql` Docker 容器，必须通过原生 mysql CLI 或安全 Python 回退路径执行 `backend/schema.sql` 初始化。
3. **安全传参与特殊字符处理**：
   - Python pymysql 回退分支严禁将密码以字符串拼接形式嵌入 Python 脚本，必须通过环境变量（如 `MYSQL_PWD` 或 `DB_PASSWORD`）或安全参数传递，确保包含单双引号、反斜杠、特殊符号的密码能够正确连接且无泄露风险。
4. **幂等性保障**：
   - 检测到已存在有效管理员时保持原账号和密码不变，不重置密码。

### P1-03：GitHub Actions CI 门禁全面修复
1. **Backend Pytest 异步事件循环冲突修复**：
   - 根除测试收集导入阶段模块顶层直接调用 `asyncio.run(init_db())` / `asyncio.run(engine.dispose())` 的问题，消除 `RuntimeError: Future attached to a different loop` 报错。
   - 采用标准 pytest-asyncio fixture（如 `autouse` 模块或会话级异步 fixture）安全初始化数据库，完整保留真实数据库测试能力，严禁通过删除或跳过测试掩盖问题。
2. **Agent 真实 Qdrant 集成测试离线确定性**：
   - 为 `agent_service_v2/tests/test_rag_pipeline.py` 的集成测试注入确定性的本地测试 Embedding 模型实现（例如基于哈希或固定维度的确定性生成器），彻底摆脱对外部付费 API Key 的依赖。
   - 保持真实 Qdrant 客户端的增删改查、Payload 过滤、蓝绿切换与回滚测试，不退化为全局 Mock。

## Acceptance Criteria

- [ ] 同一 Catalog 下上传两份同名但 `material_id` 不同的教材，分别或并发入库后，两份教材的向量切片互不影响，各自更新时不误删另一份教材的向量。
- [ ] 历史 Collection 回退逻辑在维度相同但模型不同时严格拒绝回退，并有测试覆盖。
- [ ] `deploy_prod.sh` 与 `deploy/ensure_default_admin.sh` 支持任意配置端口与包含特殊字符密码的数据库连接，并在原生 MySQL 首次建表时不依赖 Docker 容器。
- [ ] Backend 自动化测试在干净环境中运行无 `RuntimeError: Future attached to a different loop` 错误。
- [ ] Agent Service 真实 Qdrant 集成测试在无外部 API Key 的干净 CI 环境下全部通过。
- [ ] 全仓 7 项 CI 质量门禁（`python -X utf8 check_all.py`）100% 通过。
