# 拆解边界越位与重构智能体端知识规划引擎

## Goal

严格划定微服务红线，拔除后端直接调用大模型的越位违规逻辑，彻底重构智能体端课程知识抽取内核：利用 AgentScope 2.x 原生框架能力消除死写“C语言”的硬编码与残留伪 Team，实现通用的课程大纲知识树规划引擎。

## Requirements

### 1. 拔除后端越位的大模型调用 (Remove LLM Leaks from Backend)
- 彻底移除 `backend/app/services/kg_generation.py` 中直接通过 `httpx` 调用大模型 `chat/completions` 的 `generate_kg_from_llm` 函数。
- 后端不再维护任何大模型 Prompt，所有涉及大纲文本（`outline_text`）和切片（`catalog_chunks`）的知识图谱生成请求，100% 委托给 `agent_service_v2`。
- 后端角色纯粹化：仅保留 MySQL 数据持久化、版本管理（`CourseKnowledgeGraph`）与校验转发。

### 2. 拔除智能体端死写“C语言”的硬编码 (Remove Hardcoded Domain Prompts)
- 废除 `agent_service_v2/src/agent_service_v2/agents/leader_team.py` 中写死的 `You are a professional C Programming Curriculum Designer`。
- 重构为基于 AgentScope 2.0.10 原生消息与模型驱动的通用 `CourseCurriculumAgent`。
- 自适应学科教学设计：根据请求传入的课程标题（`course_title`）与专业背景，动态规划知识点层级（章 -> 节 -> 核心要点）与前驱依赖有向无环图（DAG），支持任意课程（数据结构、计算机网络、Python、数学、通识课等）。

### 3. 基于 AgentScope 原生 Tool 机制内置大纲提取 (Built-in Framework Outline Parsers)
- 在 `agent_service_v2` 内置规范的大纲提取能力（支持 Markdown 标题树与 Docx 标题层级提取），严禁大模型临时编写执行动态脚本。
- 以结构化 JSON 规范输出章、节、知识点层级树与前后驱关系。

### 4. 边界契约与无损兼容 (API Compatibility & Zero Regression)
- 保障 Backend 与 Agent 端已有的 `/agent/v2/knowledge/knowledge-graphs/generations` 接口契约完全兼容。
- 保证已有的 245 个单元测试 100% 保持绿灯，并为新提取逻辑添加专项单元测试。

## Acceptance Criteria

- [ ] `backend` 代码库中不再存在直接调用外部大模型 `chat/completions` 生成图谱的逻辑，完全收口至 Agent Service。
- [ ] `agent_service_v2` 彻底移除 `leader_team.py` 中的硬编码 C 语言提示词，通用规划器支持任意学科大纲并生成标准 DAG。
- [ ] `agent_service_v2` 内置的大纲提取工具能稳定解析标准 Markdown / Docx 目录树。
- [ ] 运行 `pytest` 测试套件，全量 245 个测试保持 100% 通过，无回归缺陷。
