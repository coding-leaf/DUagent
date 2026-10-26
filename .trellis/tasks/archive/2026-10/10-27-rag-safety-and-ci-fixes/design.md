# RAG入库数据安全加固与CI门禁修复 (Technical Design)

## 1. 架构与边界说明

本项目维持三端架构不变：
- `backend` (FastAPI): 业务编排、课程与教材元数据管理。
- `agent_service_v2` (FastAPI / AgentScope 2.x): RAG 向量存储、文档解析、分块算法、检索与重排。
- `frontend` (Vue 3 / Vite): 前端界面与交互。

本次设计集中在 `agent_service_v2/src/agent_service_v2/tools/rag.py` 内部及 CI 依赖配置，不破坏已有 API 协议。

---

## 2. 核心模块技术设计

### 2.1 教材级粒度隔离与事务状态机 (P0)

```
[开始入库]
   │
   ▼
1. 预处理清洗 (clean_text_preserving_syntax)
   │
   ▼
2. 双重预算切片 (TokenAwareRecursiveChunker)
   │
   ▼
3. 批量写入 Qdrant (is_active=False, material_id=path.name, ingestion_version=UUID)
   │ (写入失败 → 回滚当前 ingestion_version 切片 → 退出)
   ▼
4. 数量强校验 (client.count(ingestion_version))
   │ (校验失败/不匹配/异常 → 回滚当前 ingestion_version 切片 → 抛出异常)
   ▼
5. 原子激活 (set_payload: is_active=True)
   │ (激活失败/异常 → 回滚当前 ingestion_version 切片 → 抛出异常)
   ▼
6. 激活验证 (client.count(ingestion_version, is_active=True) == expected)
   │ (验证失败 → 回滚当前 ingestion_version 切片 → 抛出异常)
   ▼
7. 淘汰同教材旧切片 (delete: course_id == C AND material_id == M AND version != V)
   │ (仅在步骤 6 验证成功后执行，绝不影响其他 material_id)
   ▼
[入库完成]
```

**关键 Filter 设计**：
- **回滚 Filter**：
  `must: [ingestion_version == V]`
- **写入强校验 Filter**：
  `must: [course_id == C, material_id == M, ingestion_version == V]`
- **激活验证 Filter**：
  `must: [ingestion_version == V, is_active == True]`
- **淘汰清理旧版 Filter**：
  `must: [course_id == C, material_id == M], must_not: [ingestion_version == V]`

---

### 2.2 检索防泄露与 Legacy 数据隔离 (P1)

在 `build_catalog_kg_context()` 与 `retrieve_course_context()` 中：
1. **主检索**：
   显式限定 `must: [course_id == catalog_id, is_active == True]`。
2. **历史 Legacy 兜底**：
   当主检索未命中任何切片时，判断是否存在历史遗留数据（在引入蓝绿版本机制前写入的数据）：
   - 条件：`course_id == catalog_id`，且在 Payload 解析时必须满足：
     - `payload.is_active is not False`
     - 且 `payload` 中无正在入库的 `ingestion_version`（或为已确认的 legacy 格式）。
   - 任何显式带有 `is_active=False` 的临时切片直接在过滤器和 Python 端双重剔除，严禁参与图谱生成或上下文拼装。

---

### 2.3 章节前缀超长与最终完整文本 Token 兜底 (P2)

在 `TokenAwareRecursiveChunker` 中：
1. **前缀预算约束**：
   - 最大允许前缀 Tokens 设为 `safe_threshold // 3`（例如 400//3 ≈ 133 tokens）；
   - 若 `estimate_token_count(prefix) > max_allowed_prefix` 且包含多层级面包屑，从左往右折叠高层目录（`[... > 当前节]`），避免前缀本身挤占过多正文空间；
2. **动态正文预算计算**：
   - `max_body_tokens = max(self.safe_threshold - prefix_tokens - 10, self.chunk_size // 2)`；
3. **最终文本双重检查**：
   - 组合 `full_text = f"{prefix}{piece}"` 后，检查 `estimate_token_count(full_text)`；
   - 若 `> safe_threshold`，则针对该 `piece` 采用更激进的切分预算（`safe_threshold - prefix_tokens - 10`）进行二次切片，确保生成的每一个最终 Chunk 都满足 `<= safe_threshold`。

---

### 2.4 历史 Collection 兼容与读取回退 (P2)

在构建知识库集合名称与检索时：
1. `get_course_knowledge_collection_name(settings)` 派生模型集合名称；
2. 在 `retrieve_course_context` 和 `build_catalog_kg_context` 中：
   - 优先在派生的目标 Collection 中查询；
   - 若目标 Collection 暂无该课程切片，且历史默认集合 `course_knowledge_v1_1024`（或配置的默认原始名）存在于 Qdrant，并且向量维度与当前配置匹配，则透明回退至历史集合执行只读查询；
   - 新入库（`ingest_course_material`）始终写入规范派生的隔离集合，促成平滑迁移。

---

### 2.5 CI 环境依赖修复 (P2)

- 在 `backend/requirements.txt` 中增加：
  ```
  pytest==9.1.1
  pytest-asyncio==1.4.0
  ```
- 确保无论是 `check_all.py` 的独立测试，还是 GitHub Actions runner 创建的干净虚拟环境，均能直接运行 `backend-tests` 门禁。
