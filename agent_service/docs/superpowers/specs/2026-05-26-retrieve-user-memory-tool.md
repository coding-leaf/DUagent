# retrieve_user_memory 工具挂载

## 目标

为 `POST /agent/v1/tutoring/chat` 的 ReActAgent toolkit 新增 `retrieve_user_memory` 工具，使模型在推理循环中可按需查询用户长期记忆。

## 现状

- `retrieve_course_knowledge` 工具已挂载到 ReActAgent toolkit
- 用户记忆已通过首轮注入方式传入 user message（`_build_react_user_message()` 第 63 行）
- `QdrantVectorStore.search_user_memory()` 检索路径已就绪

## 设计

### 两条路径并存

| 路径 | 机制 | 时机 |
|------|------|------|
| 首轮注入 | `retrieval_context.user_memory_facts` 拼入 user message | 每次请求，无需 tool call |
| 工具调用 | `retrieve_user_memory(query)` | ReAct 推理中按需触发 |

- 两条路径数据源一致：均走 `QdrantVectorStore.search_user_memory()`
- 注入负责低成本首轮 grounding，工具负责推理中深挖
- 注入保持现状不变

### 工具行为

```
retrieve_user_memory(query: str) → ToolResponse
```

- 闭包捕获：`user_id`、`embedding_provider`、`vector_store`、`limit`
- `user_id` 为空时返回"当前对话无用户记忆数据"
- 异常时返回"用户记忆检索暂时不可用"，不抛异常
- 返回内容受 `limit` 控制条数，每个 chunk 截断到 500 字符

### 数据流

```
tutoring/chat 请求
  │
  ├─ 首轮注入: user_memory_facts ──→ _build_react_user_message()
  │
  └─ ReAct toolkit:
       ├─ retrieve_course_knowledge(query)  ← 已有
       └─ retrieve_user_memory(query)       ← 新增
            │
            └─ vector_store.search_user_memory(user_id, vector, limit=3)
```

## 变更清单

### agents/tutoring_tools.py

`build_tutoring_toolkit()` 新增 `user_id` 参数，注册第二个工具函数 `retrieve_user_memory`。

工具函数内部调用 `embedding_provider.embed_texts([query])` → `vector_store.search_user_memory(user_id, vector, limit=limit)`，每个结果截断到 500 字符，拼接为 ToolResponse。

### agents/tutoring_react_flow.py

`generate_tutoring_react_response()` 调用 `build_tutoring_toolkit()` 时传入 `request.user_id`。

### 测试

- `test_retrieve_user_memory_returns_facts` — 正常返回
- `test_retrieve_user_memory_empty_user_id` — user_id 为空
- `test_retrieve_user_memory_search_failure` — 异常分支
- 集成测试：ReActAgent 挂载两个工具后正常生成

### WORKFLOW.md

更新"下一步"和接口进度表，标记 `retrieve_user_memory` 工具为已完成。

## 不变项

- 降级链顺序：ReActAgent → chat JSON → rule-based
- toolkit 创建条件：`embedding_provider` 和 `vector_store` 均非 None
- 不新增 Qdrant collection、schema、client 实例
- `QdrantVectorStore` 接口不变
- 首轮注入路径不改
