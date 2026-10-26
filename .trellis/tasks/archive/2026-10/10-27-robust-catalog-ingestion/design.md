# 教材安全切片与版本化幂等入库技术设计 (Design)

## 1. 架构总览与组件职责

```text
[PDF / 文档文件]
       │
       ▼
1. PDF / Text Parser 提取原始章节 (Sections: titles + text)
       │
       ▼
2. 语法保护型预处理器 (clean_text_preserving_syntax)
   ├── 保护代码块 (```...```) 与公式 ($...$) 不受影响
   └── 针对目录与普通文本：折叠引导线 ([\.·•]{3,} -> '...') 与冗余空白
       │
       ▼
3. Token 感知自适应递归切片器 (TokenAwareRecursiveChunker)
   ├── 读取目标 chunk_size (默认 512) 与 overlap (默认 64)
   ├── 继承章节面包屑路径（注入 Payload 与前缀）
   └── 动态 Token 检测：若块超过安全阈值，按自然语义边界 (段落 -> 句子) 递归二次细分
       │
       ▼
4. 蓝绿版本化 Qdrant 写入流水线 (VersionedIngestionPipeline)
   ├── 依据 (EMBEDDING_MODEL, DIMENSION) 物理隔离 Collection
   ├── 生成唯一版本批次号 ingestion_version
   ├── 分批（batch_size=16~32）写入待生效切片 (is_active=False)
   ├── 写入完整性与健康校验 (Count 校验)
   ├── 原子切换生效版本 (is_active=True)
   └── 异步淘汰清理旧版本切片 (version != ingestion_version)
```

## 2. 核心模块与技术实现细节

### 2.1 语法保护型清洗规则 (`clean_text_preserving_syntax`)
- **保护区提取**：利用正则优先匹配 Markdown 代码块（````...````）、内联代码（`` `...` ``）及 LaTeX 块级/行内数学公式（`$$...$$`、`$...$`），将其替换为唯一占位符（如 `__CODE_BLOCK_0__`）。
- **文本层清洗**：
  - 目录连点折叠：`re.sub(r'[\.·•…]{3,}', '...', line)`；
  - 连续空行压缩：保留最多两个连续换行符；
  - 移除 PDF 常见的换页符 `\f` 与无意义控制字符。
- **还原保护区**：清洗完成后，将占位符准确还原为原始代码与公式，严格保留代码缩进、注释及公式结构。

### 2.2 Token 感知自适应递归二次分块 (`TokenAwareRecursiveChunker`)
- **模型上限与安全阈值**：
  - 读取当前配置的 `EMBEDDING_MODEL` 及对应安全 Token 阈值（`BAAI/bge-large-zh-v1.5` 上限 512，安全阈值设为 400；`BAAI/bge-m3` 上限 8192，安全阈值设为 1200）。
  - Token 计数：中文字符按 1.2 token/字、英文单词按 1.3 token/词进行保守估算（或配合真实分词估算），绝不低估。
- **递归拆分规则**：
  - 优先在章节边界切片；若单节过长，优先在双换行（段落）切片；
  - 若段落仍超限，在标点符号（`。\n`、`！\n`、`？\n`、`；\n`）处切片；
  - 若超大单句（如极长表达式或单行数据）超限，按滑动窗口安全拆分，绝不截断抛弃内容。
- **结构化元数据携带**：
  - 提取解析出的 `chapter_path`（例如 `["第1章 导言", "1.2 变量与算术表达式"]`）；
  - Payload 写入：`headings: list[str]`, `chapter_path: str`；
  - 向量化文本格式：`[{chapter_path}]\n{content_text}`，使嵌入向量携带章节上下文。

### 2.3 Qdrant 蓝绿版本化入库 (`VersionedIngestionPipeline`)
- **Collection 物理隔离设计**：
  - 集合命名规则：默认优先从环境变量读取 `QDRANT_COURSE_KNOWLEDGE_COLLECTION`。
  - 模型变更时，若未显式指定，依据模型规范自动派生安全集合名（例如：`course_knowledge_{model_slug}_{dim}`），确保向量空间 100% 独立，防止不同模型向量混淆导致检索失效。
- **幂等写入与状态切换**：
  1. 生成本轮批次 `ingestion_version = uuid.uuid4().hex`。
  2. 每一条 Qdrant Point 写入 Payload：
     ```json
     {
       "course_id": "<course_id>",
       "catalog_id": "<catalog_id>",
       "material_id": "<material_id>",
       "ingestion_version": "<ingestion_version>",
       "is_active": false,
       "chapter_path": "<chapter_path>",
       "chunk_index": 0,
       "total_chunks": 477,
       "chunk": { ... }
     }
     ```
  3. 分批调用 `kb.insert_document`（batch_size=16），遇到瞬态网络异常实施指数退避重试（最多 3 次）。
  4. 批次全量写入完成后，校验已插入点数是否等于生成切片总数。
  5. 校验通过后，更新该批次点位 `is_active = True`，或者在系统内记录该 `catalog_id` 的当前有效版本 `active_version = ingestion_version`。
  6. 清理逻辑：调用 Qdrant Delete API 删除满足以下条件的陈旧点位：
     `catalog_id == current_catalog_id AND ingestion_version != current_ingestion_version`。
  7. 若写入途中发生不可恢复错误，直接删除本轮未完成的 `ingestion_version` 切片，现有线上检索流量完全不受影响。

## 3. 风险、边界与兼容性

- **向后兼容性**：检索端 `build_catalog_kg_context` 与 AgentScope 检索逻辑增加兼容性支持——优先匹配当前 `active` 或最新版本；老数据若无 `ingestion_version`，在重新入库前仍可降级兜底检索。
- **性能开销**：正则清洗与安全分块在 Python 本地 CPU 完成，处理 300 页教材耗时 < 1 秒，无感知瓶颈。
- **网络开销**：批次控制在 16~32，兼顾 SiliconFlow API 吞吐与单请求连接稳定性。
