# Phase 3: `assessment/generate-questions` ReActAgent 迁移

根据升级方案，当前 `assessment/generate-questions` 接口的编排泄漏在 API 层，且作为复杂推理任务（生成题目 -> 格式自检 -> 调整），非常适合使用 ReActAgent。
本次修改的目标是将 `generate-questions` 升级为使用 ReActAgent，同时完成 API 边界收束。

为满足 AGENTS.md“一次不超过5个文件”的限制，本次迁移拆分为两步。

## 拆分步骤概述

### Step A：API 边界收束与编排函数建立
将 API 层中的 AI Provider 创建和 RAG 逻辑下沉到 `agents/assessment.py`，建立 `generate_questions_with_agent()` 编排入口。此阶段只涉及基础封装，不引入真正的 ReActAgent。

### Step B：引入 ReActAgent
新增 ReActAgent 类、Toolkit 工具（通过闭包注入依赖）和专属 Prompt，并将 ReActAgent 接入到 Step A 建立的编排函数主流程中。

---

## Proposed Changes - Step A

### [agent_service/api/v1/assessment.py]
#### [MODIFY] [assessment.py](file:///home/yezisama/workspace/workflow/EDUagent/agent_service/api/v1/assessment.py)
- 移除直接调用 `get_ai_providers()` 和 `build_question_generation_knowledge_context()` 的逻辑。
- 端点 `generate_questions` 改为只调用 `generate_questions_with_agent(request)`。

### [agent_service/agents/assessment.py]
#### [MODIFY] [assessment.py](file:///home/yezisama/workspace/workflow/EDUagent/agent_service/agents/assessment.py)
- 新增编排函数 `generate_questions_with_agent(request: QuestionGenerateRequest, providers=None, vector_store=None) -> list[GeneratedQuestion]`。
- **依赖注入**：函数内部如果未传入 providers，则调用 `get_ai_providers()` 获取，支持测试注入。
- **RAG 注入**：编排层负责调用 `build_question_generation_knowledge_context(request, embedding_provider, vector_store=vector_store)` 获取 `course_knowledge_context`，并传入后续 LLM 调用。
- **vector_store 注入**：同步调整 `build_question_generation_knowledge_context(request, embedding_provider, vector_store=None, limit=5)`，当 `vector_store` 为 `None` 时才创建 `QdrantVectorStore()`；测试可传 fake store，避免直接依赖真实 Qdrant。
- **降级链（Step A）**：先调用 `generate_questions_with_llm()` (Phase 1A structured_model)，若返回 `None` 或空列表 `[]`，则回落 `generate_questions_data()` (规则版骨架题)。保证最终必定返回非空题目列表，不把 `None` 或空结果泄漏给 API 层。

### [agent_service/tests/test_assessment_agent.py]
#### [MODIFY] [test_assessment_agent.py](file:///home/yezisama/workspace/workflow/EDUagent/agent_service/tests/test_assessment_agent.py)
- 补充对 `generate_questions_with_agent()` 的编排测试，注入 fake providers 验证 API 边界收束逻辑及降级链正常工作。

---

## Proposed Changes - Step B

### [agent_service/agents/assessment_react.py]
#### [NEW] [assessment_react.py](file:///home/yezisama/workspace/workflow/EDUagent/agent_service/agents/assessment_react.py)
- 新增 `QuestionGeneratorReActAgent`，参照 `tutoring_react.py` 结构。
- 提供 `generate` 方法，接收 `QuestionGenerateRequest`。
- 将 `retrieve_course_knowledge` 等工具挂载给 ReActAgent。
- **可用性判断**：仅当 `chat_provider` 同时具备 `model` 和 `formatter` 时才尝试 ReActAgent；否则直接跳过到 LLM structured_model fallback，不抛错。
- **输出协议**：Prompt 要求 ReActAgent 输出 JSON 数组（或包含题目数组的对象）。ReActAgent 结束后提取文本，调用 `agents/assessment.py` 中新增的 `_parse_question_payload()`，再调用现有 `_coerce_questions()` 进行严格类型保护。解析失败或校验后为空列表则返回 `None`。

### [agent_service/agents/assessment_tools.py]
#### [NEW] [assessment_tools.py](file:///home/yezisama/workspace/workflow/EDUagent/agent_service/agents/assessment_tools.py)
- 新增 `retrieve_course_knowledge` 工具工厂。采用闭包捕获 `course_id`、`embedding_provider`、`vector_store` 和 `limit`，避免在工具内部反复创建 Qdrant Client。
- 新增 `validate_question_format` 工具（同闭包形式，如有参数需求），提供本地格式校验（校验内容是否非占位符，选项/答案类型是否一致）。

### [agent_service/prompts/assessment.py]
#### [MODIFY] [assessment.py](file:///home/yezisama/workspace/workflow/EDUagent/agent_service/prompts/assessment.py)
- 新增针对 ReActAgent 的 system prompt（如 `build_question_react_system_prompt()`），强调先调用检索工具、再生成题目、使用自检工具校验并在输出最终结果前修复错误，最终输出标准 JSON。

### [agent_service/agents/assessment.py] (更新编排)
#### [MODIFY] [assessment.py](file:///home/yezisama/workspace/workflow/EDUagent/agent_service/agents/assessment.py)
- 更新 `generate_questions_with_agent()` 的降级链：`QuestionGeneratorReActAgent.generate()` -> `generate_questions_with_llm()` -> `generate_questions_data()`。
- 新增 `_parse_question_payload(raw: str) -> list[dict]`，统一支持：
  - markdown fence 包裹的 JSON；
  - JSON 数组：`[{...}]`；
  - JSON 对象：`{"questions": [{...}]}`。
- 将现有 `_parse_question_json()` 改为调用 `_parse_question_payload()` 或直接替换调用点，避免 ReAct 路径和普通 LLM fallback 出现两套解析规则。
- 所有生成链路都必须将 `None` 或空列表视为失败，继续降级到下一层。

### [agent_service/tests/test_assessment_agent.py] (更新测试)
#### [MODIFY] [test_assessment_agent.py](file:///home/yezisama/workspace/workflow/EDUagent/agent_service/tests/test_assessment_agent.py)
- 增加 ReActAgent 生成的链路测试，注入 fake tools 和 fake providers。

---

## Verification Plan

### Automated Tests
- Step A 后运行：
  ```bash
  ./.venv/bin/pytest tests/test_assessment_agent.py -q
  ./.venv/bin/pytest tests/test_openapi_alignment.py -q
  ./.venv/bin/pytest -q
  ```
- Step B 后运行：
  ```bash
  ./.venv/bin/pytest tests/test_assessment_agent.py -q
  ./.venv/bin/pytest tests/test_openapi_alignment.py -q
  ./.venv/bin/pytest -q
  ```
- 每个步骤完成后更新 `WORKFLOW.md`，记录接口状态、当前上下文、下一步建议、已运行测试命令和结果。

## 文件范围说明

- Step A 修改文件预计为：
  - `api/v1/assessment.py`
  - `agents/assessment.py`
  - `tests/test_assessment_agent.py`
  - `WORKFLOW.md`
- Step B 原计划涉及 5 个代码/测试文件，加上 `WORKFLOW.md` 会超过 AGENTS.md 的单次 5 文件限制，因此 Step B 执行前需要进一步拆分或向用户明确申请超过 5 个文件。
