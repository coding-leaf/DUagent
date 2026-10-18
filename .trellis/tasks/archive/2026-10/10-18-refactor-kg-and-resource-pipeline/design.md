# 技术架构与设计方案 (Technical Design)

## 1. 严格划定系统边界 (Strict Boundary Enforcement)

```text
【旧架构：边界越位，两头散乱】
Backend (8001) ──────(越位直接调用)──────▶ 外部 LLM (chat/completions)
      │
      └─(部分转发)─▶ Agent Service (8002) ──(硬编码 C语言 prompt)──▶ 外部 LLM

【新架构：单向委托，智能体内聚】
Backend (8001) ── (仅负责业务持久化与委托转发)
      │
      │ HTTP 内部鉴权调用: POST /agent/v2/knowledge/knowledge-graphs/generations
      ▼
Agent Service v2 (8002) ── (独占所有分析、大纲解析与大模型能力)
  ├── 1. 通用课程大纲规划智能体 (CourseCurriculumAgent)
  │      - 废除硬编码 C 语言，支持自适应学科注入
  │      - 使用 AgentScope 2.0.10 原生 ChatResponse / Msg
  │      - 强制输出合规的前驱依赖有向无环图 (DAG)
  └── 2. 框架原生大纲解析工具 (DocumentOutlineExtractor)
         - 原生解析 Markdown 标题树与 Docx 标题层级
         - 毫秒级提取规整的章-节-知识点树状数据
```

---

## 2. 核心模块与代码职责重塑

### 2.1 Backend 瘦身与收敛 (`backend/app/services/kg_generation.py`)
- **删除**：彻底移除 `generate_kg_from_llm(outline: str)` 函数。
- **重构**：当 `source_type == "outline_text"` 时，统一调用 Agent Service 暴露的标准接口：
  ```python
  payload = {
      "source_type": "outline_text",
      "context": outline,
      "course_title": course_title,
  }
  return await kg_agent_client.post_json(
      "/agent/v2/knowledge/knowledge-graphs/generations",
      payload,
  )
  ```
- **保留**：保留 Backend 纯粹的图谱版本持久化（`save_knowledge_graph_version`）与拓扑校验（`validate_kg_json_payload`）。

### 2.2 Agent 端重构通用规划智能体 (`agent_service_v2/src/agent_service_v2/agents/curriculum_planner.py`)
- 替代并废弃旧的 `leader_team.py` 中的硬编码实现。
- 系统提示词（System Prompt）全面升级为通用教育学设计范式：
  - 动态注入 `{{course_title}}`（自适应计算机、数学、工程、文学等任意学科）；
  - 规范三级拓扑结构：`nodes`（包含 `id`, `name`, `chapter`, `level`）与 `edges`（包含 `from`, `to` 表示前驱关系）；
  - 内部自动进行拓扑环路自检（DAG Check），确保无闭环依赖。

### 2.3 大纲提取原生工具封装 (`agent_service_v2/src/agent_service_v2/tools/outline_extractor.py`)
- 基于 AgentScope `FunctionTool` 规范暴露：
  - `extract_markdown_outline(content: str) -> dict`
  - `extract_docx_outline(file_path: str) -> dict`
- 提取纯净的 `[{chapter, section, knowledge_points}]` 结构，为规划智能体提供清晰且无噪的大纲上下文。

---

## 3. 兼容性与风险评估

- **零破坏性改动**：
  - Backend 的 `CourseKnowledgeGraph` 数据表结构零修改。
  - 前端调用的 `/admin/course-catalogs/{catalog_id}/knowledge-graphs/generations` 路由契约零修改。
  - 仅仅改变了内部大模型调用的发起位置（从 Backend 违规调用 收回到 Agent Service 正规调用）。
- **可回滚性**：改动完全处于 Python 业务逻辑层，Git 随时可检出恢复。
