# DUagent 交接前稳定性修复 (Technical Design)

## 1. 架构与边界说明

本项目维持三端架构（`backend` + `agent_service_v2` + `frontend`）与 Docker/宿主机混合部署基础设施。
本次稳定性修复集中在：
- 数据传输契约扩展：Backend -> Agent Service -> Qdrant 传递真实教材 ID；
- 语义安全控制：RAG 历史集合回退的模型身份判定；
- 部署与管理脚本加固：`deploy_prod.sh` 与 `deploy/ensure_default_admin.sh`；
- 测试基础设施健壮性：Backend 事件循环生命周期与 Agent 确定性离线 Embedding。

---

## 2. 核心模块详细设计

### 2.1 教材级物理隔离与真实 ID 贯穿 (P0-01)

#### 数据契约变更：
1. **Backend -> Agent Service** (`/agent/v2/knowledge/ingestions`):
   ```python
   # Backend: backend/app/services/catalog_ingestion_service.py
   payload = {
       "catalog_id": catalog.id,
       "materials": [
           {
               "storage_uri": material.storage_uri or "",
               "material_id": material.id,  # 传入 CourseCatalogMaterial.id
           }
           for material in materials
       ],
   }
   ```
2. **Agent Service Request 契约** (`agent_service_v2/src/agent_service_v2/api/knowledge.py`):
   ```python
   class MaterialIngestionItem(BaseModel):
       storage_uri: str = Field(..., description="课本资源的相对路径或 URI")
       material_id: str | None = Field(None, description="真实教材业务 ID")
   ```
3. **Qdrant 入库与清理生命周期** (`agent_service_v2/src/agent_service_v2/tools/rag.py`):
   - `ingest_course_material(..., material_id: str | None = None)`
   - 确定有效教材标识：`effective_material_id = material_id or path.name`
   - Payload 结构：
     ```python
     meta.update({
         "course_id": course_id,
         "catalog_id": course_id,
         "material_id": effective_material_id,  # 真实业务 ID (如 cmat_...)
         "filename": path.name,                # 原始文件名
         "ingestion_version": ingestion_version,
         "is_active": False,
     })
     ```
   - 写入强校验 Filter、激活验证 Filter、激活后旧版本淘汰 Filter：
     ```python
     # 淘汰同教材旧版本 Filter (严格限定 course_id 与 material_id)
     cleanup_filter = Filter(
         must=[
             FieldCondition(key="chunk.metadata.course_id", match=MatchValue(value=course_id)),
             FieldCondition(key="chunk.metadata.material_id", match=MatchValue(value=effective_material_id)),
         ],
         must_not=[
             FieldCondition(key="chunk.metadata.ingestion_version", match=MatchValue(value=ingestion_version)),
         ],
     )
     ```
   - **效果**：同一 Catalog 下即使两份教材物理文件名完全相同（如 `data.pdf`），只要 `material_id` 不同，旧版本清理只淘汰匹配自身 `material_id` 的点位，绝不影响另一份教材。

---

### 2.2 历史 Qdrant Collection 严格模型语义空间兼容判定 (P1-01)

#### 判定逻辑加固：
1. **语义空间红线**：
   相同维度不等于向量空间兼容。例如同为 1024 维的 `bge-large-zh-v1.5` 与 `text-embedding-3-large`，向量夹角与聚类完全不一致，混用会导致严重幻觉。
2. **模型兼容判定算法**：
   在 `_get_historical_fallback_collection(client, settings, target_collection)` 中：
   - 检查历史集合名称是否含有明确的模型标识（如 `bge_large_zh`）；
   - 或者检查集合 metadata / settings 中是否显式声明了兼容的 fallback 模型映射（例如：`settings.HISTORICAL_FALLBACK_COMPATIBLE_MODELS` 或默认规则）；
   - 若候选历史集合为无模型标识的 Legacy 集合（如纯粹的 `course_knowledge_v1_1024`）：
     - 必须比对当前配置的模型是否为当时该 Legacy 集合使用的基准模型（DUagent 历史 v1 约定基准模型为 `BAAI/bge-large-zh-v1.5`）；
     - 若当前模型并非该兼容基准模型（例如更换为了 `BAAI/bge-m3` 或 `OpenAI` 模型），即使维度恰巧同为 1024，也**坚决拒绝回退**，返回 `None`；
   - 增加单元测试：维度相同但模型不同（如 `custom-1024` vs `bge-large-zh`）时断言返回 `None`。

---

### 2.3 宿主机原生 MySQL 部署安全与通用配置 (P1-02)

1. **环境参数解析**：
   ```bash
   db_host="$(env_value "$ENV_FILE" DB_HOST)"
   db_host="${db_host:-127.0.0.1}"
   db_port="$(env_value "$ENV_FILE" DB_PORT)"
   db_port="${db_port:-3306}"
   db_user="$(env_value "$ENV_FILE" DB_USER)"
   db_user="${db_user:-root}"
   db_password="$(env_value "$ENV_FILE" DB_PASSWORD)"
   db_name="$(env_value "$ENV_FILE" DB_NAME)"
   db_name="${db_name:-duagent}"
   ```
2. **初始化路径解耦**：
   - 若探测到 `eduagent-mysql` 容器正在运行，走 Docker 容器路径：
     `docker exec -e MYSQL_PWD="$db_password" -i eduagent-mysql mysql -u"$db_user" "$db_name" < "$SCHEMA_FILE"`
   - 若原生 MySQL（宿主机直接监听对应端口），且宿主机有 `mysql` 命令：
     `MYSQL_PWD="$db_password" mysql -h "$db_host" -P "$db_port" -u"$db_user" "$db_name" < "$SCHEMA_FILE"`
   - 若原生 MySQL 且宿主机无 `mysql` 命令：
     调用 Python pymysql 脚本分批执行 schema 语句。
3. **安全参数传递**：
   - 在 Python 回退脚本中，通过 `os.environ["DB_PASSWORD"]` 获取密码，严禁在 `-c "..."` 字符串中插值替换，彻底规避包含 `'`、`"`、`\`、`$` 等特殊字符密码的解析失败和注入风险。

---

### 2.4 CI 异步事件循环与确定性测试架构 (P1-03)

#### Backend Pytest 事件循环冲突：
- **问题根源**：模块顶层导入阶段执行 `asyncio.run(init_db())`，连接池与未关闭的底层连接挂靠到了导入期的瞬时 Loop。在执行测试时，pytest-asyncio 重新创建 Loop，引发 `RuntimeError: Future attached to a different loop`。
- **解法**：
  在 `backend/tests/` 中消除所有文件顶层的裸 `asyncio.run(...)`。改为利用 pytest 钩子或在需要初始化的测试模块内使用模块级/函数级 fixture：
  ```python
  @pytest.fixture(scope="module", autouse=True)
  async def setup_test_schema():
      await init_db()
      yield
      await engine.dispose()
  ```
  保证所有异步操作严格在当前测试用例的活动事件循环内创建与销毁。

#### Agent 真实 Qdrant 离线确定性测试：
- **问题根源**：GitHub Actions 环境缺少 API Key 时，`build_embedding_model_from_settings()` 无法构造模型或报错。
- **解法**：
  在 `agent_service_v2/tests/test_rag_pipeline.py` 中，定义轻量确定性本地 DummyEmbedding 类（输出固定 1024 维的确定性向量，例如文本 hash 派生归一化浮点数组），并将其注入/patch 至 KnowledgeBase 实例中。
  保留真实的 Qdrant 客户端调用与读写，既不依赖外部付费 API，又保障集成测试真实覆盖 Qdrant 存储、检索、Payload 过滤与版本回滚。
