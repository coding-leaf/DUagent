# 教材安全切片与版本化幂等入库实施计划 (Implementation Plan)

## 1. 实施检查清单 (Ordered Checklist)

- [x] **Step 1: 文本预处理与语法保护清洗模块**
  - 在 `agent_service_v2/src/agent_service_v2/tools/rag.py` 中实现 `clean_text_preserving_syntax`。
  - 支持提取并保护代码块与公式，折叠目录引导符 `[\.·•]{3,}`，压缩多余空行。
  - 编写单元测试验证代码缩进与公式不变形，长连点被成功折叠。

- [x] **Step 2: Token 感知自适应递归二次切片模块**
  - 在 `tools/rag.py` 中引入/实现 `TokenAwareRecursiveChunker`。
  - 根据当前模型动态计算安全 Token 上限，递归切分超长段落；
  - 章节路径（`chapter_path`）结构化挂载至 Chunk 元数据，并前缀化附加到向量文本；
  - 增加章节缺失时的滑动窗口降级逻辑。

- [x] **Step 3: Qdrant 蓝绿版本化写入与淘汰清理**
  - 在 `rag.py` 中升级 `ingest_course_material`。
  - 自动绑定 `ingestion_version` 与 `is_active` 状态；
  - 写入完成后进行计数与健康校验，原子激活新版本并异步清除旧版本脏切片；
  - 增加针对临时网络抖动的指数退避重试。

- [x] **Step 4: 集合模型隔离与检索兼容适配**
  - 验证 Qdrant 集合根据模型名称与维度的隔离机制；
  - 调整 `build_catalog_kg_context`，使其能够感知版本过滤或兼容老切片。

- [x] **Step 5: 真实教材端到端回归验证**
  - 针对此前报错任务 `863bee78bd9e46b5` 的教材《C程序设计语言 (Brian W. Kernighan, Dennis M. Ritchie) ...pdf》执行全量切片与入库测试；
  - 验证写入成功率 100%、无 400 20015 错误抛出、Qdrant 点位完整。

- [x] **Step 6: 全仓质量门禁与回归检验**
  - 执行 `python -X utf8 check_all.py` 确保 7 项检查全绿。

## 2. 验证命令 (Validation Commands)

```bash
# 1. 快速语法与单测验证
python check_all.py --fast

# 2. RAG 切片与清洗单元测试
cd agent_service_v2 && uv run pytest tests/test_rag.py -v

# 3. 真实教材端到端入库测试脚本
cd agent_service_v2 && uv run python -c "
import asyncio, os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv('../.env')
from agent_service_v2.tools.rag import ingest_course_material
from agent_service_v2.agents.model_provider import AgentModelSettings

pdf = Path('../backend/storage/course_catalogs/ce85dae2e0954512/45f7383d68db4b56/C程序设计语言 (Brian W. Kernighan, Dennis M. Ritchie) (z-library.sk, 1lib.sk, z-lib.sk).pdf')
settings = AgentModelSettings()
cnt = asyncio.run(ingest_course_material(pdf, 'ce85dae2e0954512', settings))
print('Successfully ingested chunks:', cnt)
"

# 4. 全仓完整门禁
python -X utf8 check_all.py
```

## 3. 回滚方案 (Rollback Points)

- 若切片或入库逻辑出现未预期的异常，可使用 Git 回滚 `agent_service_v2/src/agent_service_v2/tools/rag.py`。
- Qdrant 写入因采用新版本隔离，未激活版本可通过脚本或接口一键清除，不会污染已有稳定教材向量数据。
