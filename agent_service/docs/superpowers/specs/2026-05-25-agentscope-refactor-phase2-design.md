# Phase 2: AgentScope 深度接入设计

2026-05-25

## 背景

Phase 1 已完成：Qdrant 存储层统一使用 AgentScope `QdrantStore`。
剩余待重构的"直连"代码：

| 区域 | 当前状态 | 目标 |
|------|---------|------|
| 死代码 | `core/ai.py` 中 `OpenAICompatible*Provider` | 移除 |
| 死代码 | `agentscope_course_retrieval.py`（POC，已无调用方） | 移除 |
| 失效配置 | `TUTORING_COURSE_KNOWLEDGE_PROVIDER` | 移除 |
| Tutoring 编排 | 手动调用 `chat_provider.complete()` + 正则 `<agent_result>` | ReActAgent + JSON mode |
| 结构化输出 | 正则 `<agent_result>` 解析 | `response_format: json_object` |

## Phase 2A: 清理死代码

### 修改文件

- `core/ai.py`：移除 `OpenAICompatibleEmbeddingProvider`、`OpenAICompatibleChatProvider`、`_post_openai_compatible_json` 及其专用辅助函数。保留 `OpenAICompatibleRerankerProvider`（AgentScope 无 reranker 模块）。
- `core/config.py`：移除 `TUTORING_COURSE_KNOWLEDGE_PROVIDER`
- `memory/agentscope_course_retrieval.py`：删除文件
- `tests/test_agentscope_course_retrieval.py`：删除文件
- `.env.example`：移除 `TUTORING_COURSE_KNOWLEDGE_PROVIDER` 配置行

## Phase 2B: Tutoring JSON Mode

### 问题

当前 tutoring 使用 prompt 约定 `<agent_result>{...}</agent_result>` 提取结构化元数据。DeepSeek 原生支持 `response_format: {"type": "json_object"}`，可在 API 层面保证输出合法 JSON。

### 设计

```
当前：
  prompt: "... 最后追加 <agent_result>{...}</agent_result>"
  解析: 正则提取 → json.loads()
  降级: 原始文本作为 model_text

目标：
  request: messages + response_format: {"type": "json_object"}
  prompt: "... 最后输出 JSON: {"knowledge_points": [...], "suggestion": "..."}"
  解析: json.loads(content) → 提取字段
  降级: 正则 <agent_result> → 原始文本
```

### 修改文件

- `prompts/tutoring.py`：更新系统提示词为 JSON mode 约定
- `agents/tutoring.py` `parse_tutoring_model_response()`：优先 `json.loads()`，失败降级正则
- `core/ai.py` `AgentScopeChatProvider.complete()`：通过 generate_kwargs 传入 `response_format`

## Phase 2C: ReActAgent Tutor Adapter

### 设计

新增 `agents/tutoring_react.py`：

```python
class TutorReActAgent:
    """基于 ReActAgent 的 tutor 适配器，失败时降级到规则版。"""
    def __init__(self, chat_model, embedding_model, knowledge_base, toolkit):
        ...
    async def generate(request, retrieval_context) -> TutoringModelResponse:
        ...
```

### 架构

```
api/v1/tutoring.py             （不改动）
    |
agents/tutoring.py             （保留规则版 fallback）
    |
agents/tutoring_react.py       （新增: ReActAgent adapter）
    |       |
    |       +-- knowledge: KnowledgeBase(QdrantVectorStore + embedding)
    |       +-- toolkit: Toolkit(diagram, code tools)
    |       +-- memory: InMemoryMemory
    |
core/ai.py                     （现有 AgentScope providers）
memory/vector_store.py         （已重构为 AgentScope）
```

### 降级链

```
TutorReActAgent.generate()
    | 失败
    v
generate_tutoring_model_response()
    | 失败
    v
规则版 generate_tutoring_events()
```

### ReActAgent 带来的收益

- 推理循环（max_iters 上限）
- Generic RAG：Knowledge 在每次回复前自动检索
- 工具自主调用：Agent 自行决定何时调图解/代码工具

### 保持手动处理的部分

- 检索上下文组装（agent 之前运行，喂入 Knowledge）
- SSE 事件组装（API 层）
- 规则版 fallback

## 文件汇总

| Phase | 文件 | 操作 |
|-------|------|------|
| 2A | `core/ai.py` | 移除死 provider |
| 2A | `core/config.py` | 移除失效配置 |
| 2A | `memory/agentscope_course_retrieval.py` | 删除 |
| 2A | `tests/test_agentscope_course_retrieval.py` | 删除 |
| 2A | `.env.example` | 移除失效行 |
| 2B | `prompts/tutoring.py` | JSON mode prompt |
| 2B | `agents/tutoring.py` | JSON mode 解析器 |
| 2B | `core/ai.py` | chat 中传入 response_format |
| 2C | `agents/tutoring_react.py` | **新增** ReActAgent 适配器 |
| 2C | `tests/test_tutoring_react.py` | **新增** 适配器测试 |

## 测试策略

- 2A：跑全量测试，确认无导入错误
- 2B：JSON 解析 + 降级链单元测试
- 2C：mock ReActAgent + fake QdrantStore 单元测试

## 回滚安全性

- 每个 Phase 可独立合入
- 规则版 fallback 全程保留
- API/Schema 不做任何改动
