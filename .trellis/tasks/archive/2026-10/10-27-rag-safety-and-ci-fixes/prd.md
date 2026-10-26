# RAG入库数据安全加固与CI门禁修复 (PRD)

## Goal

针对 DUagent RAG 入库及检索体系进行数据安全、事务回滚、检索隔离、Token 预算兜底与历史兼容性加固，并修复 CI 环境 pytest 缺失问题，确保知识库入库具备可靠的教材级隔离、原子生效与故障保护能力。

## Requirements

### P0：数据安全与教材隔离
1. **教材级粒度清理隔离**：
   - `ingest_course_material()` 在清理旧版本向量时，Qdrant 删除过滤器必须同时指定 `course_id` 与 `material_id`（教材标识，例如 `path.name`）。
   - 同一课程下不同教材入库时，严禁误删其他教材的向量数据。
2. **激活强前置与失败防护**：
   - 新版本切片写入后，必须通过 `set_payload` 成功激活且通过点位完整性验证（`is_active=True`），才允许执行旧版本清理。
   - 若 `set_payload` 激活过程抛出异常或激活校验未通过，必须立即回滚清理本次入库的临时切片，并抛出异常阻断流程，**绝对禁止**清理旧版本数据。

### P1：检索正确性与完整性校验
3. **未激活切片防泄露检索**：
   - `build_catalog_kg_context()` 与 `retrieve_course_context()` 在检索知识库时，仅允许读取已激活切片（`is_active=True`）或明确标记的旧版兼容数据（无 `ingestion_version` 且无 `is_active=False`）。
   - 在未查到数据时，严禁无条件放开 `is_active` 进行全量兜底匹配；正在入库或未完成版本（`is_active=False`）绝对不能参与图谱生成或问答检索。
4. **Qdrant 写入数量强校验**：
   - 在激活前执行 `client.count()` 校验，验证实际写入点位数是否等于预期切片数 `len(chunks)`。
   - 若 `count()` 校验失败（数量不一致或网络/客户端异常），必须触发回滚并抛出异常，严禁忽略异常静默进入激活步骤。

### P2：Token 预算、集合兼容与 CI 门禁
5. **章节前缀与最终文本双重预算保护**：
   - 修复章节前缀过长导致切片超预算的问题：在 `TokenAwareRecursiveChunker` 中，若 `prefix_tokens` 过长，动态裁剪或折叠章节路径；
   - 组合 `full_text = f"{prefix}{piece}"` 后，必须对最终文本再次进行 Token 估算校验（`estimate_token_count(full_text) <= safe_threshold`）；若仍然超标，递归降级二次切分。
6. **历史 Collection 兼容与回退读取**：
   - 基于模型动态派生集合名（如 `course_knowledge_{model}_{dim}`）的同时，针对未迁移的历史集合（如 `course_knowledge_v1_1024`）提供向后兼容读取机制。在检索时，若模型派生集合未命中且历史集合存在且向量维度一致，支持透明回退检索。
7. **CI 环境 pytest 依赖补齐**：
   - 在 `backend/requirements.txt` 中补齐 `pytest` 与 `pytest-asyncio`，修复 GitHub Actions CI 在独立虚拟环境中运行 `backend-tests` 报找不到模块的问题。

## Acceptance Criteria

- [ ] 同一课程下连续入库教材 A 与教材 B，教材 A 的有效切片在教材 B 入库后保持完好，数量与检索均不受影响。
- [ ] 模拟新版本激活（`set_payload`）失败或报错，旧版本教材切片完好无损，新版本临时切片被全部回滚清理。
- [ ] 正在写入（`is_active=False`）的数据绝不被 `build_catalog_kg_context` 或 `retrieve_course_context` 召回。
- [ ] `client.count` 不一致或异常时阻断激活并回滚。
- [ ] 任意极端深层或超长章节前缀下，生成的全部 Chunk 最终 Token 均严格 `<= safe_threshold` (400)。
- [ ] 历史 Collection 数据在相同向量维度下可被正常检索，无缝平滑兼容。
- [ ] 编写涵盖上述场景的真实 Qdrant 集成测试，严禁用 Mock 测试替代真实存储检验。
- [ ] 全仓 7 项 CI 质量门禁（`python -X utf8 check_all.py`）100% 通过。
